#!/usr/bin/env python3
"""
brain-setup.py — First-run installer for claude-brain.

Creates database, config, directories, hooks, MCP registration,
and seeds initial brain data. Idempotent — safe to re-run.

Usage:
    python3 scripts/brain-setup.py
    python3 scripts/brain-setup.py --questionnaire  (import filled questionnaire)
"""

import json
import os
import platform
import re
import shutil
import sqlite3
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIN_PYTHON = (3, 10)
PIP_PACKAGES = ["PyYAML", "mcp", "sentence-transformers", "numpy"]
HOOK_EVENTS = ["SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"]
HOOK_SCRIPTS = ["session-start.py", "user-prompt-submit.py", "stop.py", "session-end.py"]

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def green(text):
    return f"\033[92m{text}\033[0m"

def red(text):
    return f"\033[91m{text}\033[0m"

def yellow(text):
    return f"\033[93m{text}\033[0m"

def bold(text):
    return f"\033[1m{text}\033[0m"

def phase_header(num, total, title):
    print(f"\n{'='*60}")
    print(f"  [{num}/{total}] {title}")
    print(f"{'='*60}")

def ok(msg):
    print(f"  {green('✓')} {msg}")

def fail(msg):
    print(f"  {red('✗')} {msg}")

def warn(msg):
    print(f"  {yellow('!')} {msg}")

def info(msg):
    print(f"  {msg}")

def ask(prompt, default=None):
    if default:
        raw = input(f"  {prompt} [{default}]: ").strip()
        return raw if raw else default
    return input(f"  {prompt}: ").strip()

def ask_yn(prompt, default="y"):
    suffix = "[Y/n]" if default == "y" else "[y/N]"
    raw = input(f"  {prompt} {suffix}: ").strip().lower()
    if not raw:
        return default == "y"
    return raw in ("y", "yes")

def generate_prefix(name, existing_prefixes):
    """Generate a 2-3 char prefix from a project name, avoiding collisions."""
    parts = name.split("-")
    # Try first letters of each word (2-3 chars)
    if len(parts) >= 2:
        candidate = "".join(p[0] for p in parts[:3])
    else:
        candidate = name[:3]

    if candidate not in existing_prefixes:
        return candidate

    # Collision — try adding more letters
    for length in range(2, min(len(name.replace("-", "")), 5)):
        flat = name.replace("-", "")
        candidate = flat[:length]
        if candidate not in existing_prefixes:
            return candidate

    # Last resort — append digit
    base = name.replace("-", "")[:2]
    for i in range(2, 100):
        candidate = f"{base}{i}"
        if candidate not in existing_prefixes:
            return candidate
    return base

# ---------------------------------------------------------------------------
# Phase 1: Pre-flight
# ---------------------------------------------------------------------------

def phase_preflight():
    phase_header(1, 9, "PRE-FLIGHT CHECKS")
    errors = []

    # Python version
    v = sys.version_info
    if v >= MIN_PYTHON:
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        fail(f"Python {v.major}.{v.minor} — need {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+")
        errors.append("Python version too old")

    # Claude Code
    claude_path = shutil.which("claude")
    if claude_path:
        try:
            result = subprocess.run(["claude", "--version"], capture_output=True, text=True, timeout=10)
            version = result.stdout.strip() or result.stderr.strip()
            ok(f"Claude Code found: {version[:60]}")
        except Exception:
            ok(f"Claude Code found at {claude_path}")
    else:
        fail("Claude Code not installed")
        info("  Install: https://docs.anthropic.com/en/docs/claude-code/overview")
        errors.append("Claude Code not found")

    # pip
    pip_cmd = None
    if shutil.which("pip3"):
        pip_cmd = ["pip3"]
        ok("pip3 available")
    else:
        try:
            subprocess.run([sys.executable, "-m", "pip", "--version"],
                           capture_output=True, timeout=10, check=True)
            pip_cmd = [sys.executable, "-m", "pip"]
            ok("pip available (via python3 -m pip)")
        except Exception:
            fail("pip not found")
            errors.append("pip not available")

    if errors:
        print(f"\n  {red('HARD STOP')}: Fix the above errors before continuing.")
        sys.exit(1)

    return pip_cmd

# ---------------------------------------------------------------------------
# Phase 2: Dependencies
# ---------------------------------------------------------------------------

def phase_dependencies(pip_cmd):
    phase_header(2, 9, "DEPENDENCIES")
    failed = []

    for pkg in PIP_PACKAGES:
        import_name = pkg.lower().replace("-", "_")
        if import_name == "pyyaml":
            import_name = "yaml"

        try:
            __import__(import_name)
            ok(f"{pkg} already installed")
        except ImportError:
            info(f"Installing {pkg}...")
            try:
                subprocess.run(
                    pip_cmd + ["install", "--quiet", pkg],
                    capture_output=True, text=True, timeout=300, check=True
                )
                # Verify import
                __import__(import_name)
                ok(f"{pkg} installed")
            except Exception as e:
                fail(f"{pkg} failed to install: {e}")
                failed.append(pkg)

    if failed:
        print(f"\n  {red('ERROR')}: Failed to install: {', '.join(failed)}")
        print("  Try manually: pip3 install " + " ".join(failed))
        sys.exit(1)

# ---------------------------------------------------------------------------
# Phase 3: Interactive Projects & Storage
# ---------------------------------------------------------------------------

