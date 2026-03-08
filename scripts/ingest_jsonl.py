#!/usr/bin/env python3
"""
ingest_jsonl.py — Core JSONL ingestion engine for claude-brain.

Parses Claude Code JSONL session files, maps projects, deduplicates,
and writes to SQLite (sys_sessions, transcripts, sys_ingest_log, tool_results).

Usage:
    python3 ingest_jsonl.py <file_path> [--project <prefix>] [--type <file_type>]

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

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SKIP_TYPES = {"progress", "file-history-snapshot", "queue-operation"}
STORABLE_TYPES = {"user", "assistant", "system"}
SKIP_CONTENT_BLOCK_TYPES = {"tool_use", "tool_result", "thinking", "redacted_thinking", "image"}

# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

def get_root_path():
    """Determine project root from this script's location (scripts/ -> parent)."""
    return str(pathlib.Path(__file__).resolve().parent.parent)


def load_config(root_path):
    """Load and validate config.yaml."""
    config_path = os.path.join(root_path, "config.yaml")
    if not os.path.exists(config_path):
        raise SystemExit(f"FATAL: config.yaml not found at {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    # Validate required keys
    for key_path in [
        ("storage", "local_db_path"),
        ("jsonl_project_mapping",),
    ]:
        obj = config
        for k in key_path:
            if not isinstance(obj, dict) or k not in obj:
                raise SystemExit(f"FATAL: Missing config key: {'.'.join(key_path)}")
            obj = obj[k]
    return config


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def setup_logging(root_path):
    """Configure file + stderr logging."""
    hostname = socket.gethostname()
    log_dir = os.path.join(root_path, "logs", hostname)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "ingest_jsonl.log")

    logger = logging.getLogger("ingest_jsonl")
    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                            datefmt="%Y-%m-%dT%H:%M:%SZ")

    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.WARNING)
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def connect_db(db_path):
    """Connect to SQLite with WAL mode and busy timeout."""
    if not os.path.exists(db_path):
        raise SystemExit(f"FATAL: Database not found at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


# ---------------------------------------------------------------------------
# Project detection
# ---------------------------------------------------------------------------

def build_project_mappings(config):
    """Build ordered list of (pattern, prefix) for project detection.

    Longer patterns sort first so 'johnny-goods-assistant' matches before
    'johnny-goods'. This handles both Windows folder names and Fedora cwd paths.
    """
    raw = config.get("jsonl_project_mapping", {})
    # Sort by length descending so longer/more-specific patterns match first
    return sorted(raw.items(), key=lambda x: len(x[0]), reverse=True)


def detect_project(file_path, first_line_data, mappings, override=None):
    """Detect project prefix from file path and JSONL cwd field.

    Priority:
    1. --project override
    2. Folder name match from file path
    3. cwd field match from JSONL data
    4. Default: "oth"
    """
    if override:
        return override

    # Normalize path separators for matching
    norm_path = file_path.replace("\\", "/")

    # Check folder name / path fragment match
    for pattern, prefix in mappings:
        if pattern in norm_path:
            return prefix

    # Check cwd from first JSONL line
    if first_line_data:
        cwd = first_line_data.get("cwd", "")
        if cwd:
            norm_cwd = cwd.replace("\\", "/")
            for pattern, prefix in mappings:
                if pattern in norm_cwd:
                    return prefix

    return "oth"


# ---------------------------------------------------------------------------
# File type detection
# ---------------------------------------------------------------------------

def detect_file_type(file_path, first_line_data, override=None):
    """Detect file type: jsonl, subagent, or tool_result.

    Rules:
    - .txt in tool-results/ directory -> tool_result
    - .jsonl with agentId in first line -> subagent
    - .jsonl without agentId -> jsonl
    """
    if override:
        return override

    if file_path.endswith(".txt"):
        # Check if in a tool-results/ directory
        norm = file_path.replace("\\", "/")
        if "/tool-results/" in norm or "/tool_results/" in norm:
            return "tool_result"

    if file_path.endswith(".jsonl"):
        if first_line_data and "agentId" in first_line_data:
            return "subagent"
        return "jsonl"

    # Default based on extension
    if file_path.endswith(".txt"):
        return "tool_result"
    return "jsonl"


# ---------------------------------------------------------------------------
# Content extraction
# ---------------------------------------------------------------------------

def extract_content(message_data):
    """Extract text content from a message object.

    Rules:
    - String content -> use directly
    - Array content -> concatenate text blocks with newline
    - Skip: tool_use, tool_result, thinking, redacted_thinking, image
    - No text blocks -> return empty string
    - No message -> return empty string
    """
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
            block_type = block.get("type", "")
            if block_type == "text":
                text_parts.append(block.get("text", ""))
            elif block_type in SKIP_CONTENT_BLOCK_TYPES:
                continue
            # Unknown block types are silently skipped
        return "\n".join(text_parts)

    return ""


# ---------------------------------------------------------------------------
# JSONL ingestion
# ---------------------------------------------------------------------------

def ingest_jsonl_file(conn, file_path, project, file_type, logger):
    """Ingest a JSONL file (type=jsonl or subagent) into the database.

    Returns (records_imported, records_skipped).
    """
    is_subagent = 1 if file_type == "subagent" else 0
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    records_imported = 0
    records_skipped = 0
    session_data = {}  # session_id -> {earliest_timestamp, model, cwd, version}

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, 1):
            raw_line = raw_line.strip()
            if not raw_line:
                records_skipped += 1
                continue

            # Parse JSON
            try:
                data = json.loads(raw_line)
            except json.JSONDecodeError:
                logger.warning("Malformed JSON at line %d in %s", line_num, file_path)
                records_skipped += 1
                continue

            # Skip non-storable types
            msg_type = data.get("type", "")
            if msg_type in SKIP_TYPES:
                records_skipped += 1
                continue
            if msg_type not in STORABLE_TYPES:
                records_skipped += 1
                logger.warning("Unknown type '%s' at line %d in %s", msg_type, line_num, file_path)
                continue

            # Require uuid
            uuid = data.get("uuid")
            if not uuid:
                logger.warning("Missing uuid at line %d in %s", line_num, file_path)
                records_skipped += 1
                continue

            # Extract fields
            session_id = data.get("sessionId", "")
            parent_uuid = data.get("parentUuid")
            subtype = data.get("subtype")
            timestamp = data.get("timestamp", "")

            message = data.get("message")
            if isinstance(message, dict):
                role = message.get("role")
                model = message.get("model")
                content = extract_content(message)
                usage = message.get("usage", {})
                token_input = usage.get("input_tokens") if isinstance(usage, dict) else None
                token_output = usage.get("output_tokens") if isinstance(usage, dict) else None
                stop_reason = message.get("stop_reason")
            else:
                # System messages may have content directly on the object
                role = None
                model = None
                content = data.get("content", "")
                if isinstance(content, list):
                    # Handle array content on system messages
                    content = extract_content({"content": content})
                elif not isinstance(content, str):
                    content = ""
                token_input = None
                token_output = None
                stop_reason = None

            # Track session metadata
            if session_id and session_id not in session_data:
                session_data[session_id] = {
                    "earliest_timestamp": timestamp,
                    "model": None,
                    "cwd": data.get("cwd", ""),
                    "version": data.get("version", ""),
                }
            if session_id and session_id in session_data:
                sd = session_data[session_id]
                # Update earliest timestamp
                if timestamp and (not sd["earliest_timestamp"] or timestamp < sd["earliest_timestamp"]):
                    sd["earliest_timestamp"] = timestamp
                # Capture model from first assistant message
                if msg_type == "assistant" and model and not sd["model"]:
                    sd["model"] = model

            # Insert transcript row
            try:
                changes_before = conn.total_changes
                conn.execute(
                    """INSERT OR IGNORE INTO transcripts
                       (session_id, project, uuid, parent_uuid, type, subtype, role,
                        content, model, timestamp, token_input, token_output,
                        stop_reason, is_subagent, source_file, raw_json, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, project, uuid, parent_uuid, msg_type, subtype, role,
                     content, model, timestamp, token_input, token_output,
                     stop_reason, is_subagent, file_path, raw_line, now),
                )
                if conn.total_changes > changes_before:
                    records_imported += 1
            except sqlite3.IntegrityError:
                # Duplicate uuid — silent skip per contract
                pass

    # Write session rows
    for sid, sd in session_data.items():
        conn.execute(
            """INSERT OR IGNORE INTO sys_sessions
               (session_id, project, started_at, model, source, claude_version, cwd, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, project, sd["earliest_timestamp"], sd["model"],
             "jsonl_ingest", sd["version"], sd["cwd"], now),
        )

    conn.commit()
    return records_imported, records_skipped


