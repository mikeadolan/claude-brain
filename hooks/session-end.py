#!/usr/bin/env python3
"""session-end.py — Claude Code SessionEnd hook for claude-brain.

Fires when session ends (/exit or terminal close).
1. Determines current session ID and project
2. Calls generate_summary.py to create session summary
3. Calls brain_sync.py to backup the database
4. Returns {} (session is ending, no context needed)

NOTE: May not fire on terminal close. Data integrity guaranteed
by stop.py having captured all exchanges already.

RULE: stdout is SACRED. Only valid JSON goes to stdout.
"""

import glob
import os
import subprocess
import sys

import yaml


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

    # Detect project prefix from CWD using config mapping
    project = "oth"
    try:
        config_path = os.path.join(root, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        mappings = config.get("jsonl_project_mapping", {})
        for pattern, prefix in sorted(mappings.items(), key=lambda x: len(x[0]), reverse=True):
            if pattern in cwd:
                project = prefix
                break
    except Exception:
        pass

    # 1. Generate session summary
    # stdout/stderr suppressed — hook stdout is SACRED (JSON only)
    try:
        subprocess.run(
            [sys.executable, os.path.join(root, "scripts", "generate_summary.py"),
             "--session-id", session_id,
             "--project", project],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    # 2. Run database backup
    try:
        subprocess.run(
            [sys.executable, os.path.join(root, "scripts", "brain_sync.py")],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass

    print("{}")


if __name__ == "__main__":
    main()
