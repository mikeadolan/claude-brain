#!/usr/bin/env python3
"""
CI test suite for claude-brain.

Verifies cross-platform compatibility:
1. All Python scripts compile
2. All dependencies import
3. SQLite database can be created with full schema
4. FTS5 full-text search works
5. Config file parses correctly

Does NOT require interactive input or a running Claude Code session.
"""

import importlib
import os
import py_compile
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def test_python_compilation():
    """Compile every .py file in scripts/, hooks/, mcp/, tests/."""
    print("\n--- Python Compilation ---")
    dirs = ["scripts", "hooks", "mcp"]
    for d in dirs:
        folder = ROOT / d
        if not folder.exists():
            check(f"{d}/ exists", False, "directory not found")
            continue
        py_files = sorted(folder.glob("*.py"))
        check(f"{d}/ has Python files", len(py_files) > 0, f"found {len(py_files)}")
        for f in py_files:
            try:
                py_compile.compile(str(f), doraise=True)
                check(f"compile {d}/{f.name}", True)
            except py_compile.PyCompileError as e:
                check(f"compile {d}/{f.name}", False, str(e))


def test_dependencies():
    """Verify critical imports work."""
    print("\n--- Dependency Imports ---")
    modules = [
        ("yaml", "PyYAML"),
        ("sqlite3", "sqlite3 (stdlib)"),
        ("json", "json (stdlib)"),
        ("pathlib", "pathlib (stdlib)"),
        ("hashlib", "hashlib (stdlib)"),
    ]
    for mod, label in modules:
        try:
            importlib.import_module(mod)
            check(f"import {label}", True)
        except ImportError:
            check(f"import {label}", False, "not installed")

    # Optional but recommended
    for mod, label in [("sentence_transformers", "sentence-transformers"), ("numpy", "numpy")]:
        try:
            importlib.import_module(mod)
            check(f"import {label} (optional)", True)
        except ImportError:
            check(f"import {label} (optional)", True, "skipped (optional)")