# ---------------------------------------------------------------------------
# Tool result ingestion
# ---------------------------------------------------------------------------

def ingest_tool_result(conn, file_path, project, logger):
    """Ingest a tool-result .txt file into the database.

    Returns (records_imported, records_skipped).
    """
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Derive session_id from parent folder name
    # e.g., .../22b8b7ec-0a61-4740-a387-3e2b864c516a/tool-results/bezrmeixj.txt
    parts = pathlib.Path(file_path).parts
    session_id = ""
    for i, part in enumerate(parts):
        if part in ("tool-results", "tool_results") and i > 0:
            session_id = parts[i - 1]
            break

    # tool_use_id = filename without extension
    tool_use_id = pathlib.Path(file_path).stem

    # Read file contents
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        logger.error("Failed to read tool result file %s: %s", file_path, e)
        return 0, 1

    try:
        conn.execute(
            """INSERT INTO tool_results
               (session_id, project, tool_use_id, content, source_file, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, project, tool_use_id, content, file_path, now),
        )
        conn.commit()
        return 1, 0
    except sqlite3.IntegrityError:
        return 0, 1


# ---------------------------------------------------------------------------
# Main ingest function (importable by startup_check.py)
# ---------------------------------------------------------------------------

def ingest(file_path, project_override=None, type_override=None,
           config=None, root_path=None):
    """Main ingest entry point. Can be called as module or CLI.

    Returns dict: {records_imported, records_skipped, project, file_type, exit_code}
    """
    if root_path is None:
        root_path = get_root_path()
    if config is None:
        config = load_config(root_path)

    logger = setup_logging(root_path)
    db_path = config["storage"]["local_db_path"]

    # Resolve to absolute path
    file_path = os.path.abspath(file_path)

    # Check file exists
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return {"records_imported": 0, "records_skipped": 0,
                "project": "oth", "file_type": "unknown", "exit_code": 1}

    # Connect to DB
    try:
        conn = connect_db(db_path)
    except SystemExit as e:
        logger.error(str(e))
        return {"records_imported": 0, "records_skipped": 0,
                "project": "oth", "file_type": "unknown", "exit_code": 2}

    try:
        # Check ingest log for duplicates
        cur = conn.execute(
            "SELECT file_path FROM sys_ingest_log WHERE file_path = ?", (file_path,)
        )
        if cur.fetchone():
            logger.info("Already ingested, skipping: %s", file_path)
            return {"records_imported": 0, "records_skipped": 0,
                    "project": "oth", "file_type": "skipped", "exit_code": 0}

        # Read first line for detection
        first_line_data = None
        if file_path.endswith(".jsonl"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for raw in f:
                        raw = raw.strip()
                        if not raw:
                            continue
                        try:
                            first_line_data = json.loads(raw)
                            # For detection, we want the first line with a cwd field
                            # (file-history-snapshot won't have one)
                            if "cwd" in first_line_data:
                                break
                            # Keep looking for a line with cwd
                            candidate = first_line_data
                            first_line_data = candidate
                        except json.JSONDecodeError:
                            continue
            except Exception:
                pass

        # Detect file type and project
        file_type = detect_file_type(file_path, first_line_data, type_override)
        mappings = build_project_mappings(config)
        project = detect_project(file_path, first_line_data, mappings, project_override)

        # Perform ingestion
        if file_type in ("jsonl", "subagent"):
            records_imported, records_skipped = ingest_jsonl_file(
                conn, file_path, project, file_type, logger
            )
        elif file_type == "tool_result":
            records_imported, records_skipped = ingest_tool_result(
                conn, file_path, project, logger
            )
        else:
            logger.error("Unknown file type: %s", file_type)
            return {"records_imported": 0, "records_skipped": 0,
                    "project": project, "file_type": file_type, "exit_code": 1}

        # Record in ingest log
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        file_size = os.path.getsize(file_path)
        conn.execute(
            """INSERT INTO sys_ingest_log
               (file_path, file_size, file_type, records_imported, ingested_at)
               VALUES (?, ?, ?, ?, ?)""",
            (file_path, file_size, file_type, records_imported, now),
        )
        conn.commit()

        # Update session message counts
        if file_type in ("jsonl", "subagent"):
            conn.execute(
                """UPDATE sys_sessions SET message_count = (
                       SELECT COUNT(*) FROM transcripts WHERE transcripts.session_id = sys_sessions.session_id
                   ) WHERE session_id IN (
                       SELECT DISTINCT session_id FROM transcripts WHERE source_file = ?
                   )""",
                (file_path,),
            )
            conn.commit()

        logger.info("Ingested %d records from %s (%d skipped)", records_imported, file_path, records_skipped)

        return {"records_imported": records_imported, "records_skipped": records_skipped,
                "project": project, "file_type": file_type, "exit_code": 0}

    except Exception as e:
        logger.error("Unexpected error ingesting %s: %s", file_path, e)
        return {"records_imported": 0, "records_skipped": 0,
                "project": "oth", "file_type": "unknown", "exit_code": 1}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest JSONL/tool-result files into claude-brain DB")
    parser.add_argument("file_path", help="Path to JSONL file or tool-result .txt file")
    parser.add_argument("--project", default=None, help="Project prefix override (default: auto-detect)")
    parser.add_argument("--type", dest="file_type", default=None,
                        choices=["jsonl", "subagent", "tool_result"],
                        help="File type override (default: auto-detect)")
    args = parser.parse_args()

    result = ingest(args.file_path, project_override=args.project, type_override=args.file_type)

    # Print summary to stdout
    print(f"Ingested {result['records_imported']} records from {args.file_path} ({result['records_skipped']} skipped)")

    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
