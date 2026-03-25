#!/usr/bin/env python3
"""
write_session_notes.py - Store session notes in the brain database.

Replaces the LAST SESSION block in MEMORY.md. Notes are written to
sys_sessions.notes and read by session-start.py on next session start.

Usage:
    python3 write_session_notes.py --notes <text>
    python3 write_session_notes.py --notes <text> --tags "coding,debugging"
    python3 write_session_notes.py --notes-file <path>

Session ID is auto-detected from the active session's JSONL file.

Exit codes: 0 = success, 1 = error
"""

import argparse
import glob
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
        print(f"ERROR: config.yaml not found at {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def connect_db(db_path):
    if not os.path.exists(db_path):
        print(f"ERROR: Database not found at {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def auto_detect_session_id():
    """Auto-detect current session ID from JSONL files (same logic as stop.py)."""
    cwd = os.getcwd()
    encoded_cwd = cwd.replace("/", "-")
    project_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects", encoded_cwd)

    jsonl_files = glob.glob(os.path.join(project_dir, "*.jsonl"))
    if not jsonl_files:
        return None

    jsonl_path = max(jsonl_files, key=os.path.getmtime)
    return os.path.splitext(os.path.basename(jsonl_path))[0]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def write_notes(session_id, notes, db_path, tags=None):
    """Write session notes (and optionally tags) to sys_sessions."""
    conn = connect_db(db_path)
    try:
        # Support both full UUIDs and prefix matches (e.g. first 8 chars)
        row = conn.execute(
            "SELECT session_id FROM sys_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if not row and len(session_id) < 36:
            # Try prefix match for truncated IDs
            row = conn.execute(
                "SELECT session_id FROM sys_sessions WHERE session_id LIKE ?",
                (session_id + "%",),
            ).fetchone()

        if not row:
            print(f"ERROR: Session not found: {session_id}", file=sys.stderr)
            return 1

        full_id = row[0]
        conn.execute(
            "UPDATE sys_sessions SET notes = ? WHERE session_id = ?",
            (notes, full_id),
        )
        if tags:
            conn.execute(
                "UPDATE sys_sessions SET tags = ? WHERE session_id = ?",
                (tags.strip(), full_id),
            )
        conn.commit()
        tag_msg = f", tags: {tags.strip()}" if tags else ""
        print(f"Session notes written for {full_id} ({len(notes)} chars{tag_msg})")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def get_latest_notes(db_path, project=None):
    """Read the most recent session notes (for session-start injection)."""
    conn = connect_db(db_path)
    try:
        if project:
            row = conn.execute(
                """SELECT session_id, project, notes, started_at
                   FROM sys_sessions
                   WHERE notes IS NOT NULL AND notes != '' AND project = ?
                   ORDER BY started_at DESC LIMIT 1""",
                (project,),
            ).fetchone()
        else:
            row = conn.execute(
                """SELECT session_id, project, notes, started_at
                   FROM sys_sessions
                   WHERE notes IS NOT NULL AND notes != ''
                   ORDER BY started_at DESC LIMIT 1""",
            ).fetchone()

        if row:
            return {
                "session_id": row[0],
                "project": row[1],
                "notes": row[2],
                "started_at": row[3],
            }
        return None
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Write session notes to brain DB")
    parser.add_argument("--session-id", help=argparse.SUPPRESS)
    parser.add_argument("--notes", help="Session notes text")
    parser.add_argument("--notes-file", help="Read notes from file instead of --notes")
    parser.add_argument("--tags", help="Comma-separated session tags (e.g. 'coding,debugging,ai-tools')")
    parser.add_argument("--read-latest", action="store_true",
                        help="Read the most recent session notes instead of writing")
    parser.add_argument("--project", help="Filter by project prefix (for --read-latest)")
    args = parser.parse_args()

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]

    if args.read_latest:
        result = get_latest_notes(db_path, args.project)
        if result:
            print(result["notes"])
        else:
            print("No session notes found.")
        return

    # Auto-detect session ID from JSONL (always available during active session)
    session_id = args.session_id or auto_detect_session_id()
    if not session_id:
        print("ERROR: No active session detected.", file=sys.stderr)
        sys.exit(1)

    # Get notes from --notes or --notes-file
    notes = args.notes
    if args.notes_file:
        if not os.path.exists(args.notes_file):
            print(f"ERROR: Notes file not found: {args.notes_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.notes_file, "r") as f:
            notes = f.read()

    if not notes:
        print("ERROR: Must provide --notes or --notes-file", file=sys.stderr)
        sys.exit(1)

    exit_code = write_notes(session_id, notes, db_path, tags=args.tags)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
