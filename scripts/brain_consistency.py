#!/usr/bin/env python3
"""
brain_consistency.py - Automated documentation and data consistency checker.

Checks that all counts, file references, and data integrity are consistent
across the entire brain project. Run after ANY change.

Usage:
    python3 scripts/brain_consistency.py

Exit codes: 0 = all pass, 1 = issues found
"""

import os
import re
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent

# Files to check for counts
DOCS_TO_CHECK = [
    "README.md",
    "CLAUDE_BRAIN_HOW_TO.md",
    "ARCHITECTURE.md",
    "SESSION_PROTOCOLS.md",
    "CHANGELOG.md",
    "FOLDER_SCHEMA.md",
    "CROSS_REFERENCES.md",
    "LAUNCH_PLAN.md",
    "FEATURE_PLAN.md",
    "POST_MVP_ROADMAP.md",
]

# Stale terms that should NOT appear in active docs
STALE_TERMS = [
    ("generate_summary.py", "Script was deleted. Use write_session_notes.py."),
    ("NEXT_SESSION_START_PROMPT.txt", "Replaced by NEXT_SESSION.md."),
    ("OpenRouter", "Replaced by Anthropic Max. Only valid in DUAL_SESSION_GUIDE.txt."),
]

# Files where stale terms are acceptable (historical/reference docs)
STALE_TERM_EXCEPTIONS = {
    "CHANGELOG.md",  # historical version records
    "DUAL_SESSION_GUIDE.txt",  # literally about OpenRouter
    "FOLDER_SCHEMA.md",  # references DUAL_SESSION_GUIDE.txt which mentions OpenRouter
    "MIGRATION_BASH_TO_PYTHON.md",  # historical
    "ARCHITECTURE_MERGE_PLAN.md",  # historical
    "POST_MVP_ROADMAP.md",  # historical planning
    "SESSION_PROMPTS_REFERENCE.md",  # historical
    "SAVE_EXISTING_SESSIONS.md",  # historical
    "MIKES_BRAIN_QUESTIONNAIRE.txt",  # personal data
    "dolan_status.md",  # personal
    "cc-updated.sh",  # personal script
    "DATABASE_INFO.txt",  # reference
    "CLAUDE_BRAIN_MVP_PLAN.txt",  # historical plan
}

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"


def load_db():
    """Load database path from config."""
    import yaml
    config_path = ROOT_DIR / "config.yaml"
    if not config_path.exists():
        return None
    with open(config_path) as f:
        config = yaml.safe_load(f)
    storage = config.get("storage", {})
    mode = storage.get("mode", "local")
    if mode == "synced":
        return os.path.expanduser(storage.get("local_db_path", ""))
    else:
        return os.path.join(os.path.expanduser(storage.get("root_path", "")), "claude-brain.db")


def count_actual():
    """Count actual items on disk and in DB."""
    counts = {}

    # Scripts
    scripts = list((ROOT_DIR / "scripts").glob("*.py"))
    counts["scripts"] = len(scripts)

    # Hooks
    hooks = list((ROOT_DIR / "hooks").glob("*.py"))
    counts["hooks"] = len(hooks)

    # Slash commands
    cmd_dir = Path.home() / ".claude" / "commands"
    commands = list(cmd_dir.glob("*.md")) if cmd_dir.exists() else []
    counts["commands"] = len(commands)
    counts["command_names"] = sorted(f.stem for f in commands)

    # MCP tools
    server_py = ROOT_DIR / "mcp" / "server.py"
    if server_py.exists():
        content = server_py.read_text()
        counts["mcp_tools"] = content.count("@mcp.tool")
    else:
        counts["mcp_tools"] = 0

    # Skills
    skills_dir = Path.home() / ".claude" / "skills"
    if skills_dir.exists():
        counts["skills"] = len([d for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()])
    else:
        counts["skills"] = 0

    # Database counts
    db_path = load_db()
    if db_path and os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        counts["db_sessions"] = conn.execute("SELECT count(*) FROM sys_sessions").fetchone()[0]
        counts["db_transcripts"] = conn.execute("SELECT count(*) FROM transcripts").fetchone()[0]
        counts["db_decisions"] = conn.execute("SELECT count(*) FROM decisions").fetchone()[0]
        counts["db_facts"] = conn.execute("SELECT count(*) FROM facts").fetchone()[0]
        counts["db_embeddings"] = conn.execute("SELECT count(*) FROM transcript_embeddings").fetchone()[0]
        counts["db_projects"] = conn.execute("SELECT count(*) FROM project_registry").fetchone()[0]
        counts["db_null_sources"] = conn.execute("SELECT count(*) FROM transcripts WHERE source IS NULL").fetchone()[0]
        counts["db_untagged"] = conn.execute("SELECT count(*) FROM sys_sessions WHERE tags IS NULL OR tags = ''").fetchone()[0]
        counts["db_empty_notes"] = conn.execute("SELECT count(*) FROM sys_sessions WHERE notes IS NULL OR notes = ''").fetchone()[0]

        # Source distribution
        counts["db_sources"] = {}
        for r in conn.execute("SELECT source, count(*) FROM transcripts GROUP BY source"):
            counts["db_sources"][r[0] or "NULL"] = r[1]

        # MCP registrations with brain-server
        try:
            import json
            claude_json = Path.home() / ".claude.json"
            if claude_json.exists():
                with open(claude_json) as f:
                    cj = json.load(f)
                counts["mcp_registered"] = sum(
                    1 for p in cj.get("projects", {}).values()
                    if "brain-server" in p.get("mcpServers", {})
                )
            else:
                counts["mcp_registered"] = 0
        except Exception:
            counts["mcp_registered"] = 0

        # Config projects
        import yaml
        with open(ROOT_DIR / "config.yaml") as f:
            cfg = yaml.safe_load(f)
        counts["config_projects"] = len(cfg.get("projects", []))

        # Project folders on disk
        project_folders = cfg.get("projects", [])
        counts["project_folders_exist"] = sum(
            1 for p in project_folders
            if (ROOT_DIR / p["folder_name"]).exists()
        )

        conn.close()

    return counts


