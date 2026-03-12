#!/usr/bin/env python3
"""
brain_health.py — 9-point health check for claude-brain.

Performs a comprehensive diagnostic of the brain system and outputs
a clear terminal report with PASS/WARN/FAIL indicators. Diagnosis only — no fixes.

Usage:
    python3 brain_health.py [--json]

Exit codes: 0 = all PASS, 1 = any WARN, 2 = any FAIL
"""

import argparse
import json
import os
import pathlib
import sqlite3
import sys
import time

import yaml

# ---------------------------------------------------------------------------
# Config / DB
# ---------------------------------------------------------------------------

SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
ROOT_PATH = str(SCRIPT_DIR.parent)


def load_config():
    config_path = os.path.join(ROOT_PATH, "config.yaml")
    if not os.path.exists(config_path):
        return None
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def connect_db(db_path):
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Check functions — each returns (status, summary_line, details_dict)
# status: "PASS", "WARN", "FAIL"
# ---------------------------------------------------------------------------

def check_database(config):
    """1. DATABASE — file size, integrity_check, WAL status, freelist_count."""
    db_path = config["storage"]["local_db_path"]
    details = {"db_path": db_path}

    if not os.path.exists(db_path):
        return "FAIL", "Database file not found", details

    size_bytes = os.path.getsize(db_path)
    size_mb = round(size_bytes / (1024 * 1024), 1)
    details["size_mb"] = size_mb

    try:
        conn = sqlite3.connect(db_path)
        # Integrity check
        result = conn.execute("PRAGMA integrity_check;").fetchone()[0]
        integrity_ok = result == "ok"
        details["integrity"] = result

        # WAL status
        journal = conn.execute("PRAGMA journal_mode;").fetchone()[0]
        details["journal_mode"] = journal

        # Freelist (fragmentation)
        freelist = conn.execute("PRAGMA freelist_count;").fetchone()[0]
        page_count = conn.execute("PRAGMA page_count;").fetchone()[0]
        frag_pct = round((freelist / page_count) * 100, 1) if page_count > 0 else 0
        details["freelist_count"] = freelist
        details["fragmentation_pct"] = frag_pct

        conn.close()
    except Exception as e:
        return "FAIL", f"Database error: {e}", details

    if not integrity_ok:
        return "FAIL", f"Database: {size_mb} MB, INTEGRITY FAILED", details

    wal_status = "WAL" if journal == "wal" else journal.upper()
    summary = f"Database: {size_mb} MB, integrity OK, {wal_status}, {frag_pct}% fragmentation"
    return "PASS", summary, details


def check_space(config):
    """2. SPACE BREAKDOWN — size of raw_json, content, embeddings, tool_results."""
    db_path = config["storage"]["local_db_path"]
    details = {}

    if not os.path.exists(db_path):
        return "FAIL", "Database not found", details

    try:
        conn = sqlite3.connect(db_path)
        total_bytes = os.path.getsize(db_path)

        # raw_json column size
        row = conn.execute("SELECT COALESCE(SUM(LENGTH(raw_json)), 0) FROM transcripts").fetchone()
        raw_json_bytes = row[0]

        # content column size
        row = conn.execute("SELECT COALESCE(SUM(LENGTH(content)), 0) FROM transcripts").fetchone()
        content_bytes = row[0]

        # embeddings size
        emb_bytes = 0
        try:
            row = conn.execute("SELECT COALESCE(SUM(LENGTH(embedding)), 0) FROM transcript_embeddings").fetchone()
            emb_bytes = row[0]
        except Exception:
            pass

        # tool_results content size
        tr_bytes = 0
        try:
            row = conn.execute("SELECT COALESCE(SUM(LENGTH(content)), 0) FROM tool_results").fetchone()
            tr_bytes = row[0]
        except Exception:
            pass

        conn.close()

        def fmt(b):
            mb = round(b / (1024 * 1024), 1)
            pct = round((b / total_bytes) * 100) if total_bytes > 0 else 0
            return mb, pct

        rj_mb, rj_pct = fmt(raw_json_bytes)
        ct_mb, ct_pct = fmt(content_bytes)
        em_mb, em_pct = fmt(emb_bytes)
        tr_mb, tr_pct = fmt(tr_bytes)

        details = {
            "raw_json_mb": rj_mb, "raw_json_pct": rj_pct,
            "content_mb": ct_mb, "content_pct": ct_pct,
            "embeddings_mb": em_mb, "embeddings_pct": em_pct,
            "tool_results_mb": tr_mb, "tool_results_pct": tr_pct,
        }

        summary = (
            f"Space: raw_json {rj_mb} MB ({rj_pct}%), content {ct_mb} MB ({ct_pct}%), "
            f"embeddings {em_mb} MB ({em_pct}%), tool_results {tr_mb} MB ({tr_pct}%)"
        )
        return "PASS", summary, details

    except Exception as e:
        return "FAIL", f"Space check error: {e}", details


