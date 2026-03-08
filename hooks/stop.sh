#!/usr/bin/env bash
# stop.sh — Claude Code Stop hook for claude-brain.
#
# Fires after every Claude response completes.
# 1. Determines current session ID and JSONL path
# 2. Calls write_exchange.py to capture new messages to DB
# 3. Returns {} (no additional context needed)
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

if [ -z "$JSONL_PATH" ]; then
    echo '{}'
    exit 0
fi

SESSION_ID=$(basename "$JSONL_PATH" .jsonl)

# Call write_exchange.py (all output to stderr/log, not stdout)
python3 "$ROOT/scripts/write_exchange.py" \
    --session-id "$SESSION_ID" \
    --jsonl-path "$JSONL_PATH" \
    > /dev/null 2>&1 || true

echo '{}'
