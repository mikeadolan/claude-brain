#!/usr/bin/env python3
"""session-start.py — Claude Code SessionStart hook for claude-brain.

Fires once when a Claude Code session starts.
1. Runs startup_check.py (scan for new JSONL, ingest, backup)
2. Queries recent session summaries from the database
3. Returns summaries as additionalContext for Claude's awareness

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import json
import os
import sqlite3
import subprocess
import sys

import yaml


def main():
    # Read stdin (hook protocol requires it; SessionStart sends {})
    sys.stdin.read()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1. Run startup check — ingest new files, verify folders, backup DB
    #    All output suppressed from stdout (startup_check logs internally)
    try:
        subprocess.run(
            [sys.executable, os.path.join(root, "scripts", "startup_check.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    # 2. Query last session notes + recent summaries and output JSON
    try:
        config_path = os.path.join(root, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        db_path = config["storage"]["local_db_path"]
        if not os.path.exists(db_path):
            print(json.dumps({"additionalContext": ""}))
            return

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=5000;")

        lines = []

        # Get last session notes (most valuable context for continuity)
        try:
            notes_row = conn.execute("""
                SELECT session_id, project, notes, started_at
                FROM sys_sessions
                WHERE notes IS NOT NULL AND notes != ''
                ORDER BY started_at DESC LIMIT 1
            """).fetchone()
            if notes_row:
                date = notes_row[3][:10] if notes_row[3] else "unknown"
                lines.append("## Last Session Notes")
                lines.append(f"Date: {date} | Project: {notes_row[1]}")
                lines.append("")
                lines.append(notes_row[2])
                lines.append("")
        except Exception:
            pass

        # Get last 5 summaries per project (up to 10 total)
        rows = conn.execute("""
            SELECT project, summary, created_at
            FROM sys_session_summaries
            ORDER BY created_at DESC
            LIMIT 10
        """).fetchall()
        conn.close()

        if rows:
            # Group by project
            by_project = {}
            for project, summary, created_at in rows:
                if project not in by_project:
                    by_project[project] = []
                by_project[project].append((summary, created_at))

            lines.append("## Recent Session Context")
            lines.append("")
            for project, entries in by_project.items():
                lines.append(f"### {project}")
                for summary, created_at in entries[:5]:
                    date = created_at[:10] if created_at else "unknown"
                    topic = ""
                    for sline in (summary or "").split("\n"):
                        sline = sline.strip()
                        if sline.startswith("Topic:"):
                            topic = sline[6:].strip()
                            break
                    if not topic:
                        for sline in (summary or "").split("\n"):
                            sline = sline.strip()
                            if sline and not sline.startswith("Session:") and not sline.startswith("Project:") and not sline.startswith("Time:"):
                                topic = sline[:120]
                                break
                    if topic:
                        lines.append(f"- [{date}] {topic}")
                lines.append("")

        if lines:
            print(json.dumps({"additionalContext": "\n".join(lines)}))
        else:
            print(json.dumps({"additionalContext": ""}))

    except Exception:
        print(json.dumps({"additionalContext": ""}))


if __name__ == "__main__":
    main()