def check_data_health(config):
    """3. DATA HEALTH — FTS5 sync, embedding coverage, summary coverage."""
    db_path = config["storage"]["local_db_path"]
    details = {}

    if not os.path.exists(db_path):
        return "FAIL", "Database not found", details

    try:
        conn = sqlite3.connect(db_path)
        status = "PASS"
        issues = []

        # FTS5 row count vs transcripts
        transcript_count = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        fts_count = conn.execute("SELECT COUNT(*) FROM transcripts_fts").fetchone()[0]
        details["transcript_count"] = transcript_count
        details["fts_count"] = fts_count
        fts_synced = transcript_count == fts_count
        details["fts_synced"] = fts_synced

        if not fts_synced:
            status = "FAIL"
            issues.append(f"FTS5 OUT OF SYNC ({fts_count} vs {transcript_count})")
        else:
            issues.append(f"FTS5 synced ({transcript_count})")

        # Embedding coverage — count content messages with 50+ chars
        content_msgs = conn.execute(
            "SELECT COUNT(*) FROM transcripts WHERE LENGTH(content) >= 50"
        ).fetchone()[0]
        emb_count = 0
        try:
            emb_count = conn.execute("SELECT COUNT(*) FROM transcript_embeddings").fetchone()[0]
        except Exception:
            pass
        details["content_msgs_50plus"] = content_msgs
        details["embedding_count"] = emb_count
        emb_pct = round((emb_count / content_msgs) * 100) if content_msgs > 0 else 0
        details["embedding_pct"] = emb_pct

        if emb_pct < 80:
            if status == "PASS":
                status = "WARN"
            issues.append(f"embeddings {emb_pct}% ({emb_count}/{content_msgs})")
        else:
            issues.append(f"embeddings {emb_pct}% ({emb_count}/{content_msgs})")

        # Notes coverage (sys_sessions.notes is the single source of truth)
        session_count = conn.execute("SELECT COUNT(*) FROM sys_sessions").fetchone()[0]
        notes_count = conn.execute(
            "SELECT COUNT(*) FROM sys_sessions WHERE notes IS NOT NULL AND notes != ''"
        ).fetchone()[0]
        details["session_count"] = session_count
        details["notes_count"] = notes_count
        notes_pct = round((notes_count / session_count) * 100) if session_count > 0 else 0
        details["notes_pct"] = notes_pct

        if notes_pct < 80:
            if status == "PASS":
                status = "WARN"
            issues.append(f"notes {notes_pct}% ({notes_count}/{session_count})")
        else:
            issues.append(f"notes {notes_pct}% ({notes_count}/{session_count})")

        conn.close()
        summary = f"Data: {', '.join(issues)}"
        return status, summary, details

    except Exception as e:
        return "FAIL", f"Data health error: {e}", details