def phase_projects():
    phase_header(3, 9, "PROJECT SETUP")

    # --- Storage mode ---
    print("\n  Storage mode:")
    print("    synced — Root folder in a sync service (Dropbox, OneDrive, etc.)")
    print("             Database stored separately on local disk.")
    print("    local  — Everything in one folder. Single computer setup.")
    storage_mode = ask("Storage mode", "synced").lower()
    while storage_mode not in ("synced", "local"):
        storage_mode = ask("Enter 'synced' or 'local'", "synced").lower()

    # --- Detect root path ---
    script_dir = Path(__file__).resolve().parent.parent
    home = Path.home()

    if storage_mode == "synced":
        # Try to detect if we're already inside the repo
        if (script_dir / "mcp" / "server.py").exists():
            default_root = str(script_dir)
        else:
            # Common sync folder locations
            for candidate in [
                home / "Dropbox" / "claude-brain",
                home / "OneDrive" / "claude-brain",
                home / "Google Drive" / "claude-brain",
            ]:
                if candidate.parent.exists():
                    default_root = str(candidate)
                    break
            else:
                default_root = str(home / "Dropbox" / "claude-brain")

        root_path = ask("Root folder path", default_root)
        default_db = str(home / "claude-brain-local" / "claude-brain.db")
        db_path = ask("Local database path (NOT in sync folder)", default_db)
    else:
        default_root = str(home / "claude-brain")
        root_path = ask("Root folder path", default_root)
        root_path = os.path.expanduser(root_path)
        db_path = os.path.join(root_path, "claude-brain.db")
        info(f"Database will be at: {db_path}")

    root_path = os.path.expanduser(root_path)
    db_path = os.path.expanduser(db_path)

    # --- Projects ---
    print("\n  Define your projects. Each project gets its own folder.")
    print("  Names must be lowercase with hyphens only (e.g., 'my-project').")
    print("  Press Enter with no name when done. At least 1 required.")
    print()

    projects = []
    prefixes_used = set()
    pattern = re.compile(r'^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$')

    while True:
        default_hint = "general" if not projects else ""
        prompt = "Project name" + (f" (default: {default_hint})" if default_hint else " (Enter to finish)")
        name = input(f"  {prompt}: ").strip().lower()

        if not name:
            if not projects:
                name = "general"
                info("Using default: general")
            else:
                break

        if not pattern.match(name):
            warn("Invalid name. Use lowercase letters, numbers, hyphens. Must start with a letter.")
            continue

        if name in [p["folder_name"] for p in projects]:
            warn(f"'{name}' already added.")
            continue

        prefix = generate_prefix(name, prefixes_used)
        label = ask(f"  Label for '{name}'", name.replace("-", " ").title())
        shown_prefix = ask(f"  Prefix for '{name}'", prefix)
        if shown_prefix != prefix:
            if shown_prefix in prefixes_used:
                warn(f"Prefix '{shown_prefix}' already in use. Using '{prefix}'.")
                shown_prefix = prefix
            prefix = shown_prefix

        projects.append({
            "folder_name": name,
            "prefix": prefix,
            "label": label
        })
        prefixes_used.add(prefix)
        ok(f"Added: {name} (prefix: {prefix})")

    # Auto-add "other" if not present
    if "other" not in [p["folder_name"] for p in projects]:
        oth_prefix = generate_prefix("other", prefixes_used)
        projects.append({
            "folder_name": "other",
            "prefix": oth_prefix,
            "label": "Uncategorized"
        })
        prefixes_used.add(oth_prefix)
        ok(f"Auto-added: other (prefix: {oth_prefix}) — catch-all for unmatched sessions")

    # --- Quick identity questions ---
    print("\n  Quick identity setup (seeds your brain profile):")
    print("  Press Enter to skip any question.\n")
    identity = {}
    name_answer = ask("Your name")
    if name_answer:
        identity["full_name"] = name_answer
    location_answer = ask("Your location (city, state/country)")
    if location_answer:
        identity["location"] = location_answer
    role_answer = ask("What you do (role/profession)")
    if role_answer:
        identity["role"] = role_answer

    # --- Import ~/.claude/CLAUDE.md preferences ---
    claude_md_path = home / ".claude" / "CLAUDE.md"
    claude_md_content = None
    if claude_md_path.exists():
        info(f"\nFound personal CLAUDE.md at {claude_md_path}")
        if ask_yn("Import its contents as brain preferences?"):
            claude_md_content = claude_md_path.read_text(encoding="utf-8")
            ok("Will import CLAUDE.md preferences")

    # --- Confirm ---
    print(f"\n  {bold('Summary:')}")
    print(f"    Storage: {storage_mode}")
    print(f"    Root:    {root_path}")
    print(f"    DB:      {db_path}")
    print(f"    Projects:")
    for p in projects:
        print(f"      {p['folder_name']} ({p['prefix']}) — {p['label']}")
    if identity:
        print(f"    Identity: {', '.join(f'{k}={v}' for k, v in identity.items())}")
    print()

    if not ask_yn("Proceed?"):
        print("  Aborted.")
        sys.exit(0)

    return {
        "storage_mode": storage_mode,
        "root_path": root_path,
        "db_path": db_path,
        "projects": projects,
        "identity": identity,
        "claude_md_content": claude_md_content,
    }

# ---------------------------------------------------------------------------
# Phase 4: Directories
# ---------------------------------------------------------------------------

def phase_directories(cfg):
    phase_header(4, 9, "DIRECTORIES")
    root = Path(cfg["root_path"])
    db_dir = Path(cfg["db_path"]).parent

    dirs_to_create = [
        root,
        root / "scripts",
        root / "hooks",
        root / "mcp",
        root / "logs",
        root / "db-backup",
        root / "imports",
        root / "imports" / "completed",
        root / "verification",
        db_dir,
    ]

    # Project directories
    for p in cfg["projects"]:
        dirs_to_create.append(root / p["folder_name"])
        dirs_to_create.append(root / p["folder_name"] / "chat-files")

    for d in dirs_to_create:
        d.mkdir(parents=True, exist_ok=True)

    ok(f"Created {len(dirs_to_create)} directories")

    # .gitkeep in empty dirs
    for name in ["db-backup", "logs"]:
        gitkeep = root / name / ".gitkeep"
        if not gitkeep.exists():
            gitkeep.touch()
    completed_gitkeep = root / "imports" / "completed" / ".gitkeep"
    if not completed_gitkeep.exists():
        completed_gitkeep.touch()

    ok(".gitkeep files in place")

# ---------------------------------------------------------------------------
# Phase 5: Database
# ---------------------------------------------------------------------------

