#!/usr/bin/env python3
"""stop.py - Claude Code Stop hook for claude-brain.

Fires after every Claude response completes.
1. Determines current session ID and JSONL path
2. Calls write_exchange.py to capture new messages to DB
3. If backup is older than 12 hours, triggers brain_sync.py (detached)
4. Returns {} (no additional context needed)

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import glob
import json
import os
import subprocess
import sys
import time

_BACKUP_MAX_AGE = 12 * 3600  # 12 hours in seconds


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

    # Call write_exchange.py - stdout/stderr suppressed (hook stdout is SACRED)
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

    # Auto-backup if last backup is older than 12 hours
    try:
        backup_path = os.path.join(root, "db-backup", "claude-brain.db.bak1")
        run_backup = False
        if not os.path.exists(backup_path):
            run_backup = True
        else:
            age = time.time() - os.path.getmtime(backup_path)
            if age > _BACKUP_MAX_AGE:
                run_backup = True

        if run_backup:
            subprocess.Popen(
                [sys.executable, os.path.join(root, "scripts", "brain_sync.py")],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
    except Exception:
        pass

    print("{}")


if __name__ == "__main__":
    main()
