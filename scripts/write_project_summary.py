#!/usr/bin/env python3
"""
write_project_summary.py - Update project summary in the brain database.

Writes to project_registry.summary and updates summary_updated_at.
Called by Claude at end-of-session as part of the end-session protocol.

Usage:
    python3 write_project_summary.py --prefix mb --summary "<text>"
    python3 write_project_summary.py --prefix mb --summary-file <path>
    python3 write_project_summary.py --prefix mb --read   # Read current summary

Exit codes: 0 = success, 1 = error
"""

import argparse
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timezone

import yaml


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


def write_summary(prefix, summary, db_path):
    """Write project summary to project_registry.summary."""
    conn = connect_db(db_path)
    try:
        row = conn.execute(
            "SELECT prefix FROM project_registry WHERE prefix = ?",
            (prefix,),
        ).fetchone()

        if not row:
            print(f"ERROR: Project not found: {prefix}", file=sys.stderr)
            return 1

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        conn.execute(
            "UPDATE project_registry SET summary = ?, summary_updated_at = ? WHERE prefix = ?",
            (summary, now, prefix),
        )
        conn.commit()
        print(f"Project summary updated for '{prefix}' ({len(summary)} chars)")
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    finally:
        conn.close()


def read_summary(prefix, db_path):
    """Read current project summary."""
    conn = connect_db(db_path)
    try:
        row = conn.execute(
            "SELECT summary, summary_updated_at FROM project_registry WHERE prefix = ?",
            (prefix,),
        ).fetchone()
        if row and row[0]:
            print(f"Updated: {row[1]}\n")
            print(row[0])
        else:
            print(f"No summary found for '{prefix}'")
    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="Write project summary to brain DB")
    parser.add_argument("--prefix", required=True, help="Project prefix (e.g., mb, jg)")
    parser.add_argument("--summary", help="Project summary text")
    parser.add_argument("--summary-file", help="Read summary from file")
    parser.add_argument("--read", action="store_true", help="Read current summary instead of writing")
    args = parser.parse_args()

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]

    if args.read:
        read_summary(args.prefix, db_path)
        return

    summary = args.summary
    if args.summary_file:
        if not os.path.exists(args.summary_file):
            print(f"ERROR: Summary file not found: {args.summary_file}", file=sys.stderr)
            sys.exit(1)
        with open(args.summary_file, "r") as f:
            summary = f.read()

    if not summary:
        print("ERROR: Must provide --summary or --summary-file", file=sys.stderr)
        sys.exit(1)

    exit_code = write_summary(args.prefix, summary, db_path)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
