#!/usr/bin/env python3
"""
add-project.py - Add a new project to an existing claude-brain installation.

Reads your existing config.yaml, asks for the new project details, and does
only what's needed: config update, folder creation, CLAUDE.md, DB registration,
MCP server registration. Does NOT re-run full setup.

Usage:
    python3 scripts/add-project.py
"""

import json
import os
import re
import sqlite3
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path

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

def ok(msg):
    print(f"  {green('OK')} {msg}")

def fail(msg):
    print(f"  {red('FAIL')} {msg}")

def warn(msg):
    print(f"  {yellow('WARN')} {msg}")

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
    if len(parts) >= 2:
        candidate = "".join(p[0] for p in parts[:3])
    else:
        candidate = name[:3]

    if candidate not in existing_prefixes:
        return candidate

    for length in range(2, min(len(name.replace("-", "")), 5)):
        flat = name.replace("-", "")
        candidate = flat[:length]
        if candidate not in existing_prefixes:
            return candidate

    base = name.replace("-", "")[:2]
    for i in range(2, 100):
        candidate = f"{base}{i}"
        if candidate not in existing_prefixes:
            return candidate
    return base

# ---------------------------------------------------------------------------
# Load existing config
# ---------------------------------------------------------------------------

def load_config():
    """Load existing config.yaml. Returns (config_dict, config_path)."""
    script_dir = Path(__file__).resolve().parent.parent
    config_path = script_dir / "config.yaml"

    if not config_path.exists():
        fail(f"config.yaml not found at {config_path}")
        info("Run brain-setup.py first to create your initial installation.")
        sys.exit(1)

    import yaml
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    return cfg, config_path

# ---------------------------------------------------------------------------
# CLAUDE.md template
# ---------------------------------------------------------------------------

