#!/usr/bin/env python3
"""
PreToolUse hook: injects a pre-flight verification checklist before
every Bash, Edit, Write, or NotebookEdit tool call.

The checklist is the condensed version of THE 10 FAILURE MODES from
CLAUDE.md. It fires at the moment of action — the only point where the
reminder is fresh enough to land.

Triggered via ~/.claude/settings.json hooks.PreToolUse entry with
matcher "Bash|Edit|Write|NotebookEdit".

Exit 0 = proceed with the tool call (after the user/agent sees the
injected context). The hook does NOT block tool execution; it injects
context.
"""
import json
import sys

PREFLIGHT = """PRE-FLIGHT — verify before running this tool

1. NEVER ASSUME. Did you verify each cited fact?
   (--help, man, modinfo, sysfs, Exa web_search_exa, brain tools)

2. Real ambiguity in the user's request?
   → STOP and ask, do not run this tool.

3. Did the user explicitly say GO for THIS action?
   "yes" / "ok" / "apply" / "sounds good" are NOT GO.
   Discussion is not authorization. Frustration is not authorization.
   → If no explicit GO for this specific action, STOP. Present plan, wait.

4. Verify END state (e.g., /sys/module/X/parameters/, exportfs -v),
   not intermediate (e.g., /proc/cmdline, cat config).

5. Simplest form. No belt-and-suspenders (e.g., don't edit /etc/default/grub
   on top of `grubby --update-kernel=ALL` — grubby is sufficient).

6. Just got caught on a failure class in this session?
   Check that THIS action isn't repeating the same class.

7. About to output a multi-step plan / doc?
   Mentally trace each step — does the "expected output" you wrote match
   what the command actually produces? Any internal contradictions?

If any of the above is unverified, STOP this tool call. Run the
verification command first. The 30-second check is cheaper than the
5-minute "I should have checked" reply.
"""


def main():
    # Read the tool-call payload from stdin (required by Claude Code hook
    # protocol). We don't actually use it — the checklist is the same for
    # every matching tool call.
    try:
        sys.stdin.read()
    except Exception:
        pass

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": PREFLIGHT,
        }
    }
    print(json.dumps(output))
    sys.exit(0)


if __name__ == "__main__":
    main()
