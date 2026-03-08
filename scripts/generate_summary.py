#!/usr/bin/env python3
"""
generate_summary.py — Session summary generator for claude-brain.

Builds a structured summary from session transcripts (no LLM calls).
Called by hooks/session-end.sh.

Usage:
    python3 generate_summary.py --session-id <id> --project <prefix>

Exit codes: 0 = success, 1 = error
"""

import argparse
import datetime
import logging
import os
import pathlib
import re
import socket
import sqlite3
import sys

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
    log_file = os.path.join(log_dir, "generate_summary.log")

    logger = logging.getLogger("generate_summary")
    logger.setLevel(logging.DEBUG)

    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                datefmt="%Y-%m-%dT%H:%M:%SZ")
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
# Summary building
# ---------------------------------------------------------------------------

MAX_SUMMARY_LINES = 50


def extract_file_references(text):
    """Find file paths mentioned in text."""
    if not text:
        return []
    # Match common file path patterns
    patterns = [
        r'(?:/[\w./-]+\.(?:py|sh|yaml|yml|md|txt|json|jsonl|db|sql|toml|cfg))',
        r'(?:[\w.-]+\.(?:py|sh|yaml|yml|md|txt|json|jsonl|sql|toml))',
    ]
    refs = set()
    for pat in patterns:
        for match in re.findall(pat, text):
            # Skip very short matches and common false positives
            if len(match) > 4 and match not in ('.py', '.sh', '.md', '.txt'):
                refs.add(match)
    return sorted(refs)


def extract_decisions(text):
    """Find decision-like statements in text."""
    if not text:
        return []
    decisions = []
    for line in text.split('\n'):
        line_lower = line.strip().lower()
        # Match lines that look like decisions
        if any(marker in line_lower for marker in [
            'decision:', 'decided:', 'decision #', 'decision number',
            'we decided', 'decision made', 'locked decision',
        ]):
            clean = line.strip()
            if len(clean) > 10 and len(clean) < 200:
                decisions.append(clean)
    return decisions[:10]  # Cap at 10


def build_summary(transcripts, session_id, project):
    """Build a structured summary from transcript rows.

    Returns summary string, hard-capped at MAX_SUMMARY_LINES.
    """
    if not transcripts:
        return ""

    lines = []

    # Header
    lines.append(f"Session: {session_id}")
    lines.append(f"Project: {project}")

    # Time range
    timestamps = [r['timestamp'] for r in transcripts if r['timestamp']]
    if timestamps:
        lines.append(f"Time: {min(timestamps)} to {max(timestamps)}")

    # Counts
    user_count = sum(1 for r in transcripts if r['type'] == 'user')
    asst_count = sum(1 for r in transcripts if r['type'] == 'assistant')
    sys_count = sum(1 for r in transcripts if r['type'] == 'system')
    lines.append(f"Exchanges: {user_count} user, {asst_count} assistant, {sys_count} system ({len(transcripts)} total)")
    lines.append("")

    # Topic — first user message
    first_user = next((r for r in transcripts if r['type'] == 'user' and r['content']), None)
    if first_user:
        topic = first_user['content'][:200].replace('\n', ' ').strip()
        lines.append(f"Topic: {topic}")
        lines.append("")

    # Key user messages (first line of each, skip tool results)
    user_msgs = [r for r in transcripts
                 if r['type'] == 'user' and r['content'] and r['content'].strip()]
    if len(user_msgs) > 1:
        lines.append("User messages:")
        for msg in user_msgs[:15]:  # Cap at 15
            first_line = msg['content'].split('\n')[0][:120].strip()
            if first_line:
                lines.append(f"  - {first_line}")
        if len(user_msgs) > 15:
            lines.append(f"  ... and {len(user_msgs) - 15} more")
        lines.append("")

    # Decisions found in assistant messages
    all_decisions = []
    for r in transcripts:
        if r['type'] == 'assistant' and r['content']:
            all_decisions.extend(extract_decisions(r['content']))
    if all_decisions:
        lines.append("Decisions:")
        for d in all_decisions[:5]:
            lines.append(f"  - {d[:150]}")
        lines.append("")

    # Files referenced in assistant messages
    all_files = set()
    for r in transcripts:
        if r['type'] == 'assistant' and r['content']:
            all_files.update(extract_file_references(r['content']))
    if all_files:
        lines.append("Files referenced:")
        for f in sorted(all_files)[:20]:  # Cap at 20
            lines.append(f"  - {f}")
        lines.append("")

    # Model info
    models = set(r['model'] for r in transcripts if r['model'])
    if models:
        lines.append(f"Model: {', '.join(sorted(models))}")

    # Hard cap
    if len(lines) > MAX_SUMMARY_LINES:
        lines = lines[:MAX_SUMMARY_LINES - 1]
        lines.append("... (truncated to 50 lines)")

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Main generate function
# ---------------------------------------------------------------------------

def generate_summary(session_id, project, root_path=None, config=None):
    """Generate and store a session summary.

    Returns dict: {summary_lines, exit_code}
    """
    if root_path is None:
        root_path = get_root_path()
    if config is None:
        config = load_config(root_path)

    logger = setup_logging(root_path)
    db_path = config["storage"]["local_db_path"]

    try:
        conn = connect_db(db_path)
    except SystemExit as e:
        logger.error(str(e))
        return {"summary_lines": 0, "exit_code": 1}

    try:
        # Query transcripts for this session
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT session_id, project, uuid, type, subtype, role,
                      content, model, timestamp
               FROM transcripts
               WHERE session_id = ?
               ORDER BY timestamp""",
            (session_id,),
        ).fetchall()
        transcripts = [dict(r) for r in rows]

        if not transcripts:
            logger.warning("No transcripts found for session %s", session_id)
            return {"summary_lines": 0, "exit_code": 0}

        # Build summary
        summary = build_summary(transcripts, session_id, project)
        summary_lines = len(summary.split('\n'))

        if summary_lines > MAX_SUMMARY_LINES:
            logger.warning("Summary exceeded %d lines (%d), truncated", MAX_SUMMARY_LINES, summary_lines)

        # Write to DB (INSERT OR REPLACE to handle re-runs)
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Check if summary exists
        existing = conn.execute(
            "SELECT id FROM sys_session_summaries WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE sys_session_summaries
                   SET project = ?, summary = ?, created_at = ?
                   WHERE session_id = ?""",
                (project, summary, now, session_id),
            )
        else:
            conn.execute(
                """INSERT INTO sys_session_summaries
                   (session_id, project, summary, created_at)
                   VALUES (?, ?, ?, ?)""",
                (session_id, project, summary, now),
            )

        conn.commit()
        logger.info("Summary generated for session %s (%d lines)", session_id, summary_lines)

        return {"summary_lines": summary_lines, "exit_code": 0}

    except Exception as e:
        logger.error("Error generating summary for session %s: %s", session_id, e)
        return {"summary_lines": 0, "exit_code": 1}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate session summary for claude-brain")
    parser.add_argument("--session-id", required=True, help="Session UUID to summarize")
    parser.add_argument("--project", required=True, help="Project prefix")
    args = parser.parse_args()

    result = generate_summary(args.session_id, args.project)
    print(f"Summary generated for session {args.session_id} ({result['summary_lines']} lines)")
    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