def generate_claude_md(project, cfg):
    """Generate CLAUDE.md content for a project folder."""
    root = cfg["storage"]["root_path"]
    if cfg["storage"]["mode"] == "synced":
        db_path = cfg["storage"]["local_db_path"]
    else:
        db_path = os.path.join(root, "claude-brain.db")

    return textwrap.dedent(f"""\
        # {project['label']}

        PROJECT: {project['folder_name']}
        PREFIX: {project['prefix']}

        ## RULE #1 - USE THE BRAIN FIRST. ALWAYS.
        **You have a brain with persistent memory across sessions. USE IT before doing anything substantive.**
        - Before proposing a plan, starting a task, debugging, answering questions, or suggesting changes: **search the brain.**
        - Use `search_transcripts`, `search_semantic`, `get_recent_summaries`, `lookup_decision`, `lookup_fact`.
        - Files tell you WHAT exists. The brain tells you WHY -- strategic context, prior decisions, rejected approaches.
        - Not using the brain is the same as not having it.
        - If you have a web search MCP available, use it alongside the brain for external context.

        ## BRAIN CONNECTION
        MCP server "brain-server" provides persistent memory.
        Database: {db_path}

        ## SESSION START
        1. **Search the brain** -- query search_transcripts + get_recent_summaries for this project. This is step ONE.
        2. Call get_profile() and get_project_state('{project['prefix']}') to load working context.
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

        ## SESSION START PROTOCOL
        When a session starts, you receive automatic context from the session-start hook
        (last session notes, NEXT_SESSION.md, recent summaries). Before responding to the user:
        1. Search the brain: search_transcripts + get_recent_summaries for project '{project['prefix']}'
        2. Review the injected context (last session notes, NEXT_SESSION.md if present)
        3. SHOW unfinished items and next-session notes to the user prominently (they must SEE and react)
        4. Output this checklist (every row must show DONE):

        | Start-Session Checklist              | Status   |
        |--------------------------------------|----------|
        | Brain searched                       | DONE     |
        | Last session notes reviewed          | DONE     |
        | Unfinished items SHOWN to user       | DONE     |
        | Next-session notes SHOWN to user     | DONE     |

        If any row cannot show DONE, stop and fix it before proceeding.

        ## SESSION END PROTOCOL
        When the user says "end session" (or similar), complete ALL steps:
        1. Write session notes to the database:
           python3 {root}/scripts/write_session_notes.py --notes "<what was done, decisions, next steps>"
        2. Update project summary (if significant progress):
           python3 {root}/scripts/write_project_summary.py --prefix {project['prefix']} --summary "<current state>"
        3. Ask the user: "Anything you want Claude to know next session?"
        4. Write their answer (plus session summary) to NEXT_SESSION.md in this project folder
        5. Output this checklist (every row must show DONE):

        | End-Session Checklist                | Status   |
        |--------------------------------------|----------|
        | Session notes written to DB          | DONE     |
        | Project summary updated              | DONE     |
        | NEXT_SESSION.md written              | DONE     |

        If any row cannot show DONE, stop and fix it before proceeding.

        ## SLASH COMMANDS
        Type these in Claude Code for direct access:
        /brain-question, /brain-search, /brain-history, /brain-recap, /brain-decide,
        /brain-health, /brain-status, /brain-import, /brain-questionnaire, /brain-setup,
        /brain-export

        ## FILE VERSIONING
        After creating or modifying any file, run:
        python3 {root}/scripts/copy_chat_file.py \\
          [filepath] --project {project['prefix']} --session $SESSION_ID
    """)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print(f"\n{bold('claude-brain -- Add Project')}")
    print("Add a new project to your existing brain installation.\n")

    # Step 1: Load existing config
    cfg, config_path = load_config()
    root = Path(cfg["storage"]["root_path"])

    existing_projects = cfg.get("projects", [])
    existing_names = {p["folder_name"] for p in existing_projects}
    existing_prefixes = {p["prefix"] for p in existing_projects}

    print(f"  Found {len(existing_projects)} existing project(s):")
    for p in existing_projects:
        print(f"    {p['prefix']:5s} {p['folder_name']:20s} {p.get('label', '')}")
    print()

    # Step 2: Get new project details
    name_pattern = re.compile(r'^[a-z][a-z0-9-]*[a-z0-9]$|^[a-z]$')

    while True:
        name = input("  New project folder name: ").strip().lower()
        if not name:
            info("Cancelled.")
            return
        if not name_pattern.match(name):
            warn("Invalid. Use lowercase letters, numbers, hyphens. Must start with a letter.")
            continue
        if name in existing_names:
            warn(f"'{name}' already exists.")
            continue
        break

    prefix = generate_prefix(name, existing_prefixes)
    label = ask(f"Label for '{name}'", name.replace("-", " ").title())
    shown_prefix = ask(f"Prefix for '{name}'", prefix)
    if shown_prefix != prefix:
        if shown_prefix in existing_prefixes:
            warn(f"Prefix '{shown_prefix}' already in use. Using '{prefix}'.")
            shown_prefix = prefix
        prefix = shown_prefix

    new_project = {
        "folder_name": name,
        "prefix": prefix,
        "label": label,
    }

    print(f"\n  Will add: {bold(name)} (prefix: {prefix}, label: {label})")
    if not ask_yn("Proceed?"):
        info("Cancelled.")
        return

    # Step 3: Create folder + chat-files/
    project_dir = root / name
    chat_dir = project_dir / "chat-files"
    chat_dir.mkdir(parents=True, exist_ok=True)
    ok(f"Created {project_dir}/")

    # Step 4: Write CLAUDE.md
    claude_md_path = project_dir / "CLAUDE.md"
    write_it = True
    if claude_md_path.exists():
        warn("CLAUDE.md already exists in this folder.")
        write_it = ask_yn("Overwrite?", "n")

    if write_it:
        with open(claude_md_path, "w") as f:
            f.write(generate_claude_md(new_project, cfg))
        ok("CLAUDE.md written")
    else:
        ok("CLAUDE.md skipped (kept existing)")

    # Step 5: Update config.yaml
    import yaml

    cfg["projects"].append(new_project)

    if "jsonl_project_mapping" not in cfg:
        cfg["jsonl_project_mapping"] = {}
    cfg["jsonl_project_mapping"][name] = prefix

    with open(config_path, "w") as f:
        f.write("# claude-brain Configuration File\n")
        f.write("# Last updated by add-project.py on " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
        f.write("# See config.yaml.example for documentation of all options.\n\n")
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    ok(f"config.yaml updated (added {name})")

    # Step 6: Register in project_registry DB table
    if cfg["storage"]["mode"] == "synced":
        db_path = cfg["storage"]["local_db_path"]
    else:
        db_path = os.path.join(cfg["storage"]["root_path"], "claude-brain.db")

    db_path = os.path.expanduser(db_path)

    if os.path.exists(db_path):
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        conn = sqlite3.connect(db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO project_registry (folder_name, prefix, label, status, health, created_at) "
                "VALUES (?, ?, ?, 'active', 'green', ?)",
                (name, prefix, label, now)
            )
            conn.commit()
            ok(f"project_registry updated (prefix: {prefix})")
        except Exception as e:
            warn(f"DB registration failed: {e}")
            info("  You can fix this later by re-running brain-setup.py")
        finally:
            conn.close()
    else:
        warn(f"Database not found at {db_path} -- skipping DB registration")

    # Step 7: Register MCP server in ~/.claude.json
    home = Path.home()
    claude_json_path = home / ".claude.json"
    project_path_str = str(project_dir)

    if claude_json_path.exists():
        with open(claude_json_path) as f:
            claude_json = json.load(f)
    else:
        claude_json = {}

    projects_section = claude_json.get("projects", {})
    server_path = str(root / "mcp" / "server.py")
    brain_mcp_entry = {
        "type": "stdio",
        "command": "python3",
        "args": [server_path],
        "env": {}
    }

    # Create project entry if needed
    if project_path_str not in projects_section:
        projects_section[project_path_str] = {
            "allowedTools": [],
            "mcpContextUris": [],
            "mcpServers": {},
            "enabledMcpjsonServers": [],
            "disabledMcpjsonServers": [],
            "hasTrustDialogAccepted": False,
        }

    # Register brain-server
    mcp_servers = projects_section[project_path_str].get("mcpServers", {})
    if "brain-server" not in mcp_servers:
        mcp_servers["brain-server"] = brain_mcp_entry
        projects_section[project_path_str]["mcpServers"] = mcp_servers
        ok("brain-server MCP registered")
    else:
        ok("brain-server MCP already registered")

    # Step 8: Detect and offer other MCP servers from root path
    root_str = str(root)
    other_mcps = {}
    if root_str in projects_section:
        root_mcp = projects_section[root_str].get("mcpServers", {})
        for mcp_name, mcp_config in root_mcp.items():
            if mcp_name != "brain-server":
                other_mcps[mcp_name] = mcp_config

    if other_mcps:
        print(f"\n  Found {len(other_mcps)} other MCP server(s) on your root project:")
        for mcp_name in other_mcps:
            print(f"    - {mcp_name}")

        if ask_yn(f"Register these for {name} too?"):
            for mcp_name, mcp_config in other_mcps.items():
                if mcp_name not in mcp_servers:
                    mcp_servers[mcp_name] = mcp_config
                    ok(f"{mcp_name} registered")
                else:
                    ok(f"{mcp_name} already registered")
            projects_section[project_path_str]["mcpServers"] = mcp_servers

    # Write ~/.claude.json
    claude_json["projects"] = projects_section
    with open(claude_json_path, "w") as f:
        json.dump(claude_json, f, indent=4)
    ok("~/.claude.json updated")

    # Done
    print(f"\n{'='*60}")
    print(f"  {green('Done!')} Project '{name}' added to claude-brain.")
    print(f"{'='*60}")
    print(f"\n  To use the brain from this project:")
    print(f"    cd {project_dir}")
    print(f"    claude")
    print(f"\n  The brain will work automatically -- hooks capture data,")
    print(f"  MCP tools let Claude query your memory, CLAUDE.md provides")
    print(f"  instructions. Just start working.\n")


if __name__ == "__main__":
    main()