def check_backup(config):
    """4. BACKUP — exists? age? integrity? row count delta vs main DB?"""
    backup_dir = os.path.join(ROOT_PATH, "db-backup")
    details = {"backup_dir": backup_dir}

    if not os.path.isdir(backup_dir):
        return "FAIL", "Backup directory not found", details

    bak_files = sorted(
        [f for f in os.listdir(backup_dir) if f.endswith(('.bak1', '.bak2', '.bak3'))],
        key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)),
        reverse=True,
    )

    if not bak_files:
        return "FAIL", "Backup: no backup files found", details

    details["backup_count"] = len(bak_files)
    newest = os.path.join(backup_dir, bak_files[0])
    mtime = os.path.getmtime(newest)
    age_hours = round((time.time() - mtime) / 3600, 1)
    details["newest_age_hours"] = age_hours
    details["newest_file"] = bak_files[0]

    status = "PASS"
    issues = []

    # Check integrity of newest backup
    try:
        bak_conn = sqlite3.connect(newest)
        result = bak_conn.execute("PRAGMA integrity_check;").fetchone()[0]
        bak_integrity = result == "ok"
        details["backup_integrity"] = result

        # Row count delta vs main DB
        bak_count = bak_conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        bak_conn.close()

        db_path = config["storage"]["local_db_path"]
        if os.path.exists(db_path):
            main_conn = sqlite3.connect(db_path)
            main_count = main_conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
            main_conn.close()
            delta = main_count - bak_count
            details["row_delta"] = delta
            if delta > 0:
                issues.append(f"main has {delta} newer rows")
        else:
            details["row_delta"] = "unknown"

        if not bak_integrity:
            status = "FAIL"
            issues.append("INTEGRITY FAILED")

    except Exception as e:
        status = "FAIL"
        issues.append(f"integrity check error: {e}")

    if age_hours > 24:
        if status == "PASS":
            status = "WARN"
        age_str = f"{age_hours}h old"
    elif age_hours >= 1:
        age_str = f"{age_hours}h old"
    else:
        minutes = round(age_hours * 60)
        age_str = f"{minutes}m old"

    parts = [f"{len(bak_files)} copies", f"newest {age_str}"]
    if bak_integrity:
        parts.append("integrity OK")
    parts.extend(issues)
    summary = f"Backup: {', '.join(parts)}"
    return status, summary, details


def check_performance(config):
    """5. PERFORMANCE — timed FTS5 query, timed LIKE query, timed COUNT(*)."""
    db_path = config["storage"]["local_db_path"]
    details = {}

    if not os.path.exists(db_path):
        return "FAIL", "Database not found", details

    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL;")

        # Timed FTS5 query
        t0 = time.perf_counter()
        conn.execute("SELECT COUNT(*) FROM transcripts_fts WHERE transcripts_fts MATCH 'test'").fetchone()
        fts_ms = round((time.perf_counter() - t0) * 1000, 1)
        details["fts5_ms"] = fts_ms

        # Timed LIKE query
        t0 = time.perf_counter()
        conn.execute("SELECT COUNT(*) FROM transcripts WHERE content LIKE '%test%'").fetchone()
        like_ms = round((time.perf_counter() - t0) * 1000, 1)
        details["like_ms"] = like_ms

        # Timed COUNT(*)
        t0 = time.perf_counter()
        conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()
        count_ms = round((time.perf_counter() - t0) * 1000, 1)
        details["count_ms"] = count_ms

        conn.close()

        summary = f"Performance: FTS5 {fts_ms}ms, LIKE {like_ms}ms, COUNT(*) {count_ms}ms"
        return "PASS", summary, details

    except Exception as e:
        return "FAIL", f"Performance check error: {e}", details


def check_dependencies():
    """6. DEPENDENCIES — check: yaml, sqlite3, sentence_transformers, numpy importable?"""
    packages = {
        "yaml": "PyYAML",
        "sqlite3": "sqlite3",
        "sentence_transformers": "sentence-transformers",
        "numpy": "numpy",
    }
    details = {}
    missing = []

    for module, label in packages.items():
        try:
            __import__(module)
            details[label] = "ok"
        except ImportError:
            details[label] = "MISSING"
            missing.append(label)

    if missing:
        return "FAIL", f"Dependencies: MISSING {', '.join(missing)}", details

    summary = f"Dependencies: all {len(packages)} packages importable"
    return "PASS", summary, details


