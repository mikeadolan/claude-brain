#!/usr/bin/env python3
"""
startup_check.py — Session start orchestrator for claude-brain.

Scans for new JSONL files, calls ingest_jsonl.ingest() for each,
verifies required folders, triggers DB backup, prints summary.

Usage:
    python3 startup_check.py

Triggered by: hooks/session-start.sh
Exit codes: 0 = success, 1 = warnings, 2 = fatal error
"""

import datetime
import glob
import logging
import os
import pathlib
import shutil
import socket
import sqlite3
import subprocess
import sys

import yaml

# ---------------------------------------------------------------------------
# Config / Logging / DB — same patterns as ingest_jsonl.py
# ---------------------------------------------------------------------------

def get_root_path():
    return str(pathlib.Path(__file__).resolve().parent.parent)


def load_config(root_path):
    config_path = os.path.join(root_path, "config.yaml")
    if not os.path.exists(config_path):
        raise SystemExit(f"FATAL: config.yaml not found at {config_path}")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    for key_path in [
        ("storage", "local_db_path"),
        ("jsonl", "source_paths"),
    ]:
        obj = config
        for k in key_path:
            if not isinstance(obj, dict) or k not in obj:
                raise SystemExit(f"FATAL: Missing config key: {'.'.join(key_path)}")
            obj = obj[k]
    return config


def setup_logging(root_path):
    hostname = socket.gethostname()
    log_dir = os.path.join(root_path, "logs", hostname)
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "startup_check.log")

    logger = logging.getLogger("startup_check")
    logger.setLevel(logging.DEBUG)

    # Avoid duplicate handlers on repeated calls
    if not logger.handlers:
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                datefmt="%Y-%m-%dT%H:%M:%SZ")
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.INFO)
        fh.setFormatter(fmt)
        logger.addHandler(fh)

        sh = logging.StreamHandler(sys.stderr)
        sh.setLevel(logging.WARNING)
        sh.setFormatter(fmt)
        logger.addHandler(sh)

    return logger


def connect_db(db_path):
    if not os.path.exists(db_path):
        raise SystemExit(f"FATAL: Database not found at {db_path}")
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    return conn


# ---------------------------------------------------------------------------
# Folder verification
# ---------------------------------------------------------------------------

REQUIRED_FOLDERS = [
    "",             # ROOT itself
    "scripts",
    "hooks",
    "mcp",
    "logs",
    "db-backup",
    "verification",
]


def verify_folders(root_path, logger):
    """Check required folders exist. Create missing ones with warning."""
    warnings = 0
    for folder in REQUIRED_FOLDERS:
        full_path = os.path.join(root_path, folder) if folder else root_path
        if not os.path.isdir(full_path):
            logger.warning("Missing folder, creating: %s", full_path)
            os.makedirs(full_path, exist_ok=True)
            warnings += 1
    return warnings


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------

def get_ingested_files(conn):
    """Return set of file_path values already in sys_ingest_log."""
    cur = conn.execute("SELECT file_path FROM sys_ingest_log")
    return {row[0] for row in cur.fetchall()}


def discover_files(source_paths, config, logger):
    """Walk source paths and discover JSONL and tool-result files.

    Returns list of (file_path, expected_type) tuples.
    """
    ingest_subagents = config.get("jsonl", {}).get("ingest_subagents", True)
    ingest_tool_results = config.get("jsonl", {}).get("ingest_tool_results", True)

    discovered = []

    for source_path in source_paths:
        if not os.path.isdir(source_path):
            logger.warning("Source path does not exist: %s", source_path)
            continue

        for dirpath, dirnames, filenames in os.walk(source_path):
            # Skip memory directories
            if "/memory/" in dirpath or dirpath.endswith("/memory"):
                continue

            for filename in filenames:
                full_path = os.path.join(dirpath, filename)

                if filename.endswith(".jsonl"):
                    # Check if subagent
                    if "/subagents/" in full_path or "/subagent/" in full_path:
                        if ingest_subagents:
                            discovered.append((full_path, "subagent"))
                    else:
                        discovered.append((full_path, "jsonl"))

                elif filename.endswith(".txt"):
                    if ingest_tool_results and ("/tool-results/" in full_path or "/tool_results/" in full_path):
                        discovered.append((full_path, "tool_result"))

    return discovered


# ---------------------------------------------------------------------------
# Database backup
# ---------------------------------------------------------------------------

def run_backup(root_path, config, logger):
    """Run database backup with rotation.

    Inline implementation (brain_sync.sh not built yet).
    Rotation: max 2 copies. .bak2 deleted, .bak1 renamed to .bak2, new copy to .bak1.
    """
    db_path = config["storage"]["local_db_path"]
    backup_dir = os.path.join(root_path, "db-backup")
    os.makedirs(backup_dir, exist_ok=True)

    if not os.path.exists(db_path):
        logger.error("Cannot backup: DB not found at %s", db_path)
        return False, 0

    db_name = os.path.basename(db_path)
    bak1 = os.path.join(backup_dir, f"{db_name}.bak1")
    bak2 = os.path.join(backup_dir, f"{db_name}.bak2")

    # Rotate
    if os.path.exists(bak2):
        os.remove(bak2)
    if os.path.exists(bak1):
        os.rename(bak1, bak2)

    # Copy
    shutil.copy2(db_path, bak1)

    # Verify
    backup_size = os.path.getsize(bak1)
    if backup_size == 0:
        logger.error("Backup file is empty: %s", bak1)
        return False, 0

    verify = config.get("backup", {}).get("verify_after_copy", True)
    if verify:
        try:
            conn = sqlite3.connect(bak1)
            result = conn.execute("PRAGMA integrity_check;").fetchone()[0]
            conn.close()
            if result != "ok":
                logger.error("Backup integrity check failed: %s", result)
                return False, backup_size
        except Exception as e:
            logger.error("Backup integrity check error: %s", e)
            return False, backup_size

    logger.info("Backup complete: %s (%d bytes)", bak1, backup_size)
    return True, backup_size


