#!/usr/bin/env python3
"""session-end.py - Claude Code SessionEnd hook for claude-brain.

Fires when session ends (/exit or terminal close).
1. Checks if Claude wrote session notes — if not, writes fallback placeholder
2. Runs brain_sync.py to backup the database (detached)
3. Returns {} (session is ending, no context needed)

The fallback placeholder ensures every session has at least basic notes.
Next session-start.py detects the placeholder and forces Claude to write
real notes before doing anything else.

NOTE: May not fire on terminal close. Data integrity guaranteed
by stop.py having captured all exchanges already.

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import glob
import os
import sqlite3
import subprocess
import sys

import yaml


FALLBACK_MARKER = "AUTO-GENERATED FALLBACK"

# Same tag keywords used by import_chatgpt.py and brain_tag_review.py
TAG_KEYWORDS = {
    "book-editing": ["edit", "polish", "chapter", "manuscript", "copyedit", "proofread", "rewrite", "revision"],
    "memoir": ["memoir", "johnny", "goods", "maffia", "mob", "harlem", "gangster", "three fingers"],
    "job-search": ["resume", "job search", "interview", "career", "hiring", "salary", "recruiter", "linkedin"],
    "finance": ["money", "bank", "invest", "stock", "crypto", "budget", "tax", "financial"],
    "coding": ["python", "script", "code", "programming", "debug", "function", "api", "github"],
    "ai-tools": ["chatgpt", "claude", "gpt", "openai", "anthropic", "gemini", "llm", "prompt"],
    "tech-setup": ["linux", "fedora", "install", "setup", "config", "terminal", "laptop", "asus"],
    "family": ["mom", "mother", "father", "wife", "daughter", "son", "family"],
    "health": ["doctor", "medical", "health", "therapy", "leg", "injury"],
    "legal": ["lawyer", "legal", "court", "contract", "lawsuit", "attorney"],
    "home": ["house", "home", "repair", "plumbing", "electric", "hvac", "mortgage"],
    "auto": ["car", "toyota", "highlander", "vehicle", "mechanic"],
    "music": ["music", "song", "guitar", "band", "album"],
    "business": ["business", "company", "startup", "entrepreneur", "marketing"],
    "writing": ["writing", "write", "story", "narrative", "voice", "author", "publisher"],
    "research": ["research", "compare", "analysis", "review", "recommend"],
    "brain-project": ["brain", "mcp", "hook", "session-start", "session-end", "ingest", "sqlite"],
    "launch": ["launch", "readme", "github", "public", "tweet", "reddit", "hacker news"],
}


def _detect_session_id():
    """Auto-detect current session ID from JSONL files (same logic as stop.py)."""
    cwd = os.getcwd()
    encoded_cwd = cwd.replace("/", "-")
    project_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects", encoded_cwd)
    jsonl_files = glob.glob(os.path.join(project_dir, "*.jsonl"))
    if not jsonl_files:
        return None
    jsonl_path = max(jsonl_files, key=os.path.getmtime)
    return os.path.splitext(os.path.basename(jsonl_path))[0]


def _suggest_tags(conn, session_id):
    """Auto-suggest tags from transcript content (same logic as import scripts)."""
    rows = conn.execute(
        """SELECT content FROM transcripts
           WHERE session_id = ? AND role = 'user' AND content IS NOT NULL
           ORDER BY timestamp LIMIT 20""",
        (session_id,),
    ).fetchall()

    if not rows:
        return ""

    search_text = " ".join(r[0][:500].lower() for r in rows if r[0])
    matched = []
    for tag, keywords in TAG_KEYWORDS.items():
        if any(kw in search_text for kw in keywords):
            matched.append(tag)

    return ", ".join(matched[:3]) if matched else ""


def _write_fallback_tags(root, session_id):
    """Check if session has tags. If not, auto-suggest from transcript content."""
    try:
        config_path = os.path.join(root, "config.yaml")
        if not os.path.exists(config_path):
            return
        with open(config_path) as f:
            config = yaml.safe_load(f)
        db_path = config["storage"]["local_db_path"]
        if not os.path.exists(db_path):
            return

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=5000;")

        row = conn.execute(
            "SELECT tags FROM sys_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            conn.close()
            return

        existing_tags = row[0]
        if existing_tags and existing_tags.strip():
            conn.close()
            return

        tags = _suggest_tags(conn, session_id)
        if tags:
            conn.execute(
                "UPDATE sys_sessions SET tags = ? WHERE session_id = ?",
                (tags, session_id),
            )
            conn.commit()

        conn.close()
    except Exception:
        pass


def _write_fallback_notes(root, session_id):
    """Check if session has notes. If not, write a fallback placeholder."""
    try:
        config_path = os.path.join(root, "config.yaml")
        if not os.path.exists(config_path):
            return
        with open(config_path) as f:
            config = yaml.safe_load(f)
        db_path = config["storage"]["local_db_path"]
        if not os.path.exists(db_path):
            return

        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA busy_timeout=5000;")

        # Check if notes already exist
        row = conn.execute(
            "SELECT notes, project FROM sys_sessions WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            conn.close()
            return

        existing_notes = row[0]
        project = row[1] or "unknown"

        # If notes already written by Claude, do nothing
        if existing_notes and existing_notes.strip():
            conn.close()
            return

        # Gather basic session info from transcripts
        stats = conn.execute(
            """SELECT COUNT(*) as msg_count,
                      MIN(timestamp) as first_ts,
                      MAX(timestamp) as last_ts
               FROM transcripts WHERE session_id = ?""",
            (session_id,),
        ).fetchone()

        msg_count = stats[0] if stats else 0
        first_ts = (stats[1] or "unknown")[:19] if stats else "unknown"
        last_ts = (stats[2] or "unknown")[:19] if stats else "unknown"

        # Get first user message as preview
        first_msg = conn.execute(
            """SELECT substr(content, 1, 150) FROM transcripts
               WHERE session_id = ? AND role = 'user' AND content IS NOT NULL
               AND content != ''
               ORDER BY timestamp LIMIT 1""",
            (session_id,),
        ).fetchone()
        preview = first_msg[0].replace("\n", " ").strip() if first_msg else "(no content)"

        # Write fallback note
        fallback = (
            f"{FALLBACK_MARKER}\n"
            f"Claude's end-session protocol did not write notes for this session.\n"
            f"Project: {project} | Messages: {msg_count}\n"
            f"Time: {first_ts} to {last_ts}\n"
            f"First message: \"{preview}\"\n"
            f"NOTE: Rewrite these notes in the next session using the transcript."
        )

        conn.execute(
            "UPDATE sys_sessions SET notes = ? WHERE session_id = ?",
            (fallback, session_id),
        )
        conn.commit()
        conn.close()

    except Exception:
        # Hook must never fail — swallow all errors
        pass


def main():
    # Read stdin (hook protocol requires it)
    sys.stdin.read()

    # Determine ROOT (parent of hooks/)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Check for missing session notes and tags, write fallbacks if needed
    session_id = _detect_session_id()
    if session_id:
        _write_fallback_notes(root, session_id)
        _write_fallback_tags(root, session_id)

    # Run database backup (detached - hook must return immediately)
    try:
        subprocess.Popen(
            [sys.executable, os.path.join(root, "scripts", "brain_sync.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception:
        pass

    print("{}")


if __name__ == "__main__":
    main()