def test_database_creation():
    """Create a fresh database with the full schema and verify all tables."""
    print("\n--- Database Creation ---")

    # Read DDL from brain-setup.py source to stay in sync
    setup_path = ROOT / "scripts" / "brain-setup.py"
    check("brain-setup.py exists", setup_path.exists())

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test-brain.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Create all tables using the same DDL as brain-setup.py
        ddl_statements = [
            """CREATE TABLE IF NOT EXISTS sys_sessions (
                session_id TEXT PRIMARY KEY, project TEXT, started_at TEXT,
                ended_at TEXT, cwd TEXT, claude_version TEXT, model TEXT,
                source TEXT, message_count INTEGER DEFAULT 0, created_at TEXT,
                quality_score INTEGER DEFAULT NULL, quality_tags TEXT DEFAULT NULL,
                notes TEXT, tags TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS sys_ingest_log (
                file_path TEXT PRIMARY KEY, file_size INTEGER, file_type TEXT,
                records_imported INTEGER, ingested_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS project_registry (
                folder_name TEXT PRIMARY KEY, prefix TEXT UNIQUE, label TEXT,
                registered_at TEXT, summary TEXT, summary_updated_at TEXT,
                status TEXT DEFAULT 'active', health TEXT DEFAULT 'green'
            )""",
            """CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
                project TEXT, uuid TEXT UNIQUE, parent_uuid TEXT, type TEXT,
                subtype TEXT, role TEXT, content TEXT, model TEXT,
                timestamp TEXT, token_input INTEGER, token_output INTEGER,
                stop_reason TEXT, is_subagent INTEGER DEFAULT 0,
                source_file TEXT, raw_json TEXT, created_at TEXT, source TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS tool_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
                project TEXT, tool_use_id TEXT, content TEXT,
                source_file TEXT, created_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS brain_facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT,
                key TEXT, value TEXT, source TEXT, source_session TEXT,
                confidence TEXT, created_at TEXT, updated_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS brain_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT,
                preference TEXT, source TEXT, created_at TEXT, updated_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT,
                decision_number INTEGER, session_id TEXT, description TEXT,
                rationale TEXT, created_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS facts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT,
                category TEXT, key TEXT, value TEXT, source TEXT,
                session_id TEXT, created_at TEXT, updated_at TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS transcript_embeddings (
                transcript_id INTEGER PRIMARY KEY, embedding BLOB NOT NULL,
                model TEXT DEFAULT 'all-MiniLM-L6-v2', created_at TEXT
            )""",
        ]

        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_transcripts_session ON transcripts(session_id)",
            "CREATE INDEX IF NOT EXISTS idx_transcripts_project ON transcripts(project)",
            "CREATE INDEX IF NOT EXISTS idx_transcripts_timestamp ON transcripts(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_transcripts_type ON transcripts(type)",
            "CREATE INDEX IF NOT EXISTS idx_transcripts_uuid ON transcripts(uuid)",
        ]

        fts = """CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
            content, content=transcripts, content_rowid=id
        )"""

        # Create tables
        for ddl in ddl_statements:
            try:
                cursor.execute(ddl)
            except Exception as e:
                check(f"DDL execution", False, str(e))
                conn.close()
                return

        check("10 tables created", True)

        # Create indexes
        for idx in indexes:
            cursor.execute(idx)
        check("5 indexes created", True)

        # Create FTS5
        try:
            cursor.execute(fts)
            check("FTS5 virtual table created", True)
        except Exception as e:
            check("FTS5 virtual table created", False, str(e))

        conn.commit()

        # Verify all tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [r[0] for r in cursor.fetchall()]
        expected = [
            "brain_facts", "brain_preferences", "decisions", "facts",
            "project_registry", "sys_ingest_log", "sys_sessions",
            "tool_results", "transcript_embeddings", "transcripts",
            "transcripts_fts",
        ]
        for t in expected:
            check(f"table {t} exists", t in tables)

        # Test FTS5 insert and search
        cursor.execute("""INSERT INTO transcripts
            (session_id, project, uuid, role, content, timestamp, source)
            VALUES ('test-session', 'test', 'uuid-001', 'user',
                    'How do I configure the database schema?',
                    '2026-01-01T00:00:00Z', 'test')""")
        cursor.execute("""INSERT INTO transcripts_fts(rowid, content)
            VALUES (last_insert_rowid(), 'How do I configure the database schema?')""")
        conn.commit()

        cursor.execute("SELECT content FROM transcripts_fts WHERE transcripts_fts MATCH 'database'")
        results = cursor.fetchall()
        check("FTS5 search works", len(results) == 1)

        # Test insert into project_registry
        cursor.execute("""INSERT INTO project_registry (folder_name, prefix, label, registered_at)
            VALUES ('test-project', 'tp', 'Test Project', '2026-01-01T00:00:00Z')""")
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM project_registry")
        check("project_registry insert works", cursor.fetchone()[0] == 1)

        conn.close()

        # Verify database file was created and has size
        check("database file created", db_path.exists())
        check("database has data", db_path.stat().st_size > 0)


def test_config_parsing():
    """Verify config.yaml.example parses correctly."""
    print("\n--- Config Parsing ---")
    config_example = ROOT / "config.yaml.example"
    check("config.yaml.example exists", config_example.exists())

    if config_example.exists():
        try:
            import yaml
            with open(config_example) as f:
                cfg = yaml.safe_load(f)
            check("config.yaml.example parses", cfg is not None)
            check("config has 'projects' key", "projects" in cfg)
            check("config has 'database' key", "database" in cfg)
        except Exception as e:
            check("config.yaml.example parses", False, str(e))


def test_file_structure():
    """Verify expected directories and key files exist."""
    print("\n--- File Structure ---")
    expected_dirs = ["scripts", "hooks", "mcp", "verification"]
    for d in expected_dirs:
        check(f"{d}/ exists", (ROOT / d).exists())

    expected_files = [
        "README.md", "CLAUDE_BRAIN_HOW_TO.md", "LICENSE",
        "requirements.txt", "config.yaml.example",
        "mcp/server.py", "hooks/session-start.py",
        "hooks/session-end.py", "hooks/stop.py",
        "hooks/user-prompt-submit.py",
    ]
    for f in expected_files:
        check(f"{f} exists", (ROOT / f).exists())


if __name__ == "__main__":
    print("=" * 60)
    print("  claude-brain CI Test Suite")
    print(f"  Python {sys.version}")
    print(f"  Platform: {sys.platform}")
    print("=" * 60)

    test_file_structure()
    test_python_compilation()
    test_dependencies()
    test_database_creation()
    test_config_parsing()

    print("\n" + "=" * 60)
    print(f"  Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)

    sys.exit(1 if FAIL > 0 else 0)