# ---------------------------------------------------------------------------
# Summary gap repair
# ---------------------------------------------------------------------------

def repair_missing_summaries(root_path, db_path, logger):
    """Find sessions with transcripts but no summary and auto-generate them."""
    conn = connect_db(db_path)
    repaired = 0
    try:
        rows = conn.execute("""
            SELECT s.session_id, s.project
            FROM sys_sessions s
            LEFT JOIN sys_session_summaries sm ON s.session_id = sm.session_id
            WHERE sm.session_id IS NULL
              AND (SELECT COUNT(*) FROM transcripts t
                   WHERE t.session_id = s.session_id) > 0
        """).fetchall()
    finally:
        conn.close()

    if not rows:
        return 0

    gen_script = os.path.join(root_path, "scripts", "generate_summary.py")
    for session_id, project in rows:
        try:
            result = subprocess.run(
                [sys.executable, gen_script,
                 "--session-id", session_id, "--project", project],
                capture_output=True, text=True, timeout=30,
            )
            if result.returncode == 0:
                repaired += 1
                logger.info("Repaired missing summary: %s (%s)", session_id[:12], project)
            else:
                logger.warning("Failed to repair summary for %s: %s",
                               session_id[:12], result.stderr.strip())
        except Exception as e:
            logger.warning("Error repairing summary for %s: %s", session_id[:12], e)

    if repaired:
        logger.info("Auto-repaired %d missing summaries", repaired)
    return repaired


# ---------------------------------------------------------------------------
# Main startup check
# ---------------------------------------------------------------------------

def startup_check(root_path=None, config=None):
    """Run the full startup check sequence.

    Returns dict with summary info and exit_code.
    """
    if root_path is None:
        root_path = get_root_path()
    if config is None:
        config = load_config(root_path)

    logger = setup_logging(root_path)
    logger.info("=== Startup check begin ===")

    # Import ingest module
    import importlib.util
    ingest_path = os.path.join(root_path, "scripts", "ingest_jsonl.py")
    spec = importlib.util.spec_from_file_location("ingest_jsonl", ingest_path)
    ingest_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ingest_mod)

    warnings = 0
    errors = 0

    # 1. Verify folders
    folder_warnings = verify_folders(root_path, logger)
    warnings += folder_warnings

    # 2. Connect to DB
    db_path = config["storage"]["local_db_path"]
    try:
        conn = connect_db(db_path)
    except SystemExit as e:
        logger.error(str(e))
        return {"source_paths_scanned": 0, "new_files": 0,
                "records_ingested": 0, "errors": 1,
                "backup_ok": False, "backup_size": 0,
                "exit_code": 2}

    try:
        # 3. Get already-ingested files
        ingested = get_ingested_files(conn)

        # 4. Discover files from source paths
        source_paths = config["jsonl"]["source_paths"]
        all_discovered = discover_files(source_paths, config, logger)

        # 5. Filter to new files only
        new_files = [(fp, ft) for fp, ft in all_discovered
                     if os.path.abspath(fp) not in ingested]

        # 6. Ingest new files
        total_imported = 0
        ingest_errors = 0
        for file_path, file_type in new_files:
            result = ingest_mod.ingest(
                file_path, type_override=file_type,
                config=config, root_path=root_path
            )
            total_imported += result["records_imported"]
            if result["exit_code"] != 0:
                ingest_errors += 1
                errors += 1

    finally:
        conn.close()

    # 7. Run backup
    backup_ok, backup_size = run_backup(root_path, config, logger)
    if not backup_ok:
        warnings += 1

    # 8. Auto-repair missing summaries
    summaries_repaired = repair_missing_summaries(root_path, db_path, logger)

    # 9. Determine exit code
    if errors > 0:
        exit_code = 1
    else:
        exit_code = 0

    logger.info("=== Startup check complete: %d new files, %d records, %d errors ===",
                len(new_files), total_imported, errors)

    return {
        "source_paths_scanned": len(source_paths),
        "new_files": len(new_files),
        "records_ingested": total_imported,
        "errors": errors,
        "backup_ok": backup_ok,
        "backup_size": backup_size,
        "summaries_repaired": summaries_repaired,
        "exit_code": exit_code,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    result = startup_check()

    backup_status = f"OK ({result['backup_size']} bytes)" if result["backup_ok"] else "FAILED"

    print("=== Claude Brain Startup Check ===")
    print(f"Source paths scanned: {result['source_paths_scanned']}")
    print(f"New files found: {result['new_files']}")
    print(f"Records ingested: {result['records_ingested']}")
    print(f"Errors: {result['errors']}")
    print(f"Backup: {backup_status}")
    if result.get("summaries_repaired", 0) > 0:
        print(f"Summaries repaired: {result['summaries_repaired']}")
    print("===================================")

    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
