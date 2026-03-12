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
import re
import sqlite3
import subprocess
import sys

import yaml


def main():
    # Read stdin (hook protocol requires it; SessionStart sends {})
    sys.stdin.read()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 1. Run startup check — ingest new files, verify folders, backup DB
    #    stdout/stderr suppressed — hook stdout is SACRED (JSON only)
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
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ""}}))
            return

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=5000;")

        lines = []

        # Verification checklist — always first, non-negotiable
        lines.append("## Session Start Checklist")
        lines.append("- **MANDATORY: Search the brain AND web (search_transcripts, search_semantic, get_recent_summaries, exa-search) BEFORE your first substantive response.** This is Rule #1. Brain has 24,000+ transcripts. Exa has the entire web. Use BOTH.")
        lines.append("- Before acting on inherited work: verify the premise independently")
        lines.append("- Before debugging: identify WHICH component is actually failing")
        lines.append("- Do NOT trust prior session notes blindly — they may contain wrong assumptions")
        lines.append("")

        # Get last session notes (most valuable context for continuity)
        notes_text = None
        try:
            notes_row = conn.execute("""
                SELECT session_id, project, notes, started_at
                FROM sys_sessions
                WHERE notes IS NOT NULL AND notes != ''
                ORDER BY started_at DESC LIMIT 1
            """).fetchone()
            if notes_row:
                date = notes_row[3][:10] if notes_row[3] else "unknown"
                notes_text = notes_row[2] or ""
                lines.append("## Last Session Notes")
                lines.append(f"Date: {date} | Project: {notes_row[1]}")
                lines.append("")
                lines.append(notes_text)
                lines.append("")
        except Exception:
            pass

        # Scan last session notes for unfinished/unverified items
        if notes_text:
            unfinished_patterns = [
                r"\bNOT YET VERIFIED\b", r"\bNOT DONE\b", r"\bunverified\b",
                r"\buntested\b", r"\bneeds verification\b", r"\bVERIFY\b",
                r"\bnot yet tested\b", r"\bstill broken\b", r"\bstill failing\b",
            ]
            flagged = []
            for note_line in notes_text.split("\n"):
                stripped = note_line.strip()
                # Skip section headers (## Blockers, etc.)
                if stripped.startswith("#"):
                    continue
                if stripped and any(
                    re.search(p, stripped, re.IGNORECASE)
                    for p in unfinished_patterns
                ):
                    flagged.append(stripped)
            if flagged:
                lines.append("## Unfinished Items From Last Session")
                lines.append("VERIFY these independently before continuing:")
                for f in flagged:
                    lines.append(f"- {f}")
                lines.append("")

        # Gap detection: find recent sessions missing notes
        try:
            gaps = conn.execute("""
                SELECT session_id, project, started_at
                FROM sys_sessions
                WHERE (notes IS NULL OR notes = '')
                ORDER BY started_at DESC
                LIMIT 20
            """).fetchall()
            if gaps:
                lines.append("## Sessions Missing Notes")
                lines.append(f"{len(gaps)} session(s) have no notes. Consider writing notes for these:")
                for sid, proj, started in gaps:
                    date = started[:10] if started else "unknown"
                    short_id = sid[:12] if sid else "?"
                    lines.append(f"- {date} | {proj} | {short_id}...")
                lines.append("")
        except Exception:
            pass

        # Project summary injection: show current project context
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
                    lines.append("## Current Project Summary")
                    lines.append(proj_row[0])
                    lines.append("")
        except Exception:
            pass

        # Get last 10 sessions with notes, grouped by project
        rows = conn.execute("""
            SELECT project, notes, started_at
            FROM sys_sessions
            WHERE notes IS NOT NULL AND notes != ''
            ORDER BY started_at DESC
            LIMIT 10
        """).fetchall()
        conn.close()

        if rows:
            # Group by project
            by_project = {}
            for project, notes, started_at in rows:
                if project not in by_project:
                    by_project[project] = []
                by_project[project].append((notes, started_at))

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
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "\n".join(lines)}}))
        else:
            print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ""}}))

    except Exception:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": ""}}))


if __name__ == "__main__":
    main()
