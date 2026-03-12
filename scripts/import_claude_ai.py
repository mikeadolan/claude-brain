#!/usr/bin/env python3
"""
import_claude_ai.py - Import claude.ai JSON conversation exports into claude-brain.

Parses claude.ai export JSON (single conversation per file), maps messages,
writes to sys_sessions + transcripts + sys_ingest_log, moves file to completed/.

Usage:
    python3 import_claude_ai.py <json_file> --project <prefix>

Exit codes: 0 = success, 1 = error
"""

import argparse
import datetime
import json
import logging
import os
import pathlib
import shutil
import socket
import sqlite3
import sys
import time

import yaml

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
    if "storage" not in config or "local_db_path" not in config["storage"]:
        raise SystemExit("FATAL: Missing config key: storage.local_db_path")
    return config


def setup_logging(root_path):
    hostname = socket.gethostname()
    log_dir = os.path.join(root_path, "logs", hostname)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "import_claude_ai.log")

    logger = logging.getLogger("import_claude_ai")
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
# Import logic
# ---------------------------------------------------------------------------

SENDER_MAP = {
    "human": ("user", "user"),
    "assistant": ("assistant", "assistant"),
}


def import_export(file_path, project, root_path=None, config=None, move_on_success=True):
    """Import a claude.ai JSON export file.

    Returns dict: {records_imported, conversation_name, exit_code}
    """
    if root_path is None:
        root_path = get_root_path()
    if config is None:
        config = load_config(root_path)

    logger = setup_logging(root_path)
    db_path = config["storage"]["local_db_path"]
    file_path = os.path.abspath(file_path)

    # Check file exists
    if not os.path.exists(file_path):
        logger.error("File not found: %s", file_path)
        return {"records_imported": 0, "conversation_name": "", "exit_code": 1}

    # Parse JSON
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.error("Invalid JSON in %s: %s", file_path, e)
        return {"records_imported": 0, "conversation_name": "", "exit_code": 1}

    # Validate required fields
    if not isinstance(data, dict):
        logger.error("Expected JSON object in %s", file_path)
        return {"records_imported": 0, "conversation_name": "", "exit_code": 1}

    chat_messages = data.get("chat_messages")
    if not isinstance(chat_messages, list):
        logger.error("Missing or invalid chat_messages in %s", file_path)
        return {"records_imported": 0, "conversation_name": "", "exit_code": 1}

    session_id = data.get("uuid", "")
    conversation_name = data.get("name", "")
    created_at = data.get("created_at", "")
    export_model = data.get("model")

    if not session_id:
        logger.error("Missing uuid in export %s", file_path)
        return {"records_imported": 0, "conversation_name": conversation_name, "exit_code": 1}

    # Connect to DB
    try:
        conn = connect_db(db_path)
    except SystemExit as e:
        logger.error(str(e))
        return {"records_imported": 0, "conversation_name": conversation_name, "exit_code": 1}

    try:
        # Check ingest log
        cur = conn.execute(
            "SELECT file_path FROM sys_ingest_log WHERE file_path = ?", (file_path,)
        )
        if cur.fetchone():
            logger.info("Already imported, skipping: %s", file_path)
            return {"records_imported": 0, "conversation_name": conversation_name, "exit_code": 0}

        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Create session row
        conn.execute(
            """INSERT OR IGNORE INTO sys_sessions
               (session_id, project, started_at, model, source, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, project, created_at, export_model, "claude_ai_import", now),
        )

        # Import messages
        records_imported = 0
        for msg in chat_messages:
            if not isinstance(msg, dict):
                continue

            msg_uuid = msg.get("uuid")
            if not msg_uuid:
                continue

            sender = msg.get("sender", "")
            type_role = SENDER_MAP.get(sender)
            if not type_role:
                logger.warning("Unknown sender '%s' in %s, skipping", sender, file_path)
                continue

            msg_type, role = type_role
            # Content: prefer content[] blocks (newer format), fall back to text field
            content = ""
            content_blocks = msg.get("content")
            if isinstance(content_blocks, list):
                parts = []
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("text"):
                        parts.append(block["text"])
                content = "\n\n".join(parts)
            if not content:
                content = msg.get("text", "")
            timestamp = msg.get("created_at", "")
            parent_uuid = msg.get("parent_message_uuid")
            raw_json = json.dumps(msg)

            changes_before = conn.total_changes
            conn.execute(
                """INSERT OR IGNORE INTO transcripts
                   (session_id, project, uuid, parent_uuid, type, role,
                    content, model, timestamp, is_subagent,
                    source_file, raw_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, project, msg_uuid, parent_uuid, msg_type, role,
                 content, export_model, timestamp, 0,
                 file_path, raw_json, now),
            )
            if conn.total_changes > changes_before:
                records_imported += 1

        # Update session message count
        total = conn.execute(
            "SELECT COUNT(*) FROM transcripts WHERE session_id = ?", (session_id,)
        ).fetchone()[0]
        conn.execute(
            "UPDATE sys_sessions SET message_count = ? WHERE session_id = ?",
            (total, session_id),
        )

        # Record in ingest log
        file_size = os.path.getsize(file_path)
        conn.execute(
            """INSERT INTO sys_ingest_log
               (file_path, file_size, file_type, records_imported, ingested_at)
               VALUES (?, ?, ?, ?, ?)""",
            (file_path, file_size, "claude_ai_import", records_imported, now),
        )

        conn.commit()

        # Move file to imports/completed/
        if move_on_success and records_imported > 0:
            completed_dir = os.path.join(root_path, "imports", "completed")
            os.makedirs(completed_dir, exist_ok=True)
            dest = os.path.join(completed_dir, os.path.basename(file_path))
            # Avoid overwriting if filename exists
            if os.path.exists(dest):
                base, ext = os.path.splitext(os.path.basename(file_path))
                dest = os.path.join(completed_dir, f"{base}_{session_id[:8]}{ext}")
            shutil.move(file_path, dest)
            logger.info("Moved %s -> %s", file_path, dest)

        logger.info("Imported %d messages from '%s' -> project %s",
                     records_imported, conversation_name, project)

        return {"records_imported": records_imported,
                "conversation_name": conversation_name, "exit_code": 0}

    except Exception as e:
        logger.error("Error importing %s: %s", file_path, e)
        return {"records_imported": 0, "conversation_name": conversation_name, "exit_code": 1}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import claude.ai JSON export into claude-brain DB")
    parser.add_argument("json_file", help="Path to claude.ai JSON export file")
    parser.add_argument("--project", required=True, help="Project prefix to assign")
    args = parser.parse_args()

    result = import_export(args.json_file, args.project)
    print(f"Imported {result['records_imported']} messages from '{result['conversation_name']}' -> project {args.project}")
    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
