#!/usr/bin/env python3
"""
brain_export.py — Export brain data to human-readable text files.

Exports sessions, search results, profile, decisions, or weekly recap
to timestamped files in the exports/ folder.

Usage:
    python3 brain_export.py --profile
    python3 brain_export.py --decisions
    python3 brain_export.py --search "ASUS laptop"
    python3 brain_export.py --session abc123
    python3 brain_export.py --recap-week

Exit codes: 0 success, 1 error
"""

import argparse
import os
import pathlib
import re
import sqlite3
import sys
from datetime import datetime, timedelta

import yaml

# ---------------------------------------------------------------------------
# Config / DB
# ---------------------------------------------------------------------------

STOP_WORDS = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "both",
    "each", "few", "more", "most", "other", "some", "such", "no", "nor",
    "not", "only", "own", "same", "so", "than", "too", "very", "just",
    "don", "now", "and", "but", "or", "if", "while", "about", "up",
    "what", "which", "who", "whom", "this", "that", "these", "those",
    "am", "it", "its", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "they", "them", "their",
    "tell", "show", "give", "get", "got", "find", "work", "worked",
    "discuss", "discussed", "talk", "talked", "done",
}

MAX_KEYWORDS = 10


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


def get_exports_dir(root_path):
    exports_dir = os.path.join(root_path, "exports")
    os.makedirs(exports_dir, exist_ok=True)
    return exports_dir


def write_file(exports_dir, suffix, lines):
    """Write lines to a timestamped export file. Returns (path, line_count)."""
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    filename = f"{ts}_{suffix}.txt"
    filepath = os.path.join(exports_dir, filename)
    with open(filepath, "w") as f:
        for line in lines:
            f.write(line + "\n")
    return filepath, len(lines)


# ---------------------------------------------------------------------------
# Export: profile
# ---------------------------------------------------------------------------

def export_profile(conn, exports_dir):
    lines = ["BRAIN PROFILE EXPORT", f"Generated: {datetime.now().isoformat()}", ""]

    # Brain facts
    rows = conn.execute(
        "SELECT category, key, value FROM brain_facts ORDER BY category, key"
    ).fetchall()
    lines.append(f"## Brain Facts ({len(rows)} entries)")
    lines.append("")
    current_cat = None
    for cat, key, value in rows:
        if cat != current_cat:
            if current_cat is not None:
                lines.append("")
            lines.append(f"### {cat}")
            current_cat = cat
        lines.append(f"  {key}: {value}")

    lines.append("")

    # Brain preferences
    rows = conn.execute(
        "SELECT category, preference FROM brain_preferences ORDER BY category"
    ).fetchall()
    lines.append(f"## Brain Preferences ({len(rows)} entries)")
    lines.append("")
    current_cat = None
    for cat, pref in rows:
        if cat != current_cat:
            if current_cat is not None:
                lines.append("")
            lines.append(f"### {cat}")
            current_cat = cat
        lines.append(f"  - {pref}")

    path, count = write_file(exports_dir, "profile_export", lines)
    fact_count = conn.execute("SELECT COUNT(*) FROM brain_facts").fetchone()[0]
    pref_count = conn.execute("SELECT COUNT(*) FROM brain_preferences").fetchone()[0]
    print(f"Exported to: {path} ({fact_count} facts, {pref_count} preferences, {count} lines)")


# ---------------------------------------------------------------------------
# Export: decisions
# ---------------------------------------------------------------------------

def export_decisions(conn, exports_dir):
    lines = ["DECISIONS EXPORT", f"Generated: {datetime.now().isoformat()}", ""]

    rows = conn.execute(
        """SELECT decision_number, project, description, rationale, created_at
           FROM decisions ORDER BY decision_number ASC"""
    ).fetchall()

    lines.append(f"Total: {len(rows)} decisions")
    lines.append("")

    for num, project, desc, rationale, created_at in rows:
        date = (created_at or "")[:10]
        lines.append(f"Decision {num} [{project}] ({date}):")
        lines.append(f"  {desc}")
        if rationale:
            lines.append(f"  Rationale: {rationale}")
        lines.append("")

    path, count = write_file(exports_dir, "decisions_export", lines)
    print(f"Exported to: {path} ({len(rows)} decisions, {count} lines)")


# ---------------------------------------------------------------------------
# Export: session
# ---------------------------------------------------------------------------

