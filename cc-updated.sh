cat > ~/bin/cc << 'SCRIPT'
#!/bin/bash

# Claude Code launcher with auto-session logging + live token monitor
# Logs saved to: ~/Dropbox/Documents/AI/Claude/claude-brain/chat-logs/
# Token usage shown in terminal title bar (updates every 10 seconds)

LOGDIR="$HOME/Dropbox/Documents/AI/Claude/claude-brain/chat-logs"
PROJECT="$(basename "$PWD")"
mkdir -p "$LOGDIR/$PROJECT"

# ---------------------------------------------------------------------------
# Token monitor — live token usage in terminal title + desktop notifications
#
# Reads Claude Code debug log (effectiveWindow is dynamic — works for both
# 200K Max and 1M Bedrock automatically). Zero API tokens.
#
# Warning zones:
#   Normal  (< 70%)  — title shows usage quietly
#   Warm    (70-80%)  — title adds ⚠, ONE yellow desktop popup
#   Hot     (80-90%)  — title adds 🔴, red popup every 60s
#   Critical(> 90% or free < 30K) — title shows END SESSION, red popup every 60s
#
# End-session reserve: ~25K tokens needed for notes + summary + governance + git
# ---------------------------------------------------------------------------
END_SESSION_RESERVE=30000
WARNED_70=0
WARNED_80=0
LAST_CRITICAL_NOTIFY=0