def check_mcp_server(config):
    """7. MCP SERVER — check ~/.claude.json for brain-server registration; verify server.py exists."""
    details = {}
    claude_json_path = os.path.expanduser("~/.claude.json")

    if not os.path.exists(claude_json_path):
        return "FAIL", "MCP: ~/.claude.json not found", details

    try:
        with open(claude_json_path, "r") as f:
            claude_config = json.load(f)
    except Exception as e:
        return "FAIL", f"MCP: failed to read ~/.claude.json: {e}", details

    projects = claude_config.get("projects", {})
    registered_projects = []
    for project_path, project_data in projects.items():
        mcp_servers = project_data.get("mcpServers", {})
        if "brain-server" in mcp_servers:
            # Use just the last folder name for brevity
            folder_name = os.path.basename(project_path.rstrip("/"))
            registered_projects.append(folder_name)

    details["registered_projects"] = registered_projects
    details["registered_count"] = len(registered_projects)

    if len(registered_projects) == 0:
        return "FAIL", "MCP: brain-server not registered in any project", details

    # Verify server.py exists
    server_path = os.path.join(ROOT_PATH, "mcp", "server.py")
    server_exists = os.path.exists(server_path)
    details["server_py_exists"] = server_exists

    if not server_exists:
        return "FAIL", f"MCP: registered for {len(registered_projects)} projects but server.py missing", details

    summary = f"MCP: brain-server registered for {len(registered_projects)} projects, server.py exists"
    return "PASS", summary, details


def check_hooks():
    """8. HOOKS — check ~/.claude/settings.json for all 4 hooks; verify hook files exist."""
    settings_path = os.path.expanduser("~/.claude/settings.json")
    details = {}

    if not os.path.exists(settings_path):
        return "FAIL", "Hooks: ~/.claude/settings.json not found", details

    try:
        with open(settings_path, "r") as f:
            settings = json.load(f)
    except Exception as e:
        return "FAIL", f"Hooks: failed to read settings.json: {e}", details

    hooks_config = settings.get("hooks", {})
    required_hooks = ["SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"]
    hook_files = {
        "SessionStart": "session-start.py",
        "UserPromptSubmit": "user-prompt-submit.py",
        "Stop": "stop.py",
        "SessionEnd": "session-end.py",
    }

    registered = 0
    files_ok = 0
    missing_hooks = []
    missing_files = []

    for hook_name in required_hooks:
        entries = hooks_config.get(hook_name, [])
        found = False
        for entry in entries:
            for h in entry.get("hooks", []):
                cmd = h.get("command", "")
                if "claude-brain" in cmd and hook_files[hook_name] in cmd:
                    found = True
                    break
            if found:
                break

        if found:
            registered += 1
        else:
            missing_hooks.append(hook_name)

        # Check file exists
        file_path = os.path.join(ROOT_PATH, "hooks", hook_files[hook_name])
        if os.path.exists(file_path):
            files_ok += 1
        else:
            missing_files.append(hook_files[hook_name])

    details["registered"] = registered
    details["files_exist"] = files_ok
    details["missing_hooks"] = missing_hooks
    details["missing_files"] = missing_files

    if missing_hooks or missing_files:
        issues = []
        if missing_hooks:
            issues.append(f"not registered: {', '.join(missing_hooks)}")
        if missing_files:
            issues.append(f"missing files: {', '.join(missing_files)}")
        return "FAIL", f"Hooks: {registered}/4 registered, {'; '.join(issues)}", details

    summary = f"Hooks: {registered}/4 registered, all files exist"
    return "PASS", summary, details