def check_doc_counts(counts, issues):
    """Check that documentation files have correct counts."""
    checks = [
        ("scripts", [
            (r"\b(\d+)\s+(?:Python\s+)?scripts\b", "script count"),
        ]),
        ("commands", [
            (r"\b(\d+)\s+(?:slash\s+)?commands\b", "command count"),
            (r"\b(\d+)\s+command\s+files\b", "command file count"),
            (r"All\s+(\d+)\s+brain\s+commands", "brain command count"),
        ]),
        ("mcp_tools", [
            (r"\b(\d+)\s+read-only\s+(?:tools|functions)\b", "MCP tool count"),
            (r"\b(\d+)\s+MCP\s+tools\b", "MCP tool count"),
            (r"\b(\d+)\s+tools\s+registered\b", "MCP tool count"),
        ]),
        ("db_projects", [
            (r"\b(\d+)\s+projects?\b(?!.*folder)", "project count"),
        ]),
    ]

    for doc_name in DOCS_TO_CHECK:
        doc_path = ROOT_DIR / doc_name
        if not doc_path.exists():
            continue

        content = doc_path.read_text()
        lines = content.split("\n")

        for count_key, patterns in checks:
            expected = counts.get(count_key, 0)
            for pattern, label in patterns:
                for i, line in enumerate(lines, 1):
                    # Skip lines in version history, changelog entries, example output, and historical records
                    if any(skip in line for skip in [
                        "v0.0", "v0.1", "v0.2", "[0.",
                        "Session ", "Decision",
                        "Subject:", "BLUF", "sessions across",  # email example output
                        "3.F3", "3.C1", "3.C2",  # FEATURE_PLAN checklist items
                        "UTC timestamp", "All 4 scripts with logging",  # CHANGELOG historical
                        "All 113 session notes",  # CHANGELOG historical
                        "/brain-question",  # CHANGELOG listing of commands at a point in time
                    ]):
                        continue
                    matches = re.findall(pattern, line, re.IGNORECASE)
                    for m in matches:
                        found = int(m)
                        if found != expected and found > 0:
                            issues.append(
                                f"{doc_name}:{i}: {label} says {found}, actual is {expected}. "
                                f'Line: "{line.strip()[:80]}"'
                            )


def check_file_references(issues):
    """Check that all file paths referenced in key docs exist."""
    key_docs = ["ARCHITECTURE.md", "FOLDER_SCHEMA.md"]

    for doc_name in key_docs:
        doc_path = ROOT_DIR / doc_name
        if not doc_path.exists():
            continue

        content = doc_path.read_text()
        # Find script references like "scripts/brain_health.py"
        script_refs = re.findall(r"scripts/(\w+\.py)", content)
        for ref in script_refs:
            if not (ROOT_DIR / "scripts" / ref).exists():
                issues.append(f"{doc_name}: references scripts/{ref} but file does not exist")

        # Find hook references
        hook_refs = re.findall(r"hooks/(\w+\.py)", content)
        for ref in hook_refs:
            if not (ROOT_DIR / "hooks" / ref).exists():
                issues.append(f"{doc_name}: references hooks/{ref} but file does not exist")


