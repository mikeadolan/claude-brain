#!/usr/bin/env python3
"""
status.py — Database stats and health check for claude-brain.

Displays session counts, message counts, project breakdown, backup info,
and semantic search status.

Usage:
    python3 status.py [--json]

Exit codes: 0 always (informational only)
"""

import argparse
import json
import os
import pathlib
import sqlite3
import sys

import yaml

# ---------------------------------------------------------------------------
# Config / DB
# ---------------------------------------------------------------------------

def get_root_path():
    return str(pathlib.Path(__file__).resolve().parent.parent)


def load_config(root_path):
    config_path = os.path.join(root_path, "config.yaml")
    if not os.path.exists(config_path):
        raise SystemExit(f"FATAL: config.yaml not found at {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def connect_db(db_path):
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def get_status(root_path=None, config=None):
    """Collect all status data. Returns dict."""
    if root_path is None:
        root_path = get_root_path()
    if config is None:
        config = load_config(root_path)

    db_path = config["storage"]["local_db_path"]
    result = {
        "db_path": db_path,
        "db_size_kb": 0,
        "sessions": 0,
        "messages": 0,
        "projects": {},
        "last_backup": None,
        "last_backup_size_kb": 0,
        "last_ingest": None,
        "semantic_search": "disabled",
        "embedding_count": 0,
    }

    # DB size
    if os.path.exists(db_path):
        result["db_size_kb"] = round(os.path.getsize(db_path) / 1024, 1)

    conn = connect_db(db_path)
    if conn is None:
        return result

    try:
        # Total sessions
        result["sessions"] = conn.execute("SELECT COUNT(*) FROM sys_sessions").fetchone()[0]

        # Total messages
        result["messages"] = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]

        # Per-project stats
        for row in conn.execute("""
            SELECT s.project,
                   COUNT(DISTINCT s.session_id) as session_count,
                   COALESCE(t.msg_count, 0) as message_count,
                   MAX(s.started_at) as last_session
            FROM sys_sessions s
            LEFT JOIN (
                SELECT project, COUNT(*) as msg_count
                FROM transcripts
                GROUP BY project
            ) t ON t.project = s.project
            GROUP BY s.project
            ORDER BY s.project
        """):
            r = dict(row)
            result["projects"][r["project"]] = {
                "sessions": r["session_count"],
                "messages": r["message_count"],
                "last_session": r["last_session"],
            }

        # Last ingest
        row = conn.execute("SELECT MAX(ingested_at) FROM sys_ingest_log").fetchone()
        if row and row[0]:
            result["last_ingest"] = row[0]
            ingest_count = conn.execute("SELECT COUNT(*) FROM sys_ingest_log").fetchone()[0]
            result["ingest_file_count"] = ingest_count

        # Semantic search (must be before conn.close)
        sem_config = config.get("semantic_search", {})
        if sem_config.get("enabled", False):
            result["semantic_search"] = "enabled"
            try:
                count = conn.execute("SELECT COUNT(*) FROM transcript_embeddings").fetchone()[0]
                result["embedding_count"] = count
            except Exception:
                result["semantic_search"] = "enabled (table missing)"
                result["embedding_count"] = 0

    finally:
        conn.close()

    # Last backup
    backup_dir = os.path.join(root_path, "db-backup")
    if os.path.isdir(backup_dir):
        bak_files = sorted(
            [f for f in os.listdir(backup_dir) if f.endswith(('.bak1', '.bak2'))],
            key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
            reverse=True,
        )
        if bak_files:
            latest = os.path.join(backup_dir, bak_files[0])
            mtime = os.path.getmtime(latest)
            import datetime
            result["last_backup"] = datetime.datetime.fromtimestamp(
                mtime, tz=datetime.timezone.utc
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
            result["last_backup_size_kb"] = round(os.path.getsize(latest) / 1024, 1)

    return result


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------

def print_human(data):
    print("=== Claude Brain Status ===")
    print(f"Database: {data['db_path']} ({data['db_size_kb']} KB)")
    print(f"Sessions: {data['sessions']} total")
    print(f"Messages: {data['messages']} total")

    if data["projects"]:
        print("By project:")
        for proj, info in sorted(data["projects"].items()):
            last = info["last_session"] or "never"
            print(f"  {proj:5s} {info['sessions']:4d} sessions, {info['messages']:6d} messages, last: {last}")

    backup = data["last_backup"] or "never"
    print(f"Last backup: {backup} ({data['last_backup_size_kb']} KB)")

    ingest = data.get("last_ingest") or "never"
    ingest_files = data.get("ingest_file_count", 0)
    print(f"Last ingest: {ingest} ({ingest_files} files)")

    sem = data["semantic_search"]
    emb = data["embedding_count"]
    print(f"Semantic search: {sem} ({emb} embeddings)")
    print("===========================")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Claude Brain status and health check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    data = get_status()

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        print_human(data)

    sys.exit(0)


if __name__ == "__main__":
    main()