def check_config():
    """9. CONFIG — config.yaml exists? all storage paths valid? all project folders exist?"""
    config_path = os.path.join(ROOT_PATH, "config.yaml")
    details = {}

    if not os.path.exists(config_path):
        return "FAIL", "Config: config.yaml not found", details

    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
    except Exception as e:
        return "FAIL", f"Config: failed to parse config.yaml: {e}", details

    status = "PASS"
    issues = []

    # Check storage paths
    storage = config.get("storage", {})
    root = storage.get("root_path", "")
    db_path = storage.get("local_db_path", "")

    if not os.path.isdir(root):
        status = "FAIL"
        issues.append(f"root_path not found: {root}")
    details["root_path_exists"] = os.path.isdir(root)

    db_dir = os.path.dirname(db_path)
    if not os.path.isdir(db_dir):
        status = "FAIL"
        issues.append(f"db directory not found: {db_dir}")
    details["db_dir_exists"] = os.path.isdir(db_dir)

    # Check project folders exist
    projects = config.get("projects", [])
    details["project_count"] = len(projects)
    missing_folders = []

    for proj in projects:
        folder = proj.get("folder_name", "")
        folder_path = os.path.join(root, folder)
        if not os.path.isdir(folder_path):
            missing_folders.append(folder)

    details["missing_project_folders"] = missing_folders

    if missing_folders:
        if status == "PASS":
            status = "WARN"
        issues.append(f"missing folders: {', '.join(missing_folders)}")

    if not issues:
        summary = f"Config: config.yaml valid, {len(projects)} projects, all paths exist"
    else:
        summary = f"Config: {len(projects)} projects, {'; '.join(issues)}"

    return status, summary, details


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_health_check():
    """Run all 9 checks, return list of (status, summary, details) tuples."""
    config = load_config()
    if config is None:
        return [("FAIL", "Config: config.yaml not found — cannot run health check", {})]

    results = []
    results.append(("Database", *check_database(config)))
    results.append(("Space", *check_space(config)))
    results.append(("Data", *check_data_health(config)))
    results.append(("Backup", *check_backup(config)))
    results.append(("Performance", *check_performance(config)))
    results.append(("Dependencies", *check_dependencies()))
    results.append(("MCP", *check_mcp_server(config)))
    results.append(("Hooks", *check_hooks()))
    results.append(("Config", *check_config()))
    return results


def _wrap_text(text, width):
    """Word-wrap text to fit within a column width. Returns list of lines."""
    if len(text) <= width:
        return [text]
    lines = []
    while text:
        if len(text) <= width:
            lines.append(text)
            break
        # Find last space within width
        cut = text.rfind(" ", 0, width + 1)
        if cut <= 0:
            cut = width  # no space found, hard break
        lines.append(text[:cut])
        text = text[cut:].lstrip()
    return lines


