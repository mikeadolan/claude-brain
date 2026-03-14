#!/usr/bin/env python3
"""
write_exchange.py - Live exchange writer for claude-brain.

Captures new messages from the current session's JSONL file into the database.
Called by hooks/stop.py after every Claude response.

Usage:
    python3 write_exchange.py --session-id <id> --jsonl-path <path>

Exit codes: 0 = success, 1 = error (recoverable), 2 = fatal error
"""

import argparse
import datetime
import json
import logging
import os
import pathlib
import socket
import sqlite3
import sys
import time
import yaml

# Suppress HuggingFace model-loading noise (must be before any HF imports)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

# ---------------------------------------------------------------------------
# Constants - shared with ingest_jsonl.py
# ---------------------------------------------------------------------------
SKIP_TYPES = {"progress", "file-history-snapshot", "queue-operation"}
STORABLE_TYPES = {"user", "assistant", "system"}
SKIP_CONTENT_BLOCK_TYPES = {"tool_use", "tool_result", "thinking", "redacted_thinking", "image"}

# ---------------------------------------------------------------------------
# Config / Logging / DB
# ---------------------------------------------------------------------------

def get_root_path():
    return str(pathlib.Path(__file__).resolve().parent.parent)


def load_config(root_path):
    config_path = os.path.join(root_path, "config.yaml")
    if not os.path.exists(config_path):
        raise SystemExit(f"FATAL: config.yaml not found at {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    for key_path in [("storage", "local_db_path")]:
        obj = config
        for k in key_path:
            if not isinstance(obj, dict) or k not in obj:
                raise SystemExit(f"FATAL: Missing config key: {'.'.join(key_path)}")
            obj = obj[k]
    return config


def setup_logging(root_path):
    hostname = socket.gethostname()
    log_dir = os.path.join(root_path, "logs", hostname)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "write_exchange.log")

    logger = logging.getLogger("write_exchange")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                datefmt="%Y-%m-%dT%H:%M:%SZ")
        fmt.converter = time.gmtime
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.WARNING)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger


