#!/usr/bin/env python3
"""session-end.py — Claude Code SessionEnd hook for claude-brain.

Fires when session ends (/exit or terminal close).
1. Runs brain_sync.py to backup the database (detached)
2. Returns {} (session is ending, no context needed)

NOTE: May not fire on terminal close. Data integrity guaranteed
by stop.py having captured all exchanges already.

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import os
import subprocess
import sys


def main():
    # Read stdin (hook protocol requires it)
    sys.stdin.read()

    # Determine ROOT (parent of hooks/)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Run database backup (detached — hook must return immediately)
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
