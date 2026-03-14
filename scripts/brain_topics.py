#!/usr/bin/env python3
"""
brain_topics.py - Browse sessions grouped by tag.

Shows all tags in the brain with session counts, then lets you drill
into a specific tag to see the sessions under it.

Usage:
  python3 scripts/brain_topics.py                  # Show all tags
  python3 scripts/brain_topics.py "finance"        # Show sessions tagged 'finance'
  python3 scripts/brain_topics.py --project jg     # Tags for JG project only

Usage via slash command: /brain-topics
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent


def load_config():
    config_path = ROOT_DIR / "config.yaml"
    if not config_path.exists():
        print("config.yaml not found.")
        sys.exit(1)
    import yaml
    with open(config_path) as f:
        config = yaml.safe_load(f)
    storage = config.get("storage", {})
    mode = storage.get("mode", "local")
    if mode == "synced":
        return os.path.expanduser(storage.get("local_db_path", ""))
    else:
        return os.path.join(os.path.expanduser(storage.get("root_path", "")), "claude-brain.db")


def show_all_tags(conn, project=None):
    """Show all tags with session counts."""
    where = "WHERE tags IS NOT NULL AND tags != ''"
    if project:
        where += f" AND project = '{project}'"

    rows = conn.execute(f"""
        SELECT tags, project, source, started_at, message_count
        FROM sys_sessions
        {where}
        ORDER BY started_at
    """).fetchall()

    # Count tags
    tag_counts = {}
    tag_projects = {}
    tag_sources = {}
    for tags, proj, source, started, msgs in rows:
        for tag in [t.strip() for t in tags.split(",") if t.strip()]:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
            if tag not in tag_projects:
                tag_projects[tag] = set()
            tag_projects[tag].add(proj)
            if tag not in tag_sources:
                tag_sources[tag] = set()
            tag_sources[tag].add(source or "unknown")

    if not tag_counts:
        print("No tagged sessions found.")
        if not project:
            print("Run /brain-tag-review to tag your sessions.")
        return

    # Print summary
    total_tagged = len(rows)
    total_sessions = conn.execute("SELECT count(*) FROM sys_sessions").fetchone()[0]
    untagged = total_sessions - total_tagged

    title = f"Brain Topics"
    if project:
        title += f" (project: {project})"
    print(f"\n{title}")
    print(f"{'=' * 60}")
    print(f"Tagged sessions: {total_tagged} | Untagged: {untagged} | Total: {total_sessions}")
    print()

    # Sort by count
    print(f"  {'Tag':<20} {'Sessions':>8}  {'Projects':<20} {'Sources'}")
    print(f"  {'-'*20} {'-'*8}  {'-'*20} {'-'*20}")
    for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
        projects = ", ".join(sorted(tag_projects[tag]))
        sources = ", ".join(sorted(tag_sources[tag]))
        print(f"  {tag:<20} {count:>8}  {projects:<20} {sources}")

    print(f"\nTo see sessions for a tag: /brain-topics finance")
    print(f"To filter by project: /brain-topics --project jg")


def show_tag_sessions(conn, tag, project=None):
    """Show all sessions for a specific tag."""
    where = "WHERE tags LIKE ?"
    params = [f"%{tag}%"]
    if project:
        where += " AND project = ?"
        params.append(project)

    rows = conn.execute(f"""
        SELECT session_id, project, started_at, source, message_count, tags,
               substr(notes, 1, 120) as summary
        FROM sys_sessions
        {where}
        ORDER BY started_at DESC
    """, params).fetchall()

    if not rows:
        print(f"\nNo sessions found with tag '{tag}'.")
        return

    # Filter to exact tag match (not substring)
    filtered = []
    for r in rows:
        session_tags = [t.strip().lower() for t in (r[5] or "").split(",")]
        if tag.lower() in session_tags:
            filtered.append(r)

    if not filtered:
        print(f"\nNo sessions found with exact tag '{tag}'.")
        return

    title = f"Sessions tagged: {tag}"
    if project:
        title += f" (project: {project})"
    print(f"\n{title}")
    print(f"{'=' * 60}")
    print(f"Found: {len(filtered)} sessions\n")

    print(f"  {'Date':<12} {'Proj':<6} {'Source':<16} {'Msgs':>5}  Summary")
    print(f"  {'-'*12} {'-'*6} {'-'*16} {'-'*5}  {'-'*40}")
    for r in filtered:
        date = r[2][:10] if r[2] else "?"
        proj = r[1] or "?"
        source = r[3] or "?"
        msgs = r[4] or 0
        summary = r[6] or ""
        # Clean summary
        summary = summary.replace("\n", " ")[:60]
        print(f"  {date:<12} {proj:<6} {source:<16} {msgs:>5}  {summary}")


def main():
    parser = argparse.ArgumentParser(description="Browse brain sessions by tag")
    parser.add_argument("tag", nargs="?", help="Show sessions for this tag")
    parser.add_argument("--project", metavar="PREFIX", help="Filter to one project")

    args = parser.parse_args()

    db_path = load_config()
    conn = sqlite3.connect(db_path)

    if args.tag:
        show_tag_sessions(conn, args.tag, args.project)
    else:
        show_all_tags(conn, args.project)

    conn.close()


if __name__ == "__main__":
    main()
