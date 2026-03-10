#!/usr/bin/env python3
"""stop.py — Claude Code Stop hook for claude-brain.

Fires after every Claude response completes.
1. Determines current session ID and JSONL path
2. Calls write_exchange.py to capture new messages to DB
3. Returns {} (no additional context needed)

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import glob
import json
import os
import subprocess
import sys


def main():
    # Read stdin (hook protocol requires it)
    sys.stdin.read()

    # Determine ROOT (parent of hooks/)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Determine current session JSONL path from CWD
    cwd = os.getcwd()
    encoded_cwd = cwd.replace("/", "-")
    project_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects", encoded_cwd)

    # Find most recently modified JSONL = current session
    jsonl_files = glob.glob(os.path.join(project_dir, "*.jsonl"))
    if not jsonl_files:
        print("{}")
        return

    jsonl_path = max(jsonl_files, key=os.path.getmtime)
    session_id = os.path.splitext(os.path.basename(jsonl_path))[0]

    # Call write_exchange.py — stdout/stderr suppressed (hook stdout is SACRED)
    try:
        subprocess.run(
            [sys.executable, os.path.join(root, "scripts", "write_exchange.py"),
             "--session-id", session_id,
             "--jsonl-path", jsonl_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    print("{}")


if __name__ == "__main__":
    main()
