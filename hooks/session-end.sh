#!/usr/bin/env bash
# session-end.sh — Claude Code SessionEnd hook for claude-brain.
#
# Fires when session ends (/exit or terminal close).
# 1. Determines current session ID and project
# 2. Calls generate_summary.py to create session summary
# 3. Calls brain_sync.sh to backup the database
# 4. Returns {} (session is ending, no context needed)
#
# NOTE: May not fire on terminal close. Data integrity guaranteed
# by stop.sh having captured all exchanges already.
#
# RULE: stdout is SACRED. Only valid JSON goes to stdout.

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Read stdin (hook protocol requires it)
cat > /dev/null

# Determine current session JSONL path from CWD
CWD="$(pwd)"
ENCODED_CWD=$(echo "$CWD" | sed 's|^/|-|; s|/|-|g')
PROJECT_DIR="$HOME/.claude/projects/$ENCODED_CWD"

# Find most recently modified JSONL = current session
JSONL_PATH=$(ls -t "$PROJECT_DIR"/*.jsonl 2>/dev/null | head -1)

if [ -n "$JSONL_PATH" ]; then
    SESSION_ID=$(basename "$JSONL_PATH" .jsonl)

    # Detect project prefix
    PROJECT=$(python3 -c "
import yaml, os
config = yaml.safe_load(open('$ROOT/config.yaml'))
mappings = config.get('jsonl_project_mapping', {})
cwd = '$CWD'
for pattern, prefix in sorted(mappings.items(), key=lambda x: len(x[0]), reverse=True):
    if pattern in cwd:
        print(prefix)
        exit()
print('oth')
" 2>/dev/null) || PROJECT="oth"

    # 1. Generate session summary (all output to stderr/log)
    python3 "$ROOT/scripts/generate_summary.py" \
        --session-id "$SESSION_ID" \
        --project "$PROJECT" \
        > /dev/null 2>&1 || true

    # 2. Run database backup (all output to stderr/log)
    bash "$ROOT/scripts/brain_sync.sh" \
        > /dev/null 2>&1 || true
fi

echo '{}'