def export_session(conn, exports_dir, session_id):
    # Try exact match first, then prefix match
    row = conn.execute(
        "SELECT session_id, project, started_at, ended_at, message_count FROM sys_sessions WHERE session_id = ?",
        (session_id,)
    ).fetchone()

    if not row:
        # Try prefix match
        rows = conn.execute(
            "SELECT session_id, project, started_at, ended_at, message_count FROM sys_sessions WHERE session_id LIKE ?",
            (session_id + "%",)
        ).fetchall()
        if len(rows) == 1:
            row = rows[0]
        elif len(rows) > 1:
            print(f"Multiple sessions match prefix '{session_id}':")
            for r in rows:
                print(f"  {r[0]} ({r[1]}, {(r[2] or '')[:10]})")
            sys.exit(1)
        else:
            print(f"Error: no session found matching '{session_id}'")
            sys.exit(1)

    full_id = row[0]
    project = row[1]
    started = row[2]
    msg_count = row[4] or 0

    lines = [
        "SESSION TRANSCRIPT EXPORT",
        f"Generated: {datetime.now().isoformat()}",
        f"Session: {full_id}",
        f"Project: {project}",
        f"Started: {started}",
        f"Messages: {msg_count}",
        "",
        "=" * 70,
        "",
    ]

    # Get transcript
    msgs = conn.execute(
        """SELECT role, type, content, timestamp
           FROM transcripts
           WHERE session_id = ?
           ORDER BY timestamp ASC, id ASC""",
        (full_id,)
    ).fetchall()

    for role, msg_type, content, timestamp in msgs:
        ts = (timestamp or "")[:19]
        label = (role or msg_type or "unknown").upper()
        lines.append(f"[{ts}] {label}:")
        if content:
            for cline in content.split("\n"):
                lines.append(f"  {cline}")
        else:
            lines.append("  (no content)")
        lines.append("")

    date_str = (started or "unknown")[:10]
    suffix = f"session_{full_id[:8]}_{date_str}"
    path, count = write_file(exports_dir, suffix, lines)
    print(f"Exported to: {path} ({len(msgs)} messages, {count} lines)")


# ---------------------------------------------------------------------------
# Export: search
# ---------------------------------------------------------------------------

def export_search(conn, exports_dir, query):
    # Extract keywords
    cleaned = re.sub(r"[^\w\s']", " ", query)
    words = cleaned.lower().split()
    keywords = [w for w in words if w not in STOP_WORDS and len(w) > 1]
    seen = set()
    unique = []
    for k in keywords:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    keywords = unique[:MAX_KEYWORDS]

    if not keywords:
        keywords = [w.lower() for w in query.split() if len(w) > 2][:MAX_KEYWORDS]

    if not keywords:
        print(f"No searchable keywords found in: {query}")
        sys.exit(1)

    # Build FTS5 query
    escaped = []
    for kw in keywords:
        safe = kw.replace("'", "''")
        if safe.upper() in ("OR", "AND", "NOT", "NEAR"):
            safe = f'"{safe}"'
        escaped.append(safe)
    fts_query = " OR ".join(escaped)

    sql = """
        SELECT t.session_id, t.project, t.role, t.content, t.timestamp
        FROM transcripts_fts fts
        JOIN transcripts t ON t.rowid = fts.rowid
        WHERE transcripts_fts MATCH ?
          AND t.content IS NOT NULL
          AND length(t.content) > 30
        ORDER BY rank
        LIMIT 50
    """

    try:
        rows = conn.execute(sql, (fts_query,)).fetchall()
    except Exception as e:
        print(f"FTS5 search error: {e}", file=sys.stderr)
        sys.exit(1)

    lines = [
        "SEARCH RESULTS EXPORT",
        f"Generated: {datetime.now().isoformat()}",
        f"Query: {query}",
        f"Keywords: {', '.join(keywords)}",
        f"Results: {len(rows)}",
        "",
        "=" * 70,
        "",
    ]

    for session_id, project, role, content, timestamp in rows:
        ts = (timestamp or "")[:19]
        sid = session_id[:8] if session_id else "unknown"
        label = (role or "unknown").upper()
        lines.append(f"[{ts}] Session {sid} ({project}) {label}:")
        if content:
            text = content.strip()
            if len(text) > 500:
                text = text[:500] + "..."
            for cline in text.split("\n"):
                lines.append(f"  {cline}")
        lines.append("")

    # Sanitize query for filename
    safe_query = re.sub(r"[^\w\s-]", "", query)[:30].strip().replace(" ", "_")
    path, count = write_file(exports_dir, f"search_{safe_query}", lines)
    print(f"Exported to: {path} ({len(rows)} results, {count} lines)")


# ---------------------------------------------------------------------------
# Export: recap-week
# ---------------------------------------------------------------------------