monitor_tokens() {
    sleep 5  # wait for Claude Code to start and create debug file
    while true; do
        DEBUGFILE=$(ls -t ~/.claude/debug/*.txt 2>/dev/null | head -1)
        if [ -n "$DEBUGFILE" ]; then
            LINE=$(grep "autocompact:" "$DEBUGFILE" | tail -1)
            if [ -n "$LINE" ]; then
                TOKENS=$(echo "$LINE" | grep -oP 'tokens=\K[0-9]+')
                WINDOW=$(echo "$LINE" | grep -oP 'effectiveWindow=\K[0-9]+')
                THRESHOLD=$(echo "$LINE" | grep -oP 'threshold=\K[0-9]+')
                if [ -n "$TOKENS" ] && [ -n "$WINDOW" ]; then
                    # Autocompact buffer = window - threshold
                    BUFFER=$((WINDOW - THRESHOLD))
                    USABLE=$((WINDOW - BUFFER))
                    if [ "$USABLE" -le 0 ]; then
                        USABLE=$WINDOW
                    fi
                    FREE=$((USABLE - TOKENS))
                    if [ "$FREE" -lt 0 ]; then
                        FREE=0
                    fi
                    PCT=$((TOKENS * 100 / USABLE))
                    TOKENS_K=$((TOKENS / 1000))
                    USABLE_K=$((USABLE / 1000))
                    FREE_K=$((FREE / 1000))
                    NOW=$(date +%s)

                    # ── Critical: > 90% OR free < end-session reserve ──
                    if [ "$PCT" -ge 90 ] || [ "$FREE" -lt "$END_SESSION_RESERVE" ]; then
                        printf '\033]0;🔴 END SESSION NOW — %dK free — %s\007' \
                            "$FREE_K" "$PROJECT"
                        # Red popup every 60 seconds
                        if [ "$((NOW - LAST_CRITICAL_NOTIFY))" -ge 60 ]; then
                            notify-send --urgency=critical \
                                "🔴 END SESSION NOW" \
                                "Only ${FREE_K}K tokens free (${PCT}% used)\nYou need ~30K for end-session protocol\nSay 'end session' NOW" \
                                2>/dev/null
                            LAST_CRITICAL_NOTIFY=$NOW
                        fi

                    # ── Hot: 80-90% ──
                    elif [ "$PCT" -ge 80 ]; then
                        printf '\033]0;🔴 %s — %dK / %dK (%d%%) — %dK free — END SOON\007' \
                            "$PROJECT" "$TOKENS_K" "$USABLE_K" "$PCT" "$FREE_K"
                        if [ "$WARNED_80" -eq 0 ]; then
                            notify-send --urgency=critical \
                                "🔴 Token Warning — 80%" \
                                "${TOKENS_K}K / ${USABLE_K}K used (${PCT}%)\n${FREE_K}K remaining\nStart wrapping up — say 'end session' soon" \
                                2>/dev/null
                            WARNED_80=1
                        fi

                    # ── Warm: 70-80% ──
                    elif [ "$PCT" -ge 70 ]; then
                        printf '\033]0;⚠ %s — %dK / %dK (%d%%) — %dK free\007' \
                            "$PROJECT" "$TOKENS_K" "$USABLE_K" "$PCT" "$FREE_K"
                        if [ "$WARNED_70" -eq 0 ]; then
                            notify-send --urgency=normal \
                                "⚠ Token Usage — 70%" \
                                "${TOKENS_K}K / ${USABLE_K}K used (${PCT}%)\n${FREE_K}K remaining\nPlenty of room, but be aware" \
                                2>/dev/null
                            WARNED_70=1
                        fi

                    # ── Normal: < 70% ──
                    else
                        printf '\033]0;%s — %dK / %dK (%d%%) — %dK free\007' \
                            "$PROJECT" "$TOKENS_K" "$USABLE_K" "$PCT" "$FREE_K"
                    fi
                fi
            fi
        fi
        sleep 10
    done
}

echo ""
echo "  Claude Code mode?"
echo ""
echo "  1) Subscription (Pro Max)"
echo "  2) OpenRouter (1M Context Unsupported)"
echo "  3) Amazon Bedrock (1M Context Supported)"
echo ""
read -p "  Enter 1, 2, or 3: " MODE_CHOICE

case $MODE_CHOICE in
    1)
        LOGFILE="$LOGDIR/$PROJECT/$(date +%Y%m%d-%H%M%S)-max.txt"
        echo ""
        echo "  Starting Claude Code (Subscription + High Thinking)..."
        echo "  Session log: $LOGFILE"
        echo "  Token usage: watch your terminal title bar"
        echo ""
        monitor_tokens &
        MONITOR_PID=$!
        script -f -q "$LOGFILE" -c 'CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000 \
        CLAUDE_CODE_EFFORT_LEVEL="high" \
        MAX_THINKING_TOKENS=31999 \
        command claude --debug --dangerously-skip-permissions'
        kill $MONITOR_PID 2>/dev/null
        printf '\033]0;\007'
        echo ""
        echo "  Session saved to: $LOGFILE"
        ;;
    2)
        LOGFILE="$LOGDIR/$PROJECT/$(date +%Y%m%d-%H%M%S)-openrouter.txt"
        echo ""
        echo "  Starting Claude Code (OpenRouter + High Thinking)..."
        echo "  Session log: $LOGFILE"
        echo "  Token usage: watch your terminal title bar"
        echo ""
        monitor_tokens &
        MONITOR_PID=$!
        script -f -q "$LOGFILE" -c 'CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000 \
        ANTHROPIC_BASE_URL="https://openrouter.ai/api" \
        ANTHROPIC_AUTH_TOKEN="MY-KEY" \
        ANTHROPIC_API_KEY="" \
        ANTHROPIC_MODEL="anthropic/claude-opus-4.6" \
        ANTHROPIC_SMALL_FAST_MODEL="anthropic/claude-opus-4.6" \
        CLAUDE_CODE_SUBAGENT_MODEL="anthropic/claude-opus-4.6" \
        CLAUDE_CODE_EFFORT_LEVEL="high" \
        MAX_THINKING_TOKENS=31999 \
        CLAUDE_CODE_USE_PPROMPT=0 \
        OPENROUTER_HEADERS='"'"'{"extra_body": {"cache_control": {"type": "ephemeral", "ttl": "1h"}}}'"'"' \
        command claude --debug --dangerously-skip-permissions'
        kill $MONITOR_PID 2>/dev/null
        printf '\033]0;\007'
        echo ""
        echo "  Session saved to: $LOGFILE"
        ;;
    3)
        LOGFILE="$LOGDIR/$PROJECT/$(date +%Y%m%d-%H%M%S)-bedrock.txt"
        echo ""
        echo "  Starting Claude Code (Amazon Bedrock)..."
        echo "  Session log: $LOGFILE"
        echo "  Token usage: watch your terminal title bar"
        echo ""
        monitor_tokens &
        MONITOR_PID=$!
        script -f -q "$LOGFILE" -c 'CLAUDE_CODE_USE_BEDROCK=1 \
        AWS_REGION="us-east-1" \
        ANTHROPIC_MODEL="us.anthropic.claude-opus-4-6-v1[1m]" \
        ANTHROPIC_SMALL_FAST_MODEL="us.anthropic.claude-opus-4-6-v1[1m]" \
        CLAUDE_CODE_SUBAGENT_MODEL="us.anthropic.claude-opus-4-6-v1[1m]" \
        CLAUDE_CODE_MAX_OUTPUT_TOKENS=64000 \
        CLAUDE_CODE_EFFORT_LEVEL="high" \
        MAX_THINKING_TOKENS=31999 \
        command claude --debug --dangerously-skip-permissions'
        kill $MONITOR_PID 2>/dev/null
        printf '\033]0;\007'
        echo ""
        echo "  Session saved to: $LOGFILE"
        ;;
    *)
        echo "Invalid choice."
        ;;
esac
SCRIPT