DDL_STATEMENTS = [
    # --- System tables ---
    """CREATE TABLE IF NOT EXISTS sys_sessions (
        session_id       TEXT PRIMARY KEY,
        project          TEXT,
        started_at       TEXT,
        ended_at         TEXT,
        cwd              TEXT,
        claude_version   TEXT,
        model            TEXT,
        source           TEXT,
        message_count    INTEGER DEFAULT 0,
        created_at       TEXT,
        quality_score    INTEGER DEFAULT NULL,
        quality_tags     TEXT DEFAULT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS sys_ingest_log (
        file_path        TEXT PRIMARY KEY,
        file_size        INTEGER,
        file_type        TEXT,
        records_imported INTEGER,
        ingested_at      TEXT
    )""",
    # sys_session_summaries REMOVED — sys_sessions.notes is the single source of truth
    """CREATE TABLE IF NOT EXISTS project_registry (
        folder_name      TEXT PRIMARY KEY,
        prefix           TEXT UNIQUE,
        label            TEXT,
        registered_at    TEXT,
        summary          TEXT,
        summary_updated_at TEXT,
        status           TEXT DEFAULT 'active',
        health           TEXT DEFAULT 'green'
    )""",

    # --- Transcript tables ---
    """CREATE TABLE IF NOT EXISTS transcripts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id       TEXT,
        project          TEXT,
        uuid             TEXT UNIQUE,
        parent_uuid      TEXT,
        type             TEXT,
        subtype          TEXT,
        role             TEXT,
        content          TEXT,
        model            TEXT,
        timestamp        TEXT,
        token_input      INTEGER,
        token_output     INTEGER,
        stop_reason      TEXT,
        is_subagent      INTEGER DEFAULT 0,
        source_file      TEXT,
        raw_json         TEXT,
        created_at       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS tool_results (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id       TEXT,
        project          TEXT,
        tool_use_id      TEXT,
        content          TEXT,
        source_file      TEXT,
        created_at       TEXT
    )""",

    # --- Brain tables ---
    """CREATE TABLE IF NOT EXISTS brain_facts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        category         TEXT,
        key              TEXT,
        value            TEXT,
        source           TEXT,
        source_session   TEXT,
        confidence       TEXT,
        created_at       TEXT,
        updated_at       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS brain_preferences (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        category         TEXT,
        preference       TEXT,
        source           TEXT,
        created_at       TEXT,
        updated_at       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS decisions (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        project          TEXT,
        decision_number  INTEGER,
        session_id       TEXT,
        description      TEXT,
        rationale        TEXT,
        created_at       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS facts (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        project          TEXT,
        category         TEXT,
        key              TEXT,
        value            TEXT,
        source           TEXT,
        session_id       TEXT,
        created_at       TEXT,
        updated_at       TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS transcript_embeddings (
        transcript_id    INTEGER PRIMARY KEY,
        embedding        BLOB NOT NULL,
        model            TEXT DEFAULT 'all-MiniLM-L6-v2',
        created_at       TEXT
    )""",
]

DDL_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id)",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_project ON transcripts(project)",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_type ON transcripts(type)",
    "CREATE INDEX IF NOT EXISTS idx_transcripts_uuid ON transcripts(uuid)",
]

DDL_FTS = """CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
    content,
    content=transcripts,
    content_rowid=id
)"""

DDL_FTS_VOCAB = """CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts_vocab \
USING fts5vocab(transcripts_fts, row)"""

DDL_TRIGGERS = [
    """CREATE TRIGGER IF NOT EXISTS transcripts_ai AFTER INSERT ON transcripts BEGIN
        INSERT INTO transcripts_fts(rowid, content) VALUES (new.id, new.content);
    END""",
    """CREATE TRIGGER IF NOT EXISTS transcripts_au AFTER UPDATE ON transcripts BEGIN
        INSERT INTO transcripts_fts(transcripts_fts, rowid, content) VALUES ('delete', old.id, old.content);
        INSERT INTO transcripts_fts(rowid, content) VALUES (new.id, new.content);
    END""",
    """CREATE TRIGGER IF NOT EXISTS transcripts_ad AFTER DELETE ON transcripts BEGIN
        INSERT INTO transcripts_fts(transcripts_fts, rowid, content) VALUES ('delete', old.id, old.content);
    END""",
]


def phase_database(cfg):
    phase_header(5, 9, "DATABASE")
    db_path = cfg["db_path"]
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tables
    for ddl in DDL_STATEMENTS:
        cursor.execute(ddl)
    ok(f"{len(DDL_STATEMENTS)} tables verified")

    # Indexes
    for ddl in DDL_INDEXES:
        cursor.execute(ddl)
    ok(f"{len(DDL_INDEXES)} indexes verified")

    # FTS5
    try:
        cursor.execute(DDL_FTS)
        ok("FTS5 virtual table verified")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            ok("FTS5 virtual table already exists")
        else:
            fail(f"FTS5 creation failed: {e}")

    # FTS5 vocab table (for fuzzy search)
    try:
        cursor.execute(DDL_FTS_VOCAB)
        ok("FTS5 vocab table verified")
    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            ok("FTS5 vocab table already exists")
        else:
            fail(f"FTS5 vocab creation failed: {e}")

    # Triggers
    for ddl in DDL_TRIGGERS:
        try:
            cursor.execute(ddl)
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                pass
            else:
                fail(f"Trigger failed: {e}")
    ok(f"{len(DDL_TRIGGERS)} triggers verified")

    # Seed project_registry
    for p in cfg["projects"]:
        cursor.execute(
            "INSERT OR IGNORE INTO project_registry (folder_name, prefix, label, registered_at) VALUES (?, ?, ?, ?)",
            (p["folder_name"], p["prefix"], p["label"], now)
        )
    conn.commit()
    ok(f"project_registry seeded ({len(cfg['projects'])} projects)")

    # Seed identity from quick questions
    identity = cfg.get("identity", {})
    if identity:
        for key, value in identity.items():
            cursor.execute(
                "INSERT OR IGNORE INTO brain_facts (category, key, value, source, confidence, created_at, updated_at) "
                "SELECT ?, ?, ?, 'brain-setup', 'confirmed', ?, ? "
                "WHERE NOT EXISTS (SELECT 1 FROM brain_facts WHERE category='identity' AND key=?)",
                ("identity", key, value, now, now, key)
            )
        conn.commit()
        ok(f"Identity seeded ({len(identity)} facts)")

    # Import CLAUDE.md preferences
    claude_md = cfg.get("claude_md_content")
    if claude_md:
        lines = [l.strip() for l in claude_md.splitlines() if l.strip() and not l.strip().startswith("#")]
        count = 0
        for line in lines:
            if len(line) > 10:  # Skip very short lines
                cursor.execute(
                    "INSERT INTO brain_preferences (category, preference, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    ("imported-claude-md", line, "brain-setup (~/.claude/CLAUDE.md)", now, now)
                )
                count += 1
        conn.commit()
        ok(f"Imported {count} preferences from CLAUDE.md")

    conn.close()
    ok(f"Database ready: {db_path}")

