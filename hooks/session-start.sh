#!/usr/bin/env bash
# session-start.sh — Claude Code SessionStart hook for claude-brain.
#
# Fires once when a Claude Code session starts.
# 1. Runs startup_check.py (scan for new JSONL, ingest, backup)
# 2. Queries recent session summaries from the database
# 3. Returns summaries as additionalContext for Claude's awareness
#
# RULE: stdout is SACRED. Only valid JSON goes to stdout.
# All other output goes to stderr, /dev/null, or log files.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Read stdin (hook protocol requires it; SessionStart sends {})
cat > /dev/null

# 1. Run startup check — ingest new files, verify folders, backup DB
#    All output suppressed from stdout (startup_check logs internally)
python3 "$ROOT/scripts/startup_check.py" > /dev/null 2>&1 || true

# 2. Query recent session summaries and output JSON
RESULT=$(python3 - "$ROOT" <<'PYEOF' 2>/dev/null
import json, os, sqlite3, sys, yaml

root = sys.argv[1]
try:
    config = yaml.safe_load(open(os.path.join(root, "config.yaml")))
    db_path = config["storage"]["local_db_path"]
    if not os.path.exists(db_path):
        print(json.dumps({"additionalContext": ""}))
        sys.exit(0)

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=5000;")

    # Get last 5 summaries per project (up to 10 total)
    rows = conn.execute("""
        SELECT project, summary, created_at
        FROM sys_session_summaries
        ORDER BY created_at DESC
        LIMIT 10
    """).fetchall()
    conn.close()

    if not rows:
        print(json.dumps({"additionalContext": ""}))
        sys.exit(0)

    # Group by project
    by_project = {}
    for project, summary, created_at in rows:
        if project not in by_project:
            by_project[project] = []
        by_project[project].append((summary, created_at))

    # Build context text
    lines = ["## Recent Session Context", ""]
    for project, entries in by_project.items():
        lines.append(f"### {project}")
        for summary, created_at in entries[:5]:
            date = created_at[:10] if created_at else "unknown"
            # Extract topic line from summary
            topic = ""
            for sline in (summary or "").split("\n"):
                sline = sline.strip()
                if sline.startswith("Topic:"):
                    topic = sline[6:].strip()
                    break
            if not topic:
                # Fallback: first non-header line
                for sline in (summary or "").split("\n"):
                    sline = sline.strip()
                    if sline and not sline.startswith("Session:") and not sline.startswith("Project:") and not sline.startswith("Time:"):
                        topic = sline[:120]
                        break
            if topic:
                lines.append(f"- [{date}] {topic}")
        lines.append("")

    print(json.dumps({"additionalContext": "\n".join(lines)}))

except Exception:
    print(json.dumps({"additionalContext": ""}))
PYEOF
) || RESULT='{"additionalContext": ""}'

# 3. Output — guaranteed valid JSON
if [ -z "$RESULT" ]; then
    echo '{"additionalContext": ""}'
else
    echo "$RESULT"
fi