def export_recap_week(conn, exports_dir):
    now = datetime.now()
    start_dt = now - timedelta(days=6)
    start_date = start_dt.strftime("%Y-%m-%d")
    end_date = now.strftime("%Y-%m-%d")

    # Get project labels
    labels = {}
    for row in conn.execute("SELECT prefix, label FROM project_registry").fetchall():
        labels[row[0]] = row[1]

    # Query sessions
    rows = conn.execute(
        """SELECT s.session_id, s.project, s.started_at, s.message_count,
                  (SELECT summary FROM sys_session_summaries
                   WHERE session_id = s.session_id
                   ORDER BY created_at DESC LIMIT 1) as summary
           FROM sys_sessions s
           WHERE date(s.started_at) >= ?
           ORDER BY s.started_at ASC""",
        (start_date,)
    ).fetchall()

    # Decisions in range
    decisions = conn.execute(
        """SELECT decision_number, project, description
           FROM decisions WHERE date(created_at) >= ?
           ORDER BY decision_number ASC""",
        (start_date,)
    ).fetchall()

    lines = [
        "WEEKLY RECAP EXPORT",
        f"Generated: {datetime.now().isoformat()}",
        f"Range: {start_date} to {end_date}",
        f"Total sessions: {len(rows)}",
        f"Total messages: {sum(r[3] or 0 for r in rows)}",
        "",
        "=" * 70,
        "",
    ]

    # Group by project
    by_project = {}
    for row in rows:
        project = row[1] or "oth"
        if project not in by_project:
            by_project[project] = []
        by_project[project].append(row)

    dec_by_project = {}
    for d in decisions:
        proj = d[1] or "oth"
        if proj not in dec_by_project:
            dec_by_project[proj] = []
        dec_by_project[proj].append(d)

    for project in sorted(by_project.keys()):
        sessions = by_project[project]
        label = labels.get(project, project)
        msg_count = sum(s[3] or 0 for s in sessions)

        lines.append(f"## {label} ({len(sessions)} sessions, {msg_count} msgs)")
        lines.append("")

        for s in sessions:
            summary = s[4]
            topic = None
            if summary:
                for sline in summary.strip().split("\n"):
                    sline = sline.strip()
                    if sline.lower().startswith("topic:"):
                        topic = sline[6:].strip()
                        break
                if not topic:
                    for sline in summary.strip().split("\n"):
                        sline = sline.strip()
                        if not sline or sline.startswith(("Session:", "Project:", "Time:", "Exchanges:")):
                            continue
                        if sline.startswith("#"):
                            sline = sline.lstrip("#").strip()
                        topic = sline
                        break
            date_str = (s[2] or "")[:10]
            topic = topic or "(no summary)"
            if len(topic) > 120:
                topic = topic[:117] + "..."
            lines.append(f"  [{date_str}] {topic}")

        proj_decs = dec_by_project.get(project, [])
        if proj_decs:
            lines.append("")
            lines.append(f"  Decisions made:")
            for d in proj_decs:
                desc = d[2].strip().split("\n")[0]
                if len(desc) > 100:
                    desc = desc[:97] + "..."
                lines.append(f"    #{d[0]}: {desc}")

        lines.append("")

    path, count = write_file(exports_dir, "recap_week", lines)
    print(f"Exported to: {path} ({len(rows)} sessions, {count} lines)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Export brain data to text files",
        usage="python3 brain_export.py [--profile|--decisions|--search QUERY|--session ID|--recap-week]"
    )
    parser.add_argument("--profile", action="store_true", help="Export all brain facts and preferences")
    parser.add_argument("--decisions", action="store_true", help="Export all decisions")
    parser.add_argument("--session", type=str, default=None, help="Export full transcript for a session")
    parser.add_argument("--search", type=str, default=None, help="Export search results for a query")
    parser.add_argument("--recap-week", action="store_true", help="Export weekly recap")
    args = parser.parse_args()

    # Check that exactly one mode is specified
    modes = sum([args.profile, args.decisions, args.session is not None,
                 args.search is not None, args.recap_week])
    if modes == 0:
        print("Usage: /brain-export FLAG")
        print()
        print("Flags (pick one):")
        print("  --profile       Export all brain facts + preferences")
        print("  --decisions     Export all decisions, numbered")
        print('  --search QUERY  Export search results (e.g. --search "ASUS laptop")')
        print("  --session ID    Export full transcript for a session")
        print("  --recap-week    Export weekly recap to file")
        sys.exit(0)
    if modes > 1:
        print("Error: specify exactly one export flag.")
        sys.exit(1)

    root_path = get_root_path()
    config = load_config(root_path)
    db_path = config["storage"]["local_db_path"]
    exports_dir = get_exports_dir(root_path)
    conn = connect_db(db_path)

    try:
        if args.profile:
            export_profile(conn, exports_dir)
        elif args.decisions:
            export_decisions(conn, exports_dir)
        elif args.session:
            export_session(conn, exports_dir, args.session)
        elif args.search:
            export_search(conn, exports_dir, args.search)
        elif args.recap_week:
            export_recap_week(conn, exports_dir)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