def check_stale_terms(issues):
    """Check for stale terms in active documentation."""
    for doc_name in DOCS_TO_CHECK:
        if doc_name in STALE_TERM_EXCEPTIONS:
            continue
        doc_path = ROOT_DIR / doc_name
        if not doc_path.exists():
            continue

        content = doc_path.read_text()
        lines = content.split("\n")

        for term, reason in STALE_TERMS:
            for i, line in enumerate(lines, 1):
                # Skip comments, version history, and "was removed/replaced" context
                lower = line.lower()
                if any(skip in lower for skip in ["removed", "replaced", "retired", "deleted", "moved to archive", "decision", "session 4", "v0.", "[0."]):
                    continue
                if term.lower() in lower:
                    issues.append(f"{doc_name}:{i}: Stale term '{term}'. {reason}")


def check_slash_command_coverage(counts, issues):
    """Check that all slash commands appear in documentation tables."""
    cmd_names = counts.get("command_names", [])

    # Check README
    readme = ROOT_DIR / "README.md"
    if readme.exists():
        content = readme.read_text()
        for cmd in cmd_names:
            if f"/{cmd}" not in content and f"`{cmd}`" not in content:
                issues.append(f"README.md: slash command /{cmd} not listed")

    # Check HOW_TO
    howto = ROOT_DIR / "CLAUDE_BRAIN_HOW_TO.md"
    if howto.exists():
        content = howto.read_text()
        for cmd in cmd_names:
            if f"/{cmd}" not in content and f"`{cmd}`" not in content:
                issues.append(f"CLAUDE_BRAIN_HOW_TO.md: slash command /{cmd} not listed")

    # Check CROSS_REFERENCES.md
    xref = ROOT_DIR / "CROSS_REFERENCES.md"
    if xref.exists():
        content = xref.read_text()
        for cmd in cmd_names:
            if f'"{cmd}"' not in content and f"`{cmd}`" not in content:
                issues.append(f"CROSS_REFERENCES.md: slash command {cmd} not in search terms")


def check_slash_command_scripts(issues):
    """Check that every slash command references an existing script."""
    cmd_dir = Path.home() / ".claude" / "commands"
    if not cmd_dir.exists():
        return

    for cmd_file in cmd_dir.glob("*.md"):
        content = cmd_file.read_text()
        # Find script paths
        script_refs = re.findall(r"python3\s+(\S+\.py)", content)
        for ref in script_refs:
            ref_expanded = os.path.expanduser(ref)
            if not os.path.exists(ref_expanded):
                issues.append(f"~/.claude/commands/{cmd_file.name}: references {ref} but file does not exist")


def check_database_integrity(counts, issues):
    """Check database data integrity."""
    null_sources = counts.get("db_null_sources", 0)
    if null_sources > 0:
        issues.append(f"Database: {null_sources} transcripts with NULL source")

    untagged = counts.get("db_untagged", 0)
    if untagged > 0:
        issues.append(f"Database: {untagged} sessions with no tags")

    empty_notes = counts.get("db_empty_notes", 0)
    if empty_notes > 1:  # 1 is OK (current session)
        issues.append(f"Database: {empty_notes} sessions with empty notes (1 expected for current session)")

    # Check source distribution has no NULL
    sources = counts.get("db_sources", {})
    if "NULL" in sources:
        issues.append(f"Database: {sources['NULL']} transcripts with NULL source in distribution")

    # Check MCP registrations match project count
    mcp_reg = counts.get("mcp_registered", 0)
    db_projects = counts.get("db_projects", 0)
    # Subtract mike-brain (legacy, no brain-server needed)
    expected_mcp = db_projects - 1  # mike-brain excluded
    if mcp_reg < expected_mcp:
        issues.append(f"MCP: {mcp_reg} projects have brain-server, expected {expected_mcp}")

    # Check config matches DB
    config_projects = counts.get("config_projects", 0)
    if config_projects != db_projects:
        issues.append(f"Config has {config_projects} projects but DB has {db_projects}")

    # Check project folders exist
    folders_exist = counts.get("project_folders_exist", 0)
    if folders_exist != config_projects:
        issues.append(f"Only {folders_exist}/{config_projects} project folders exist on disk")


