#!/usr/bin/env python3
"""pre-compact.py - Claude Code PreCompact hook for claude-brain.

Fires before context compaction (manual /compact or auto-compact).
Safety net: calls write_exchange.py one final time to ensure all
messages are captured to the DB before compaction wipes context.

stop.py (async) handles normal capture, but there is a small window
where compaction could trigger before the last async stop.py finishes.
This hook closes that gap.

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import glob
import os
import subprocess
import sys


def main():
    # Read stdin (hook protocol requires it)
    sys.stdin.read()

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Determine current session JSONL path from CWD
    cwd = os.getcwd()
    encoded_cwd = cwd.replace("/", "-")
    project_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects", encoded_cwd)

    jsonl_files = glob.glob(os.path.join(project_dir, "*.jsonl"))
    if not jsonl_files:
        print("{}")
        return

    jsonl_path = max(jsonl_files, key=os.path.getmtime)
    session_id = os.path.splitext(os.path.basename(jsonl_path))[0]

    # Call write_exchange.py - dedup is built in, safe to call multiple times
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