def print_report(results):
    """Print bordered, colored health report with status on the right."""
    # ANSI colors
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

    # Column widths
    NAME_W = 14
    DETAIL_W = 54
    STATUS_W = 10
    INNER_W = NAME_W + DETAIL_W + STATUS_W + 8  # total inside outer borders

    # Status display: (colored_text, visual_width)
    STATUS_DISPLAY = {
        "PASS": (f"{GREEN}{BOLD}✓ PASS{RESET}", 6),
        "WARN": (f"{YELLOW}{BOLD}⚠ WARN{RESET}", 6),
        "FAIL": (f"{RED}{BOLD}✗ FAIL{RESET}", 6),
    }

    CHECK_LABELS = {
        "Database": "Database",
        "Space": "Space",
        "Data": "Data Health",
        "Backup": "Backup",
        "Performance": "Performance",
        "Dependencies": "Dependencies",
        "MCP": "MCP Server",
        "Hooks": "Hooks",
        "Config": "Config",
    }

    # Box-drawing borders
    col_sep     = f"├{'─' * (NAME_W + 2)}┼{'─' * (DETAIL_W + 2)}┼{'─' * (STATUS_W + 2)}┤"
    footer_sep  = f"├{'─' * (NAME_W + 2)}┴{'─' * (DETAIL_W + 2)}┴{'─' * (STATUS_W + 2)}┤"
    bottom      = f"└{'─' * INNER_W}┘"

    pass_count = 0
    warn_count = 0
    fail_count = 0

    print()

    # Title row (spans full width)
    title = f"{BOLD}Claude Brain Health Check{RESET}"
    title_visual = "Claude Brain Health Check"
    title_pad = INNER_W - len(title_visual) - 1
    print(f"┌{'─' * INNER_W}┐")
    print(f"│ {title}{' ' * title_pad}│")
    print(f"├{'─' * (NAME_W + 2)}┬{'─' * (DETAIL_W + 2)}┬{'─' * (STATUS_W + 2)}┤")

    # Header row
    print(f"│ {DIM}{'Check':<{NAME_W}}{RESET} │ {DIM}{'Details':<{DETAIL_W}}{RESET} │ {DIM}{'Status':^{STATUS_W}}{RESET} │")
    print(col_sep)

    # Data rows
    for name, status, summary, details in results:
        check_name = CHECK_LABELS.get(name, name)
        colored_status, status_vis_w = STATUS_DISPLAY.get(status, (status, len(status)))

        # Extract detail text (strip the check name prefix)
        detail = summary
        for prefix in [f"{name}:", f"{check_name}:"]:
            if summary.startswith(prefix):
                detail = summary[len(prefix):].strip()
                break

        # Word-wrap detail into multiple lines — show everything
        detail_lines = _wrap_text(detail, DETAIL_W)

        # Pad status to center it (accounting for ANSI invisible chars)
        status_lpad = (STATUS_W - status_vis_w) // 2
        status_rpad = STATUS_W - status_vis_w - status_lpad
        status_cell = f"{' ' * status_lpad}{colored_status}{' ' * status_rpad}"
        empty_status = f"{' ' * STATUS_W}"

        # First line: check name + first detail line + status
        print(f"│ {check_name:<{NAME_W}} │ {detail_lines[0]:<{DETAIL_W}} │ {status_cell} │")

        # Continuation lines: empty name + wrapped detail + empty status
        for extra_line in detail_lines[1:]:
            print(f"│ {'':<{NAME_W}} │ {extra_line:<{DETAIL_W}} │ {empty_status} │")

        if status == "PASS":
            pass_count += 1
        elif status == "WARN":
            warn_count += 1
        else:
            fail_count += 1

        # Dotted separator between rows (not after the last row)
        if (name, status, summary, details) != results[-1]:
            print(f"│ {DIM}{'·' * NAME_W}{RESET} │ {DIM}{'·' * DETAIL_W}{RESET} │ {DIM}{'·' * STATUS_W}{RESET} │")

    # Footer
    total = pass_count + warn_count + fail_count
    print(footer_sep)

    if fail_count > 0:
        score_color = RED
    elif warn_count > 0:
        score_color = YELLOW
    else:
        score_color = GREEN

    score_parts = [f"{score_color}{BOLD}{pass_count}/{total} PASS{RESET}"]
    if warn_count > 0:
        score_parts.append(f"{YELLOW}{warn_count} WARN{RESET}")
    if fail_count > 0:
        score_parts.append(f"{RED}{fail_count} FAIL{RESET}")
    score_text = ", ".join(score_parts)

    # Visual width of score (without ANSI codes)
    score_visual = f"{pass_count}/{total} PASS"
    if warn_count > 0:
        score_visual += f", {warn_count} WARN"
    if fail_count > 0:
        score_visual += f", {fail_count} FAIL"

    label = "Score: "
    score_pad = INNER_W - len(label) - len(score_visual) - 1
    print(f"│ {label}{score_text}{' ' * score_pad}│")
    print(bottom)
    print()

    return fail_count, warn_count


def main():
    parser = argparse.ArgumentParser(description="Claude Brain 9-point health check")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    results = run_health_check()

    if args.json:
        output = []
        for name, status, summary, details in results:
            output.append({
                "check": name,
                "status": status,
                "summary": summary,
                "details": details,
            })
        print(json.dumps(output, indent=2))
        # Count for exit code
        fail_count = sum(1 for r in results if r[1] == "FAIL")
        warn_count = sum(1 for r in results if r[1] == "WARN")
    else:
        fail_count, warn_count = print_report(results)

    if fail_count > 0:
        sys.exit(2)
    elif warn_count > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
