#!/usr/bin/env python3
"""
brain_recap.py — Progress report for a time range.

Pulls session notes and produces a narrative organized by project:
what was worked on, what was completed, key decisions, what's next.

Usage:
    python3 brain_recap.py              # today (default)
    python3 brain_recap.py --week       # last 7 days
    python3 brain_recap.py --days 3 --project mb

Exit codes: 0 success, 1 error
"""

import argparse
import os
import pathlib
import sqlite3
import sys
from datetime import datetime, timedelta

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


def get_project_labels(conn):
    rows = conn.execute("SELECT prefix, label FROM project_registry").fetchall()
    return {r[0]: r[1] for r in rows}


# ---------------------------------------------------------------------------
# Summary extraction
# ---------------------------------------------------------------------------

def extract_topic(summary):
    """Extract the topic line from a session summary."""
    if not summary:
        return None
    for line in summary.strip().split("\n"):
        line = line.strip()
        if line.lower().startswith("topic:"):
            return line[6:].strip()
    # Fallback: first non-metadata line
    for line in summary.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(("Session:", "Project:", "Time:", "Exchanges:")):
            continue
        if line.startswith("#"):
            line = line.lstrip("#").strip()
        return line
    return None


def extract_section(summary, header):
    """Extract lines under a specific header from summary."""
    if not summary:
        return []
    lines = summary.strip().split("\n")
    in_section = False
    results = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(header.lower()):
            in_section = True
            # Include content after the header on the same line
            after = stripped[len(header):].strip().lstrip(":").strip()
            if after:
                results.append(after)
            continue
        if in_section:
            # Stop at next header-like line
            if stripped and (stripped[0].isupper() or stripped.startswith("#")) \
               and ":" in stripped[:30] and not stripped.startswith("-") \
               and not stripped.startswith("*"):
                break
            if stripped.startswith("-") or stripped.startswith("*"):
                results.append(stripped)
            elif stripped:
                results.append(stripped)
    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Progress report for a time range",
        usage="python3 brain_recap.py [--today|--week|--days N] [--project PREFIX]"
    )
    parser.add_argument("--today", action="store_true", default=False,
                        help="Show today's sessions (default)")
    parser.add_argument("--week", action="store_true", default=False,
                        help="Show last 7 days")
    parser.add_argument("--days", type=int, default=None,
                        help="Show last N days")
    parser.add_argument("--project", "-p", default=None,
                        help="Filter by project prefix")
    args = parser.parse_args()

    # Determine date range
    now = datetime.now()
    if args.days is not None:
        if args.days <= 0:
            print("Usage: /brain-recap [--today|--week|--days N] [--project PREFIX]")
            print()
            print("Examples:")
            print("  /brain-recap              # today")
            print("  /brain-recap --week       # last 7 days")
            print("  /brain-recap --days 3 --project mb")
            sys.exit(0)
        num_days = args.days
    elif args.week:
        num_days = 7
    else:
        # Default: today
        num_days = 1

    if num_days == 1:
        start_date = now.strftime("%Y-%m-%d")
        range_label = f"Today ({start_date})"
    else:
        start_dt = now - timedelta(days=num_days - 1)
        start_date = start_dt.strftime("%Y-%m-%d")
        end_date = now.strftime("%Y-%m-%d")
        range_label = f"Last {num_days} days ({start_date} to {end_date})"

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]
    conn = connect_db(db_path)

    try:
        # Validate project
        if args.project:
            valid = get_valid_projects(conn)
            if args.project not in valid:
                print(f"Error: unknown project prefix '{args.project}'")
                print(f"Valid prefixes: {', '.join(sorted(valid))}")
                sys.exit(1)

        labels = get_project_labels(conn)

        # Query sessions in date range
        sql = """
            SELECT s.session_id, s.project, s.started_at, s.message_count,
                   s.notes
            FROM sys_sessions s
            WHERE date(s.started_at) >= ?
        """
        params = [start_date]

        if args.project:
            sql += " AND s.project = ?"
            params.append(args.project)

        sql += " ORDER BY s.started_at ASC"

        rows = conn.execute(sql, params).fetchall()

        if not rows:
            print(f"RECAP: {range_label}")
            print()
            if args.project:
                print(f"No sessions found for project '{args.project}' in this range.")
            else:
                print("No sessions found in this range.")
            sys.exit(0)

        # Group by project
        by_project = {}
        for row in rows:
            project = row[1] or "oth"
            if project not in by_project:
                by_project[project] = []
            by_project[project].append(row)

        # Also query decisions made in this range
        dec_sql = """
            SELECT d.decision_number, d.project, d.description
            FROM decisions d
            WHERE date(d.created_at) >= ?
        """
        dec_params = [start_date]
        if args.project:
            dec_sql += " AND d.project = ?"
            dec_params.append(args.project)
        dec_sql += " ORDER BY d.decision_number ASC"

        decisions = conn.execute(dec_sql, dec_params).fetchall()
        dec_by_project = {}
        for d in decisions:
            proj = d[1] or "oth"
            if proj not in dec_by_project:
                dec_by_project[proj] = []
            dec_by_project[proj].append(d)

        # Print recap
        total_sessions = len(rows)
        total_msgs = sum(r[3] or 0 for r in rows)
        print(f"RECAP: {range_label}")
        print(f"Total: {total_sessions} sessions, {total_msgs} messages")
        print()

        for project in sorted(by_project.keys()):
            sessions = by_project[project]
            label = labels.get(project, project)
            session_count = len(sessions)
            msg_count = sum(s[3] or 0 for s in sessions)

            print(f"{label} ({session_count} session{'s' if session_count != 1 else ''}, {msg_count} msgs):")

            # Extract topics from each session
            for s in sessions:
                summary = s[4]
                topic = extract_topic(summary)
                if topic:
                    # Clean up common prefixes
                    clean = topic.strip()
                    if len(clean) > 120:
                        clean = clean[:117] + "..."
                    print(f"  - {clean}")
                else:
                    date_str = (s[2] or "")[:10]
                    print(f"  - [{date_str}] (no notes)")

            # Show decisions for this project
            proj_decs = dec_by_project.get(project, [])
            if proj_decs:
                nums = [str(d[0]) for d in proj_decs]
                print(f"  Decisions: {', '.join(nums)}")

            print()

    finally:
        conn.close()


if __name__ == "__main__":
    main()