def check_jg_project(issues):
    """Check Johnny Goods project files for consistency."""
    jg_dir = ROOT_DIR / "johnny-goods"
    if not jg_dir.exists():
        return

    # Check CLAUDE.md references
    claude_md = jg_dir / "CLAUDE.md"
    if claude_md.exists():
        content = claude_md.read_text()

        # Check current step matches STEP_NUMBERS.txt
        step_match = re.search(r"CURRENT STEP:\s*(\d+)", content)
        if step_match:
            claude_step = step_match.group(1)

            step_nums = jg_dir / "STEP_NUMBERS.txt"
            if step_nums.exists():
                sn_content = step_nums.read_text()
                if f"<<< CURRENT STEP >>>" in sn_content:
                    current_match = re.search(r"Step\s+(\d+).*<<<\s*CURRENT STEP\s*>>>", sn_content)
                    if current_match and current_match.group(1) != claude_step:
                        issues.append(
                            f"JG: CLAUDE.md says step {claude_step} but STEP_NUMBERS.txt says step {current_match.group(1)}"
                        )

    # Check chapter files exist
    for i in range(1, 12):
        ch_file = jg_dir / "chapters" / f"chapter_{i:02d}.txt"
        if not ch_file.exists():
            issues.append(f"JG: Missing chapter file: {ch_file.name}")

    # Check NEXT_SESSION.md exists
    if not (jg_dir / "NEXT_SESSION.md").exists():
        issues.append("JG: NEXT_SESSION.md missing")


def check_compile(issues):
    """Check that all Python files compile."""
    import py_compile
    for folder in ["scripts", "hooks", "mcp"]:
        folder_path = ROOT_DIR / folder
        if not folder_path.exists():
            continue
        for py_file in folder_path.glob("*.py"):
            try:
                py_compile.compile(str(py_file), doraise=True)
            except py_compile.PyCompileError as e:
                issues.append(f"Compile error: {py_file.name}: {e}")


def main():
    print("\n\033[1mBrain Consistency Check\033[0m")
    print("=" * 60)

    counts = count_actual()
    issues = []

    # Run all checks
    checks = [
        ("Actual counts", lambda: None),  # just display
        ("Document counts", lambda: check_doc_counts(counts, issues)),
        ("File references", lambda: check_file_references(issues)),
        ("Stale terms", lambda: check_stale_terms(issues)),
        ("Slash command coverage", lambda: check_slash_command_coverage(counts, issues)),
        ("Slash command scripts", lambda: check_slash_command_scripts(issues)),
        ("Database integrity", lambda: check_database_integrity(counts, issues)),
        ("JG project files", lambda: check_jg_project(issues)),
        ("Python compilation", lambda: check_compile(issues)),
    ]

    # Display actual counts first
    print(f"\n  Actual counts on disk/DB:")
    print(f"    Scripts: {counts.get('scripts', '?')}")
    print(f"    Hooks: {counts.get('hooks', '?')}")
    print(f"    Slash commands: {counts.get('commands', '?')}")
    print(f"    MCP tools: {counts.get('mcp_tools', '?')}")
    print(f"    Skills: {counts.get('skills', '?')}")
    print(f"    Projects (DB): {counts.get('db_projects', '?')}")
    print(f"    Projects (config): {counts.get('config_projects', '?')}")
    print(f"    MCP registered: {counts.get('mcp_registered', '?')}")
    print(f"    Sessions: {counts.get('db_sessions', '?')}")
    print(f"    Transcripts: {counts.get('db_transcripts', '?')}")
    print(f"    Embeddings: {counts.get('db_embeddings', '?')}")
    print(f"    NULL sources: {counts.get('db_null_sources', '?')}")
    print(f"    Untagged sessions: {counts.get('db_untagged', '?')}")

    # Run checks
    for name, check_fn in checks[1:]:
        before = len(issues)
        check_fn()
        found = len(issues) - before
        status = PASS if found == 0 else f"{FAIL} ({found} issues)"
        print(f"\n  {name}: {status}")
        if found > 0:
            for issue in issues[before:]:
                print(f"    - {issue}")

    # Summary
    print(f"\n{'=' * 60}")
    if issues:
        print(f"  \033[91m{len(issues)} ISSUES FOUND\033[0m")
        sys.exit(1)
    else:
        print(f"  \033[92mALL CHECKS PASS\033[0m")
        sys.exit(0)


if __name__ == "__main__":
    main()
