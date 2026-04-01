#!/usr/bin/env python3
"""post-compact.py - Claude Code PostCompact hook for claude-brain.

Fires after context compaction completes.
Re-injects brain context (recent session notes, project summary)
so Claude immediately has memory after losing it to compaction.

Reuses the same DB queries as session-start.py but returns a
lighter payload (no checklist, no NEXT_SESSION.md, no gap detection).

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import json
import os
import sqlite3
import sys

import yaml


def main():
    # Read stdin (hook protocol requires it)
    sys.stdin.read()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    try:
        config_path = os.path.join(root, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        db_path = config["storage"]["local_db_path"]
        if not os.path.exists(db_path):
            print("{}")
            return

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=5000;")

        lines = []
        lines.append("## Post-Compaction Brain Context")
        lines.append("Context was just compacted. Here is what the brain remembers:")
        lines.append("")

        # Current project summary
        try:
            cwd = os.environ.get("CWD", os.getcwd())
            mapping = config.get("jsonl_project_mapping", {})
            cwd_project = None
            for folder, prefix in mapping.items():
                if folder in cwd:
                    cwd_project = prefix
                    break
            if cwd_project:
                proj_row = conn.execute("""
                    SELECT summary FROM project_registry
                    WHERE prefix = ? AND summary IS NOT NULL AND summary != ''
                """, (cwd_project,)).fetchone()
                if proj_row:
                    lines.append("### Current Project")
                    lines.append(proj_row[0])
                    lines.append("")
        except Exception:
            pass

        # Last 5 session notes for context
        try:
            rows = conn.execute("""
                SELECT project, notes, started_at
                FROM sys_sessions
                WHERE notes IS NOT NULL AND notes != ''
                ORDER BY started_at DESC
                LIMIT 5
            """).fetchall()
            if rows:
                lines.append("### Recent Sessions")
                for project, notes, started_at in rows:
                    date = started_at[:10] if started_at else "unknown"
                    topic = ""
                    for sline in (notes or "").split("\n"):
                        sline = sline.strip()
                        if sline and not sline.startswith("Session:") and not sline.startswith("Project:") and not sline.startswith("Time:"):
                            topic = sline[:120]
                            break
                    if topic:
                        lines.append(f"- [{date}] {project}: {topic}")
                lines.append("")
        except Exception:
            pass

        conn.close()

        if lines:
            context = "\n".join(lines)
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PostCompact",
                    "additionalContext": context
                }
            }))
        else:
            print("{}")

    except Exception:
        print("{}")


if __name__ == "__main__":
    main()