# ---------------------------------------------------------------------------
# Phase 6: Config + CLAUDE.md
# ---------------------------------------------------------------------------

def phase_config(cfg):
    phase_header(6, 9, "CONFIG & CLAUDE.MD FILES")
    root = Path(cfg["root_path"])

    # --- Generate config.yaml ---
    import yaml

    projects_list = []
    for p in cfg["projects"]:
        projects_list.append({
            "folder_name": p["folder_name"],
            "prefix": p["prefix"],
            "label": p["label"],
        })

    # Build jsonl_project_mapping from projects
    jsonl_mapping = {}
    for p in cfg["projects"]:
        jsonl_mapping[p["folder_name"]] = p["prefix"]

    config_data = {
        "storage": {
            "mode": cfg["storage_mode"],
            "root_path": cfg["root_path"],
        },
        "database": {
            "write_every_response": True,
            "read_priority": [
                "structured_tables",
                "raw_transcripts",
                "project_files",
                "tell_user_not_found",
            ],
        },
        "backup": {
            "max_copies": 2,
            "verify_after_copy": True,
        },
        "projects": projects_list,
        "brain": {
            "prefix": "brain",
            "categories": [
                "identity", "family", "professional", "working-style",
                "technical-setup", "goals", "preferences", "lessons-learned",
                "contacts", "health",
            ],
        },
        "jsonl": {
            "source_paths": [
                os.path.join(str(Path.home()), ".claude", "projects"),
            ],
            "ingest_subagents": True,
            "ingest_tool_results": True,
        },
        "jsonl_project_mapping": jsonl_mapping,
        "semantic_search": {
            "enabled": True,
            "model": "all-MiniLM-L6-v2",
        },
        "file_versioning": {
            "enabled": True,
            "folder_pattern": "{date}_{time}_{session_id_short}",
            "date_format": "YYYY-MM-DD",
            "time_format": "HHMMSS",
            "session_id_length": 8,
        },
        "logging": {
            "enabled": True,
            "level": "info",
        },
        "startup": {
            "run_on_session_start": True,
            "blocking": True,
            "verify_folders": True,
        },
        "scripts": {
            "commands": {
                "brain-check": "startup_check.py",
                "brain-sync": "brain_sync.py",
                "brain-status": "status.py",
            },
        },
        "meta": {
            "project_name": "claude-brain",
            "version": "0.1.0",
            "license": "MIT",
            "github": "https://github.com/yourusername/claude-brain",
        },
    }

    if cfg["storage_mode"] == "synced":
        config_data["storage"]["local_db_path"] = cfg["db_path"]

    config_path = root / "config.yaml"
    write_config = True
    if config_path.exists():
        warn(f"config.yaml already exists at {config_path}")
        write_config = ask_yn("Overwrite?", "n")

    if write_config:
        with open(config_path, "w") as f:
            f.write("# claude-brain Configuration File\n")
            f.write("# Generated by brain-setup.py on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write("# See config.yaml.example for documentation of all options.\n\n")
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        ok(f"config.yaml written")
    else:
        ok("config.yaml skipped (kept existing)")

    # --- Generate config.yaml.example ---
    example_data = {
        "storage": {
            "mode": "synced",
            "root_path": "~/Dropbox/claude-brain",
            "local_db_path": "~/claude-brain-local/claude-brain.db",
        },
        "database": config_data["database"],
        "backup": config_data["backup"],
        "projects": [
            {"folder_name": "my-project", "prefix": "mp", "label": "My Project"},
            {"folder_name": "general", "prefix": "gen", "label": "General Conversations"},
            {"folder_name": "other", "prefix": "oth", "label": "Uncategorized"},
        ],
        "brain": config_data["brain"],
        "jsonl": {
            "source_paths": ["~/.claude/projects"],
            "ingest_subagents": True,
            "ingest_tool_results": True,
        },
        "jsonl_project_mapping": {
            "my-project": "mp",
            "general": "gen",
        },
        "semantic_search": config_data["semantic_search"],
        "file_versioning": config_data["file_versioning"],
        "logging": config_data["logging"],
        "startup": config_data["startup"],
        "scripts": config_data["scripts"],
        "meta": {
            "project_name": "claude-brain",
            "version": "0.1.0",
            "license": "MIT",
            "github": "https://github.com/yourusername/claude-brain",
            "author": "Your Name",
        },
    }

    example_path = root / "config.yaml.example"
    if example_path.exists():
        ok("config.yaml.example already exists (shipped with repo, skipping)")
    else:
        with open(example_path, "w") as f:
            f.write("# claude-brain Configuration File — EXAMPLE\n")
            f.write("# Copy this to config.yaml and edit with your values.\n")
            f.write("# Or run: python3 scripts/brain-setup.py (generates config for you)\n\n")
            yaml.dump(example_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        ok("config.yaml.example written")

    # --- Generate CLAUDE.md per project ---
    for p in cfg["projects"]:
        project_dir = root / p["folder_name"]
        claude_md = project_dir / "CLAUDE.md"

        template = textwrap.dedent(f"""\
            # {p['label']}

            PROJECT: {p['folder_name']}
            PREFIX: {p['prefix']}

            ## RULE #1 — USE THE BRAIN FIRST. ALWAYS.
            **You have a brain with persistent memory across sessions. USE IT before doing anything substantive.**
            - Before proposing a plan, starting a task, debugging, answering questions, or suggesting changes: **search the brain.**
            - Use `search_transcripts`, `search_semantic`, `get_recent_summaries`, `lookup_decision`, `lookup_fact`.
            - Files tell you WHAT exists. The brain tells you WHY — strategic context, prior decisions, rejected approaches.
            - Not using the brain is the same as not having it.

            ## BRAIN CONNECTION
            MCP server "brain-server" provides persistent memory.
            Database: {cfg['db_path']}

            ## SESSION START
            1. **Search the brain** — query search_transcripts + get_recent_summaries for this project. This is step ONE.
            2. Call get_profile() and get_project_state('{p['prefix']}') to load working context.
            3. Hooks handle startup check and context injection automatically.

            ## TOOL ROUTING
            When you need information, use the right MCP tool:
            - "Who is [person]?" / "What do I know about..." -> lookup_fact
            - "What did we decide about..." -> lookup_decision
            - "Find conversations about..." -> search_transcripts
            - "What did we discuss about..." -> search_transcripts (or search_semantic for meaning-based)
            - "Show me session..." -> get_session
            - "Recent sessions" -> get_recent_sessions
            - "My preferences" / "My profile" -> get_profile
            - "Project status" -> get_project_state
            - "Brain status" / "How many sessions" -> get_status

            ## SEARCH PRIORITY
            1. Structured tables (decisions, facts) via MCP
            2. Raw transcripts via MCP search_transcripts()
            3. Semantic search via MCP search_semantic() (meaning-based)
            4. Project text files in this folder
            5. Tell user: "I don't have this information"

            ## FILE VERSIONING
            After creating or modifying any file, run:
            python3 {root}/scripts/copy_chat_file.py \\
              [filepath] --project {p['prefix']} --session $SESSION_ID

            ## SESSION END
            Hooks handle session summary generation and database backup
            automatically. No manual steps required.
        """)

        write_it = True
        if claude_md.exists():
            warn(f"CLAUDE.md already exists in {p['folder_name']}/")
            write_it = ask_yn(f"  Overwrite {p['folder_name']}/CLAUDE.md?", "n")

        if write_it:
            with open(claude_md, "w") as f:
                f.write(template)
            ok(f"CLAUDE.md written for {p['folder_name']}")
        else:
            ok(f"CLAUDE.md skipped for {p['folder_name']} (kept existing)")

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Phase 7: Email Digests (optional)
# ---------------------------------------------------------------------------

def phase_email(cfg):
    phase_header(7, 9, "EMAIL DIGESTS (optional)")

    print("""
  The brain can email you proactive status reports:
    - Daily standup at 8am (what to work on today)
    - Weekly portfolio digest (Monday mornings)
    - Project deep dives (on demand)

  Requires a Gmail account with an App Password.
  (Not your regular password — a 16-character App Password from Google.)
""")

    if not ask_yn("Do you want to set up email digests?", "n"):
        info("Skipped. You can set this up later in config.yaml.")
        cfg["email_enabled"] = False
        return

    # Get email address
    from_addr = ""
    while not from_addr:
        from_addr = input("  Gmail address: ").strip()
        if "@" not in from_addr:
            warn("That doesn't look like an email address.")
            from_addr = ""

    to_addr = from_addr
    if ask_yn(f"  Send digests to the same address ({from_addr})?"):
        pass
    else:
        to_addr = input("  Recipient email address: ").strip() or from_addr

    # Get app password
    print(f"""
  You need a Gmail App Password (NOT your regular password).
  To create one:
    1. Go to myaccount.google.com -> Security -> 2-Step Verification
    2. At the bottom, click "App passwords"
    3. Create one for "Mail" / "Other" -> name it "claude-brain"
    4. Copy the 16-character password
""")
    app_password = input("  Gmail App Password: ").strip()
    if not app_password:
        warn("No password entered. Email will be disabled.")
        cfg["email_enabled"] = False
        return

    # Test connection
    info("Testing SMTP connection...")
    try:
        import smtplib
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(from_addr, app_password)
        ok("SMTP connection successful!")
    except Exception as e:
        warn(f"SMTP test failed: {e}")
        warn("Email config saved anyway — you can fix the password later in config.yaml.")

    # Write email config directly to config.yaml
    config_path = Path(cfg["root_path"]) / "config.yaml"
    if config_path.exists():
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}
        config_data["email"] = {
            "enabled": True,
            "from_address": from_addr,
            "to_address": to_addr,
            "gmail_app_password": app_password,
        }
        with open(config_path, "w") as f:
            f.write("# claude-brain Configuration File\n")
            f.write("# Updated by brain-setup.py on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
            f.write("# See config.yaml.example for documentation of all options.\n\n")
            yaml.dump(config_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        ok("Email config written to config.yaml")
    else:
        warn("config.yaml not found — run full setup first. Email config skipped.")
        return

    # Offer to set up cron
    print()
    root = cfg["root_path"]
    digest_script = os.path.join(root, "scripts", "brain_digest.py")
    log_dir = os.path.dirname(cfg["db_path"])
    daily_cron = f'0 8 * * 1-5 /usr/bin/python3 {digest_script} --daily >> {log_dir}/digest.log 2>&1'
    weekly_cron = f'0 8 * * 1 /usr/bin/python3 {digest_script} >> {log_dir}/digest.log 2>&1'

    if ask_yn("  Set up daily standup cron (weekdays 8am)?", "y"):
        try:
            import subprocess
            existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            if "brain_digest" not in existing and "--daily" not in existing:
                new_cron = existing.rstrip("\n") + "\n" + daily_cron + "\n"
                subprocess.run(["crontab", "-"], input=new_cron, text=True)
                ok("Daily cron installed (weekdays 8am)")
            else:
                ok("Daily cron already exists, skipped")
        except Exception as e:
            warn(f"Could not set cron: {e}")
            info(f"  Add manually: {daily_cron}")

    if ask_yn("  Set up weekly digest cron (Monday 8am)?", "y"):
        try:
            existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
            if "brain_digest" not in existing or "--daily" in existing:
                # Check if weekly already there
                if "brain_digest.py >>" in existing and "--daily" not in existing.split("brain_digest.py >>")[0].split("\n")[-1]:
                    ok("Weekly cron already exists, skipped")
                else:
                    new_cron = existing.rstrip("\n") + "\n" + weekly_cron + "\n"
                    subprocess.run(["crontab", "-"], input=new_cron, text=True)
                    ok("Weekly cron installed (Monday 8am)")
        except Exception as e:
            warn(f"Could not set cron: {e}")
            info(f"  Add manually: {weekly_cron}")

    ok("Email digests configured")


# Phase 8: Registration + Ingestion
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

def phase_registration(cfg):
    phase_header(8, 9, "REGISTRATION & INGESTION")
    root = Path(cfg["root_path"])
    home = Path.home()

    # --- Register hooks in ~/.claude/settings.json ---
    settings_path = home / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    if settings_path.exists():
        with open(settings_path) as f:
            settings = json.load(f)
    else:
        settings = {}

    hooks = settings.get("hooks", {})
    hooks_added = 0

    for event, script in zip(HOOK_EVENTS, HOOK_SCRIPTS):
        hook_cmd = f"python3 {root}/hooks/{script}"
        existing = hooks.get(event, [])

        # Check if already registered with same command
        already = False
        for entry in existing:
            for h in entry.get("hooks", []):
                if h.get("command") == hook_cmd:
                    already = True
                    break

        if not already:
            new_entry = {
                "matcher": "",
                "hooks": [{"type": "command", "command": hook_cmd}]
            }
            if existing:
                existing.append(new_entry)
            else:
                existing = [new_entry]
            hooks[event] = existing
            hooks_added += 1

    if hooks_added > 0:
        settings["hooks"] = hooks
        info(f"Will add {hooks_added} hook(s) to {settings_path}")
        if ask_yn("Register hooks?"):
            with open(settings_path, "w") as f:
                json.dump(settings, f, indent=4)
            ok(f"{hooks_added} hooks registered")
        else:
            warn("Hooks not registered — brain won't auto-capture sessions")
    else:
        ok("All 4 hooks already registered")

    # --- Register MCP server in ~/.claude.json ---
    claude_json_path = home / ".claude.json"
    if claude_json_path.exists():
        with open(claude_json_path) as f:
            claude_json = json.load(f)
    else:
        claude_json = {}

    projects_section = claude_json.get("projects", {})
    mcp_added = 0
    server_path = str(root / "mcp" / "server.py")

    mcp_entry = {
        "type": "stdio",
        "command": "python3",
        "args": [server_path],
        "env": {}
    }

    for p in cfg["projects"]:
        project_path = str(root / p["folder_name"])
        if project_path not in projects_section:
            projects_section[project_path] = {
                "allowedTools": [],
                "mcpContextUris": [],
                "mcpServers": {},
                "enabledMcpjsonServers": [],
                "disabledMcpjsonServers": [],
                "hasTrustDialogAccepted": False,
            }

        existing_mcp = projects_section[project_path].get("mcpServers", {})
        if "brain-server" not in existing_mcp:
            existing_mcp["brain-server"] = mcp_entry
            projects_section[project_path]["mcpServers"] = existing_mcp
            mcp_added += 1

    # Also register for the root path
    root_str = str(root)
    if root_str not in projects_section:
        projects_section[root_str] = {
            "allowedTools": [],
            "mcpContextUris": [],
            "mcpServers": {},
            "enabledMcpjsonServers": [],
            "disabledMcpjsonServers": [],
            "hasTrustDialogAccepted": False,
        }
    if "brain-server" not in projects_section[root_str].get("mcpServers", {}):
        projects_section[root_str].setdefault("mcpServers", {})["brain-server"] = mcp_entry
        mcp_added += 1

    if mcp_added > 0:
        claude_json["projects"] = projects_section
        info(f"Will register MCP server for {mcp_added} project path(s)")
        if ask_yn("Register MCP server?"):
            with open(claude_json_path, "w") as f:
                json.dump(claude_json, f, indent=4)
            ok(f"MCP server registered for {mcp_added} paths")
        else:
            warn("MCP not registered — brain queries won't work until registered")
    else:
        ok("MCP server already registered for all projects")

    # --- Install custom slash commands ---
    commands_dir = home / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)

    slash_commands = {
        "brain-import": textwrap.dedent(f"""\
            Import claude.ai conversation exports into the brain database.

            Step 1: List JSON files in the imports folder:
              ls {root}/imports/*.json

            If no JSON files are found, tell the user:
            "No JSON files found in {root}/imports/. To import claude.ai conversations:
            1. Install the AI Chat Exporter Chrome extension from the Chrome Web Store
            2. Go to claude.ai, open a conversation, click the extension icon, export as JSON
            3. Move the downloaded .json file to: {root}/imports/
            4. Then run /brain-import again"
            And stop here.

            Step 2: If files ARE found, show the user a numbered list of filenames.
            Ask: "Which file do you want to import?" (they can say a number or filename)

            Step 3: Ask which project to assign it to. Show the available projects by running:
              python3 -c "import sqlite3; conn=sqlite3.connect('{db_path}'); [print(f'  {{r[1]}} — {{r[2]}}') for r in conn.execute('SELECT folder_name, prefix, label FROM project_registry ORDER BY folder_name')]"

            Step 4: Run the import with their choices:
              python3 {root}/scripts/import_claude_ai.py "<chosen_file_path>" --project <chosen_prefix>

            Step 5: Show the result. If successful, tell the user the file has been moved to imports/completed/.
            Ask if they want to import another file (if more remain in imports/).
        """),
        "brain-status": textwrap.dedent(f"""\
            Run the brain status check. Execute this command:
            python3 {root}/scripts/status.py

            Show the user the full output. This displays:
            - Total sessions and messages in the database
            - Messages per project
            - Last session date per project
            - Database size and backup status
            - Semantic search embedding count
        """),
        "brain-setup": textwrap.dedent(f"""\
            Run the brain setup script to add projects or fix configuration.
            Execute this command:
            python3 {root}/scripts/brain-setup.py

            This is an interactive script. It will walk through setup phases
            and is safe to re-run (idempotent). Use this when:
            - Adding a new project
            - Fixing a broken hook or MCP registration
            - Re-generating config after changes
        """),
        "brain-questionnaire": textwrap.dedent(f"""\
            Help the user fill out their brain questionnaire.

            The questionnaire file is at: {root}/brain-questionnaire.txt

            First, read the file to see what's already filled in.
            Then ask the user what they'd like to add or update.
            Edit the file with their answers.

            When they're done, run:
            python3 {root}/scripts/brain-setup.py --questionnaire

            This imports their answers into the brain database so Claude
            knows who they are across every session.
        """),
    }

    cmds_added = 0
    for name, content in slash_commands.items():
        cmd_path = commands_dir / f"{name}.md"
        if not cmd_path.exists():
            with open(cmd_path, "w") as f:
                f.write(content)
            cmds_added += 1

    if cmds_added > 0:
        ok(f"{cmds_added} slash commands installed: " + ", ".join(f"/{n}" for n in slash_commands))
    else:
        ok("All slash commands already installed")

    # --- Scan for existing JSONL files ---
    jsonl_dir = home / ".claude" / "projects"
    if jsonl_dir.exists():
        jsonl_files = list(jsonl_dir.rglob("*.jsonl"))
        if jsonl_files:
            info(f"\nFound {len(jsonl_files)} JSONL session files in {jsonl_dir}")
            ingest_script = root / "scripts" / "ingest_jsonl.py"
            startup_script = root / "scripts" / "startup_check.py"

            if startup_script.exists():
                if ask_yn("Import existing sessions now?"):
                    info("Running startup_check.py to ingest sessions...")
                    try:
                        result = subprocess.run(
                            [sys.executable, str(startup_script)],
                            capture_output=True, text=True, timeout=120,
                            cwd=str(root)
                        )
                        if result.returncode == 0:
                            ok("Sessions ingested")
                            if result.stdout.strip():
                                for line in result.stdout.strip().split("\n")[-5:]:
                                    info(f"  {line}")
                        else:
                            warn(f"Ingestion returned code {result.returncode}")
                            if result.stderr.strip():
                                info(f"  {result.stderr.strip()[:200]}")
                    except Exception as e:
                        warn(f"Ingestion error: {e}")
                else:
                    info("Sessions will be imported automatically on your first Claude Code session.")
            else:
                info("startup_check.py not found — sessions will be imported on first Claude Code session.")
    else:
        info("No existing JSONL files found (new Claude Code installation)")

    # --- Check for claude.ai exports ---
    imports_dir = root / "imports"
    json_files = list(imports_dir.glob("*.json")) if imports_dir.exists() else []
    if json_files:
        info(f"\nFound {len(json_files)} JSON file(s) in imports/ folder")
        import_script = root / "scripts" / "import_claude_ai.py"
        if import_script.exists():
            info(f"Run: python3 {import_script} to import them")
        else:
            info("import_claude_ai.py not found — will be available after full setup")

# ---------------------------------------------------------------------------
# Phase 8: Health Check + Next Steps
# ---------------------------------------------------------------------------

def phase_health_check(cfg):
    phase_header(9, 9, "HEALTH CHECK & NEXT STEPS")
    root = Path(cfg["root_path"])
    home = Path.home()
    checks = []

    # DB
    try:
        conn = sqlite3.connect(cfg["db_path"])
        conn.execute("SELECT 1")
        tables = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        conn.close()
        checks.append(("Database", True, f"{tables} tables"))
    except Exception as e:
        checks.append(("Database", False, str(e)))

    # Config
    config_path = root / "config.yaml"
    if config_path.exists():
        try:
            import yaml
            with open(config_path) as f:
                yaml.safe_load(f)
            checks.append(("config.yaml", True, "valid YAML"))
        except Exception as e:
            checks.append(("config.yaml", False, str(e)))
    else:
        checks.append(("config.yaml", False, "not found"))

    # Hooks
    settings_path = home / ".claude" / "settings.json"
    if settings_path.exists():
        with open(settings_path) as f:
            settings = json.load(f)
        registered = sum(1 for e in HOOK_EVENTS if e in settings.get("hooks", {}))
        if registered == 4:
            checks.append(("Hooks", True, f"all {registered} registered"))
        else:
            checks.append(("Hooks", False, f"only {registered}/4 registered"))
    else:
        checks.append(("Hooks", False, "settings.json not found"))

    # MCP server file
    server_py = root / "mcp" / "server.py"
    if server_py.exists():
        checks.append(("MCP server.py", True, "exists"))
    else:
        checks.append(("MCP server.py", False, "not found"))

    # MCP registration
    claude_json_path = home / ".claude.json"
    if claude_json_path.exists():
        with open(claude_json_path) as f:
            cj = json.load(f)
        mcp_count = sum(
            1 for p_cfg in cj.get("projects", {}).values()
            if "brain-server" in p_cfg.get("mcpServers", {})
        )
        if mcp_count > 0:
            checks.append(("MCP registered", True, f"{mcp_count} project(s)"))
        else:
            checks.append(("MCP registered", False, "not registered"))
    else:
        checks.append(("MCP registered", False, ".claude.json not found"))

    # Project directories
    missing_dirs = []
    for p in cfg["projects"]:
        pdir = root / p["folder_name"]
        if not pdir.exists():
            missing_dirs.append(p["folder_name"])
    if missing_dirs:
        checks.append(("Project dirs", False, f"missing: {', '.join(missing_dirs)}"))
    else:
        checks.append(("Project dirs", True, f"all {len(cfg['projects'])} exist"))

    # CLAUDE.md files
    missing_md = []
    for p in cfg["projects"]:
        if not (root / p["folder_name"] / "CLAUDE.md").exists():
            missing_md.append(p["folder_name"])
    if missing_md:
        checks.append(("CLAUDE.md files", False, f"missing in: {', '.join(missing_md)}"))
    else:
        checks.append(("CLAUDE.md files", True, f"all {len(cfg['projects'])} deployed"))

    # DB stats
    try:
        conn = sqlite3.connect(cfg["db_path"])
        sessions = conn.execute("SELECT COUNT(*) FROM sys_sessions").fetchone()[0]
        transcripts = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        facts = conn.execute("SELECT COUNT(*) FROM brain_facts").fetchone()[0]
        conn.close()
        checks.append(("DB contents", True, f"{sessions} sessions, {transcripts} messages, {facts} facts"))
    except Exception:
        pass

    # Print results
    print()
    all_pass = True
    for name, passed, detail in checks:
        status = green("PASS") if passed else red("FAIL")
        print(f"  {status}  {name}: {detail}")
        if not passed:
            all_pass = False

    # --- Questionnaire info ---
    print(f"\n{'='*60}")
    print(f"  PERSONALIZE YOUR BRAIN")
    print(f"{'='*60}")
    questionnaire_path = root / "brain-questionnaire.txt"
    if not questionnaire_path.exists():
        _write_questionnaire_template(questionnaire_path)
    print(f"""
  A questionnaire template has been created at:
    {questionnaire_path}

  Fill it out to teach the brain about you — your background,
  preferences, family, goals, and working style. This makes Claude
  actually know who you are across every session.

  Once you're in Claude Code, just type:  /brain-questionnaire
  Claude will help you fill it out and import your answers.
""")

    # --- Slash commands ---
    print(f"{'='*60}")
    print(f"  SLASH COMMANDS (use inside Claude Code)")
    print(f"{'='*60}")
    print(f"""
  These commands work inside any Claude Code session:

    /brain-import         Import claude.ai web conversations
    /brain-status         Check brain health and statistics
    /brain-setup          Re-run setup (add projects, fix config)
    /brain-questionnaire  Fill out or update your brain profile
""")

    # --- Next steps ---
    print(f"{'='*60}")
    print(f"  WHAT TO DO NEXT")
    print(f"{'='*60}")
    print(f"""
  1. START USING IT
     Open Claude Code in any project folder:
       cd {root / cfg['projects'][0]['folder_name']}
       claude
     The brain activates automatically — hooks fire, MCP connects,
     context loads. Nothing else to configure.

  2. IMPORT CLAUDE.AI CONVERSATIONS (optional)
     If you've been using claude.ai (the website), you can import
     your conversation history into the brain.

     Step 1 — Install the Chrome extension:
       Open Chrome and go to the Chrome Web Store:
         https://chromewebstore.google.com
       Search for "AI Chat Exporter" (by Ankit Maity).
       It's a free extension with a blue download icon.
       Click "Add to Chrome" and confirm the install.
       You'll see a small icon appear in your browser toolbar.

     Step 2 — Export conversations:
       Go to https://claude.ai and open any conversation.
       Click the AI Chat Exporter icon in your toolbar
       (top-right of Chrome, may be under the puzzle piece menu).
       Select "JSON" as the export format.
       Click "Export" — a .json file downloads to your
       Downloads folder.

       Repeat for each conversation you want to import.

     Step 3 — Move the exported files:
       Move all the .json files into your imports folder:
         mv ~/Downloads/*.json {root / 'imports'}/

     Step 4 — Import into the brain:
       Open Claude Code in any project folder and type:
         /brain-import
       Claude will walk you through assigning each conversation
       to a project. Successfully imported files are moved to
       imports/completed/ automatically.

  3. FILL OUT THE QUESTIONNAIRE (optional)
     Open Claude Code and type:  /brain-questionnaire
     Claude will help you fill out your profile interactively.

  4. CHECK BRAIN STATUS (anytime)
     Inside Claude Code, type:  /brain-status
""")

    if all_pass:
        print(f"  {green('Setup complete. Your brain is ready.')}")
    else:
        print(f"  {yellow('Setup finished with warnings. Review FAIL items above.')}")

    return all_pass


def _write_questionnaire_template(path):
    """Write a blank questionnaire template for the user to fill out."""
    template = textwrap.dedent("""\
        # Brain Questionnaire
        # Fill out as much or as little as you want.
        # Lines starting with # are comments and will be ignored.
        # After filling out, run: python3 scripts/brain-setup.py --questionnaire

        ## IDENTITY
        # Full name:
        # Nickname / preferred name:
        # Location (city, state/country):
        # Age or birth year:

        ## FAMILY
        # Spouse/partner name:
        # Children (names and ages):
        # Pets:
        # Other family members to know about:

        ## PROFESSIONAL
        # Current role/title:
        # Company/organization:
        # Industry:
        # Key skills:
        # Career background (brief):

        ## WORKING STYLE
        # Communication preference (direct, detailed, casual, formal):
        # How you like feedback (blunt, gentle, structured):
        # Decision-making style:
        # Pet peeves in AI responses:
        # What you value most in AI assistance:

        ## TECHNICAL SETUP
        # Primary OS:
        # Editor/IDE:
        # Primary programming languages:
        # Key tools you use daily:

        ## GOALS
        # Current main project(s):
        # What you're trying to accomplish this month:
        # Long-term goals:

        ## HEALTH (optional)
        # Any health context that affects your work:

        ## PREFERENCES
        # Timezone:
        # Work hours:
        # Anything else the brain should know:
    """)
    with open(path, "w") as f:
        f.write(template)


def import_questionnaire(root_path, db_path):
    """Import a filled-out questionnaire into brain_facts."""
    q_path = Path(root_path) / "brain-questionnaire.txt"
    if not q_path.exists():
        fail(f"Questionnaire not found: {q_path}")
        sys.exit(1)

    content = q_path.read_text(encoding="utf-8")
    now = datetime.now(timezone.utc).isoformat()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    current_category = "general"
    count = 0

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            # Check if it's a category header
            if line.startswith("## "):
                current_category = line[3:].strip().lower().replace(" ", "-")
            continue

        # Parse "Key: Value" format
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip().lower().replace(" ", "_")
            value = value.strip()
            if value:  # Only insert if there's a value
                # Upsert — update if same category+key exists
                existing = cursor.execute(
                    "SELECT id FROM brain_facts WHERE category=? AND key=?",
                    (current_category, key)
                ).fetchone()
                if existing:
                    cursor.execute(
                        "UPDATE brain_facts SET value=?, source='questionnaire', updated_at=? WHERE id=?",
                        (value, now, existing[0])
                    )
                else:
                    cursor.execute(
                        "INSERT INTO brain_facts (category, key, value, source, confidence, created_at, updated_at) VALUES (?, ?, ?, 'questionnaire', 'confirmed', ?, ?)",
                        (current_category, key, value, now, now)
                    )
                count += 1

    conn.commit()
    conn.close()
    ok(f"Imported {count} facts from questionnaire")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"\n{bold('claude-brain setup')}")
    print("Persistent memory system for Claude Code\n")

    # Handle --questionnaire mode
    if "--questionnaire" in sys.argv:
        # Need to find root and db paths
        script_dir = Path(__file__).resolve().parent.parent
        config_path = script_dir / "config.yaml"
        if config_path.exists():
            import yaml
            with open(config_path) as f:
                config = yaml.safe_load(f)
            root_path = config["storage"]["root_path"]
            if config["storage"]["mode"] == "synced":
                db_path = config["storage"]["local_db_path"]
            else:
                db_path = os.path.join(root_path, "claude-brain.db")
            import_questionnaire(root_path, db_path)
        else:
            fail("config.yaml not found. Run brain-setup.py first (without --questionnaire).")
            sys.exit(1)
        return

    # Normal setup flow
    pip_cmd = phase_preflight()
    phase_dependencies(pip_cmd)
    cfg = phase_projects()
    phase_directories(cfg)
    phase_database(cfg)
    phase_config(cfg)
    phase_email(cfg)
    phase_registration(cfg)
    phase_health_check(cfg)


if __name__ == "__main__":
    main()