def connect_db(db_path):
    if not os.path.exists(db_path):
        raise SystemExit(f"FATAL: Database not found at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


# ---------------------------------------------------------------------------
# Content extraction - same logic as ingest_jsonl.py
# ---------------------------------------------------------------------------

def extract_content(message_data):
    if not message_data:
        return ""
    content = message_data.get("content")
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text":
                text_parts.append(block.get("text", ""))
        return "\n".join(text_parts)
    return ""


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def detect_project(config, jsonl_path, cwd):
    """Detect project from path and cwd using config mappings."""
    mappings = config.get("jsonl_project_mapping", {})
    # Sort longer patterns first
    sorted_mappings = sorted(mappings.items(), key=lambda x: len(x[0]), reverse=True)

    norm_path = jsonl_path.replace("\\", "/")
    for pattern, prefix in sorted_mappings:
        if pattern in norm_path:
            return prefix

    if cwd:
        norm_cwd = cwd.replace("\\", "/")
        for pattern, prefix in sorted_mappings:
            if pattern in norm_cwd:
                return prefix

    return "oth"


# ---------------------------------------------------------------------------
# Semantic embedding (conditional - SQLite + numpy, Decision 89)
# ---------------------------------------------------------------------------

SEMANTIC_AVAILABLE = False
_embed_model = None

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    SEMANTIC_AVAILABLE = True
except (ImportError, Exception):
    pass


def _get_embed_model(config):
    """Lazily load the SentenceTransformer model (cached after first call)."""
    global _embed_model
    if _embed_model is not None:
        return _embed_model
    sem_config = config.get("semantic_search", {})
    model_name = sem_config.get("model", "all-MiniLM-L6-v2")
    _embed_model = SentenceTransformer(model_name)
    return _embed_model


def embed_message(config, conn, transcript_id, content, logger):
    """Generate embedding and store in transcript_embeddings table."""
    if not SEMANTIC_AVAILABLE:
        return
    if not config.get("semantic_search", {}).get("enabled", False):
        return
    if not content or len(content.strip()) < 50:
        return

    try:
        model = _get_embed_model(config)
        embedding = model.encode(content)
        embedding_blob = np.array(embedding, dtype=np.float32).tobytes()
        model_name = config.get("semantic_search", {}).get("model", "all-MiniLM-L6-v2")
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn.execute(
            """INSERT OR REPLACE INTO transcript_embeddings
               (transcript_id, embedding, model, created_at)
               VALUES (?, ?, ?, ?)""",
            (transcript_id, embedding_blob, model_name, now),
        )
    except Exception as e:
        logger.warning("Embedding failed for transcript %d: %s", transcript_id, e)


# ---------------------------------------------------------------------------
# Main write function
# ---------------------------------------------------------------------------

def write_exchange(session_id, jsonl_path, root_path=None, config=None):
    """Read JSONL, find new messages, write to DB.

    Returns dict: {new_messages, exit_code}
    """
    if root_path is None:
        root_path = get_root_path()
    if config is None:
        config = load_config(root_path)

    logger = setup_logging(root_path)
    db_path = config["storage"]["local_db_path"]

    jsonl_path = os.path.abspath(jsonl_path)

    if not os.path.exists(jsonl_path):
        logger.error("JSONL file not found: %s", jsonl_path)
        return {"new_messages": 0, "exit_code": 1}

    try:
        conn = connect_db(db_path)
    except SystemExit as e:
        logger.error(str(e))
        return {"new_messages": 0, "exit_code": 2}

    try:
        # Get existing UUIDs for this session
        cur = conn.execute(
            "SELECT uuid FROM transcripts WHERE session_id = ?", (session_id,)
        )
        existing_uuids = {row[0] for row in cur.fetchall()}

        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        new_count = 0
        earliest_ts = None
        latest_ts = None
        model = None
        cwd = None
        version = None

        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line_num, raw_line in enumerate(f, 1):
                raw_line = raw_line.strip()
                if not raw_line:
                    continue

                try:
                    data = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                msg_type = data.get("type", "")
                if msg_type in SKIP_TYPES or msg_type not in STORABLE_TYPES:
                    continue

                uuid = data.get("uuid")
                if not uuid:
                    continue

                # Skip already-stored messages
                if uuid in existing_uuids:
                    continue

                # Track metadata
                ts = data.get("timestamp", "")
                if ts:
                    if earliest_ts is None or ts < earliest_ts:
                        earliest_ts = ts
                    if latest_ts is None or ts > latest_ts:
                        latest_ts = ts

                if cwd is None:
                    cwd = data.get("cwd", "")
                if version is None:
                    version = data.get("version", "")

                # Extract fields
                message = data.get("message")
                if isinstance(message, dict):
                    role = message.get("role")
                    msg_model = message.get("model")
                    content = extract_content(message)
                    usage = message.get("usage", {})
                    token_input = usage.get("input_tokens") if isinstance(usage, dict) else None
                    token_output = usage.get("output_tokens") if isinstance(usage, dict) else None
                    stop_reason = message.get("stop_reason")
                    if msg_type == "assistant" and msg_model and model is None:
                        model = msg_model
                else:
                    role = None
                    msg_model = None
                    content = data.get("content", "")
                    if isinstance(content, list):
                        content = extract_content({"content": content})
                    elif not isinstance(content, str):
                        content = ""
                    token_input = None
                    token_output = None
                    stop_reason = None

                # Detect project
                project = detect_project(config, jsonl_path, cwd)

                parent_uuid = data.get("parentUuid")
                subtype = data.get("subtype")
                is_subagent = 1 if "agentId" in data else 0

                # Insert
                changes_before = conn.total_changes
                conn.execute(
                    """INSERT OR IGNORE INTO transcripts
                       (session_id, project, uuid, parent_uuid, type, subtype, role,
                        content, model, timestamp, token_input, token_output,
                        stop_reason, is_subagent, source_file, raw_json, created_at, source)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, project, uuid, parent_uuid, msg_type, subtype, role,
                     content, msg_model, ts, token_input, token_output,
                     stop_reason, is_subagent, jsonl_path, raw_line, now, "claude_code"),
                )
                if conn.total_changes > changes_before:
                    new_count += 1
                    existing_uuids.add(uuid)

                    # Embed for semantic search if available
                    transcript_id = conn.execute(
                        "SELECT last_insert_rowid()").fetchone()[0]
                    embed_message(config, conn, transcript_id, content, logger)

        # Upsert session row
        if cwd is None:
            cwd = ""
        project = detect_project(config, jsonl_path, cwd)

        # Check if session exists
        existing = conn.execute(
            "SELECT session_id FROM sys_sessions WHERE session_id = ?", (session_id,)
        ).fetchone()

        if existing:
            # Update message_count and ended_at
            total = conn.execute(
                "SELECT COUNT(*) FROM transcripts WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
            conn.execute(
                """UPDATE sys_sessions
                   SET message_count = ?, ended_at = ?
                   WHERE session_id = ?""",
                (total, latest_ts, session_id),
            )
        else:
            # Create new session
            total = conn.execute(
                "SELECT COUNT(*) FROM transcripts WHERE session_id = ?", (session_id,)
            ).fetchone()[0]
            conn.execute(
                """INSERT INTO sys_sessions
                   (session_id, project, started_at, ended_at, model, source,
                    claude_version, cwd, message_count, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, project, earliest_ts, latest_ts, model,
                 "write_exchange", version, cwd, total, now),
            )

        conn.commit()

        logger.info("Wrote %d new messages for session %s", new_count, session_id)
        return {"new_messages": new_count, "exit_code": 0}

    except Exception as e:
        logger.error("Error writing exchange for session %s: %s", session_id, e)
        return {"new_messages": 0, "exit_code": 1}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Write live exchanges to claude-brain DB")
    parser.add_argument("--session-id", required=True, help="Current session UUID")
    parser.add_argument("--jsonl-path", required=True, help="Path to current session JSONL")
    args = parser.parse_args()

    result = write_exchange(args.session_id, args.jsonl_path)
    print(f"Wrote {result['new_messages']} new messages for session {args.session_id}")
    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
