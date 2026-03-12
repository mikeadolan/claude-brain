#!/usr/bin/env python3
"""
brain_history.py - Session timeline from the brain database.

Clean list of recent sessions, one line each: date, project, message count,
duration, and topic (from session notes).

Usage:
    python3 brain_history.py
    python3 brain_history.py --project jg --count 5

Exit codes: 0 success, 1 error
"""

import argparse
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
        print(f"FATAL: config.yaml not found at {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def connect_db(db_path):
    if not os.path.exists(db_path):
        print(f"FATAL: database not found at {db_path}", file=sys.stderr)
        sys.exit(1)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


def get_valid_projects(conn):
    rows = conn.execute("SELECT prefix FROM project_registry").fetchall()
    return {r[0] for r in rows}


# ---------------------------------------------------------------------------
# Duration formatting
# ---------------------------------------------------------------------------

def format_duration(started, ended):
    """Calculate and format duration between two ISO timestamps."""
    if not started or not ended:
        return None
    try:
        from datetime import datetime
        fmt1 = "%Y-%m-%dT%H:%M:%S.%fZ"
        fmt2 = "%Y-%m-%dT%H:%M:%SZ"
        fmt3 = "%Y-%m-%dT%H:%M:%S.%f"
        fmt4 = "%Y-%m-%dT%H:%M:%S"

        for fmt in (fmt1, fmt2, fmt3, fmt4):
            try:
                start_dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                end_dt = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                break
            except (ValueError, AttributeError):
                continue
        else:
            return None

        delta = end_dt - start_dt
        total_mins = int(delta.total_seconds() / 60)
        if total_mins < 1:
            return "<1m"
        elif total_mins < 60:
            return f"{total_mins}m"
        else:
            hours = total_mins // 60
            mins = total_mins % 60
            if mins == 0:
                return f"{hours}h"
            return f"{hours}h {mins}m"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Session timeline from the brain database",
        usage="python3 brain_history.py [--project PREFIX] [--count N]"
    )
    parser.add_argument("--project", "-p", default=None,
                        help="Filter by project prefix (jg, gen, mb, etc.)")
    parser.add_argument("--count", "-c", type=int, default=10,
                        help="Number of sessions to show (default: 10)")
    args = parser.parse_args()

    if args.count <= 0:
        print("Usage: /brain-history [--project PREFIX] [--count N]")
        print()
        print("Examples:")
        print("  /brain-history")
        print("  /brain-history --project jg --count 5")
        sys.exit(0)

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]
    conn = connect_db(db_path)

    try:
        # Validate project prefix
        if args.project:
            valid = get_valid_projects(conn)
            if args.project not in valid:
                print(f"Error: unknown project prefix '{args.project}'")
                print(f"Valid prefixes: {', '.join(sorted(valid))}")
                sys.exit(1)

        # Query sessions with notes and message count
        sql = """
            SELECT s.session_id, s.project, s.started_at, s.ended_at,
                   s.message_count, s.notes
            FROM sys_sessions s
            WHERE 1=1
        """
        params = []

        if args.project:
            sql += " AND s.project = ?"
            params.append(args.project)

        sql += " ORDER BY s.started_at DESC LIMIT ?"
        params.append(args.count)

        rows = conn.execute(sql, params).fetchall()

        if not rows:
            if args.project:
                print(f"No sessions found for project: {args.project}")
            else:
                print("No sessions found in the database.")
            sys.exit(0)

        # Format and print
        for row in rows:
            session_id = row[0]
            project = row[1] or "oth"
            started = row[2]
            ended = row[3]
            msg_count = row[4] or 0
            summary = row[5]

            # Date
            date_str = started[:10] if started else "unknown"

            # Duration
            duration = format_duration(started, ended)
            dur_str = f" | {duration}" if duration else ""

            # Topic: extract from notes
            if summary:
                topic = None
                for line in summary.strip().split("\n"):
                    line = line.strip()
                    # Look for "Topic:" line first
                    if line.lower().startswith("topic:"):
                        topic = line[6:].strip()
                        break
                if not topic:
                    # Fallback: first non-empty line that isn't metadata
                    for line in summary.strip().split("\n"):
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("Session:") or line.startswith("Project:") \
                           or line.startswith("Time:") or line.startswith("Exchanges:"):
                            continue
                        # Remove markdown headers
                        if line.startswith("#"):
                            line = line.lstrip("#").strip()
                        topic = line
                        break
                if not topic:
                    topic = "No notes"
                # Truncate if too long
                if len(topic) > 100:
                    topic = topic[:97] + "..."
            else:
                topic = "No notes"

            print(f"{date_str} | {project:<3} | {msg_count:>4} msgs{dur_str} | {topic}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
