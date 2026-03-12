#!/usr/bin/env python3
"""brain_sync.py - Rotating backup of SQLite database for claude-brain.

Rotation: max 2 copies. .bak2 deleted, .bak1 renamed to .bak2, new copy to .bak1.
Verifies backup with sqlite3 integrity_check.

Usage:  python3 brain_sync.py
Exit codes: 0 = success, 1 = failure
"""

import os
import shutil
import socket
import sqlite3
import sys
from datetime import datetime, timezone

import yaml


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hostname = socket.gethostname()
    log_dir = os.path.join(root, "logs", hostname)
    log_file = os.path.join(log_dir, "brain_sync.log")

    # Source: read DB path from config.yaml
    config_file = os.path.join(root, "config.yaml")
    if not os.path.isfile(config_file):
        print(f"Error: config.yaml not found at {config_file}", file=sys.stderr)
        sys.exit(1)

    with open(config_file) as f:
        config = yaml.safe_load(f)

    storage = config.get("storage", {})
    mode = storage.get("mode", "local")
    if mode == "synced":
        db_source = storage["local_db_path"]
    else:
        db_source = os.path.join(storage["root_path"], "claude-brain.db")

    backup_dir = os.path.join(root, "db-backup")
    db_name = os.path.basename(db_source)
    bak1 = os.path.join(backup_dir, f"{db_name}.bak1")
    bak2 = os.path.join(backup_dir, f"{db_name}.bak2")

    # Ensure directories exist
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(backup_dir, exist_ok=True)

    def log(level, msg):
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = f"{ts} [{level}] {msg}"
        try:
            with open(log_file, "a") as lf:
                lf.write(line + "\n")
        except Exception:
            pass
        if level == "ERROR":
            print(line, file=sys.stderr)

    # Check source exists
    if not os.path.isfile(db_source):
        log("ERROR", f"Source database not found: {db_source}")
        print(f"Error: Source database not found: {db_source}", file=sys.stderr)
        sys.exit(1)

    # Rotate backups
    if os.path.isfile(bak2):
        os.remove(bak2)
    if os.path.isfile(bak1):
        os.rename(bak1, bak2)

    # Copy (preserves metadata like cp -p)
    shutil.copy2(db_source, bak1)

    # Verify size > 0
    backup_size = os.path.getsize(bak1)
    if backup_size == 0:
        log("ERROR", f"Backup file is empty: {bak1}")
        print("Error: Backup file is empty", file=sys.stderr)
        sys.exit(1)

    # Verify integrity via Python sqlite3
    try:
        conn = sqlite3.connect(bak1)
        integrity = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        conn.close()
    except Exception as e:
        log("ERROR", f"Integrity check failed: {e}")
        print("Error: Integrity check failed", file=sys.stderr)
        sys.exit(1)

    if integrity != "ok":
        log("ERROR", f"Integrity check failed: {integrity}")
        print("Error: Integrity check failed", file=sys.stderr)
        sys.exit(1)

    log("INFO", "Integrity check passed")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    log("INFO", f"Backup complete: {bak1} ({backup_size} bytes) at {timestamp}")

    # Output to stdout
    print(f"Backup complete: {bak1} ({backup_size} bytes) at {timestamp}")


if __name__ == "__main__":
    main()
