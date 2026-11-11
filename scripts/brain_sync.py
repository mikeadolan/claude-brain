#!/usr/bin/env python3
"""brain_sync.py - Rotating backup of SQLite database for claude-brain.

Rotation: max 2 copies. .bak2 deleted, .bak1 renamed to .bak2, new copy to .bak1.
Verifies backup with sqlite3 integrity_check.

If backup.offsite.enabled is set, the verified .bak1 is also copied to the
off-site path (NAS, network share, cloud folder) with its own rotation plus
dated snapshots. An unreachable off-site target never fails the local backup.

Usage:  python3 brain_sync.py
Exit codes: 0 = success, 1 = failure
"""

import glob
import os
import shutil
import socket
import sqlite3
import sys
from datetime import datetime, timezone

import yaml


def _offsite_backup(bak1, db_name, offsite_cfg, log):
    """Copy the verified local backup to the off-site target.

    Rotation on the target: <db>.bak2 removed, <db>.bak1 -> .bak2, fresh copy
    to .bak1. One dated snapshot per day (<stem>-YYYY-MM-DD.db), pruned to
    backup.offsite.keep_dated entries.

    Returns (ok, message). Never raises: local backup already succeeded.
    """
    raw_path = str(offsite_cfg.get("path", "") or "").strip()
    if not raw_path:
        return False, "backup.offsite.path is empty"

    offsite_dir = os.path.expandvars(os.path.expanduser(raw_path))
    try:
        keep_dated = int(offsite_cfg.get("keep_dated", 7))
    except (TypeError, ValueError):
        keep_dated = 7

    try:
        os.makedirs(offsite_dir, exist_ok=True)

        off_bak1 = os.path.join(offsite_dir, f"{db_name}.bak1")
        off_bak2 = os.path.join(offsite_dir, f"{db_name}.bak2")
        if os.path.isfile(off_bak2):
            os.remove(off_bak2)
        if os.path.isfile(off_bak1):
            os.rename(off_bak1, off_bak2)
        shutil.copy2(bak1, off_bak1)

        if os.path.getsize(off_bak1) != os.path.getsize(bak1):
            return False, f"size mismatch after copy to {off_bak1}"

        # Dated snapshot: at most one per day, keeps history beyond bak1/bak2.
        stem, ext = os.path.splitext(db_name)
        snapshot = os.path.join(offsite_dir, f"{stem}-{datetime.now().strftime('%Y-%m-%d')}{ext}")
        if not os.path.isfile(snapshot):
            shutil.copy2(bak1, snapshot)

        dated = sorted(
            glob.glob(os.path.join(offsite_dir, f"{stem}-*{ext}")),
            key=os.path.getmtime,
            reverse=True,
        )
        if keep_dated < 0:
            keep_dated = 0
        for old in dated[keep_dated:]:
            os.remove(old)

        return True, f"{off_bak1} ({os.path.getsize(off_bak1)} bytes), {min(len(dated), keep_dated)} dated snapshots"
    except OSError as e:
        return False, str(e)


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

    with open(config_file, encoding="utf-8") as f:
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

    # Off-site copy runs only after the local backup is verified and is never fatal
    offsite_cfg = (config.get("backup") or {}).get("offsite") or {}
    if offsite_cfg.get("enabled"):
        offsite_ok, offsite_msg = _offsite_backup(bak1, db_name, offsite_cfg, log)
        if offsite_ok:
            log("INFO", f"Offsite backup complete: {offsite_msg}")
            print(f"Offsite backup complete: {offsite_msg}")
        else:
            log("WARN", f"Offsite backup failed: {offsite_msg}")
            print(f"Warning: Offsite backup failed: {offsite_msg}", file=sys.stderr)


if __name__ == "__main__":
    main()
