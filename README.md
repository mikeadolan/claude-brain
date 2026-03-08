# claude-brain

**Persistent memory for Claude Code.** Every conversation, every decision, every fact — stored locally in SQLite, searchable via MCP, captured automatically by hooks. No cloud. No API costs. No manual saving.

---

## The Problem

Claude Code starts every session from zero. Close the terminal and everything is gone — context, decisions, preferences, project knowledge. You end up:

1. **Re-explaining who you are** every session (name, preferences, working style)
2. **Re-stating decisions** you already locked weeks ago
3. **Losing track** of what happened across sessions and projects
4. **Manually maintaining** history files that go stale
5. **Hoping Claude remembers** to save things (it doesn't — reliably)

claude-brain fixes all five.

---

## How It Works

```
Session starts
    |
    v
[session-start hook] ingests new JSONL files, loads recent session summaries
    |
    v
You type a prompt
    |
    v
[user-prompt-submit hook] searches your brain, injects top 3 relevant memories
    |
    v
Claude responds (can also query the brain on-demand via 11 MCP tools)
    |
    v
[stop hook] captures the exchange and writes it to the database
    |
    v
Session ends
    |
    v
[session-end hook] generates a session summary, backs up the database
```

**Two systems, clean split:**
- **Hooks write.** Four shell scripts fire at session lifecycle events — start, prompt, response, end. They capture data automatically. Claude doesn't need to decide to save anything.
- **MCP reads.** Ten read-only tools let Claude query the brain on demand — search transcripts, look up decisions, load your profile.

This eliminates the single biggest reliability problem in AI memory systems: depending on the AI to follow save instructions. Hooks run at the CLI layer. They always fire.

---

## Quick Start

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 2.0+
- Python 3.10+
- pip3

### Install

```bash
# Clone the repo
git clone https://github.com/mikeadolan/claude-brain.git
cd claude-brain

# Run the interactive setup
python3 scripts/brain-setup.py
```

The setup script handles everything:
1. Checks dependencies (Python, pip, Claude Code, Node.js)
2. Installs Python packages (PyYAML, MCP SDK, sentence-transformers, numpy)
3. Walks you through project creation (name, prefix, label)
4. Creates all folders and the SQLite database (11 tables, FTS5, indexes)
5. Generates your `config.yaml` (personalized, never committed to git)
6. Registers hooks in `~/.claude/settings.json`
7. Registers the MCP server with Claude Code
8. Runs a health check to verify everything works

After setup, just use Claude Code normally. The brain works in the background.

---

## What Gets Captured

| Source | How | When |
|--------|-----|------|
| Claude Code conversations | Hooks (automatic) | Every exchange, real-time |
| Claude.ai conversations | Manual import via `/brain-import` | When you export + import |
| Your profile (facts, preferences) | `/brain-questionnaire` | During setup or anytime |
| Project facts and decisions | Populated via scripts or MCP | As needed |

### Database Tables

| Table | What It Stores |
|-------|---------------|
| `transcripts` | Every message from every session (FTS5 full-text search) |
| `transcript_embeddings` | Semantic search vectors (384-dim, sentence-transformers) |
| `sys_sessions` | Session metadata (project, model, timestamps, quality score) |
| `sys_session_summaries` | Auto-generated session recaps |
| `brain_facts` | Everything about you (cross-project) |
| `brain_preferences` | How you work (cross-project) |
| `facts` | Project-specific knowledge (characters, status, timelines) |
| `decisions` | Locked decisions per project |
| `tool_results` | Tool call outputs from Claude Code |
| `sys_ingest_log` | Import tracking (prevents duplicate ingestion) |
| `project_registry` | Project name-to-prefix mapping |

---

## Hooks

Four hooks fire automatically at session lifecycle events. Registered in `~/.claude/settings.json` during setup. No configuration needed after install.

### session-start.sh
**Fires:** Once when a Claude Code session starts.
- Runs `startup_check.py` (scans for new JSONL files, ingests them, backs up DB)
- Loads recent session summaries (last 5-10 per project)
- Returns summaries as context so Claude immediately knows what happened recently

### user-prompt-submit.sh
**Fires:** Before every user message is sent to Claude.
- Extracts keywords from your prompt
- Runs FTS5 search against the brain database
- Injects top 3 relevant memories into Claude's context
- Skips short prompts (<15 chars) and filters stop words

### stop.sh
**Fires:** After every Claude response completes.
- Captures the exchange (your prompt + Claude's response)
- Writes to the database via `write_exchange.py`
- Generates and stores a semantic embedding for the message

### session-end.sh
**Fires:** When the session ends (including `/exit` and terminal close).
- Generates a session summary via `generate_summary.py`
- Backs up the database via `brain_sync.sh`

**Data safety:** If the terminal is closed without `/exit`, the stop hook has already captured every exchange up to that point. The session-start hook catches up on anything missed via JSONL reconciliation. Zero data loss.

---

## Slash Commands

Ten commands available in any Claude Code session:

| Command | What It Does |
|---------|-------------|
| `/brain-status` | Database stats — sessions, messages, per-project counts, backup status, semantic search status |
| `/brain-import` | Import a claude.ai conversation export (JSON) into the brain |
| `/brain-question` | Ask a natural language question and search the entire brain (FTS5 + semantic + facts + decisions) |
| `/brain-questionnaire` | Fill out or update your personal profile (brain_facts + brain_preferences) |
| `/brain-setup` | Re-run the setup script to add projects or fix configuration |
| `/brain-search` | Raw transcript search — returns matching results with timestamps, session IDs, and excerpts |
| `/brain-history` | Session timeline — one line per session with date, project, message count, and topic |
| `/brain-recap` | Progress report for a time range (today, week, or N days), grouped by project |
| `/brain-decide` | Fast decision lookup by number or keyword — shows full decision text and rationale |
| `/brain-export` | Export data to timestamped text files (profile, decisions, search results, sessions, weekly recap) |

---

## MCP Tools

Ten read-only tools registered as the `brain-server` MCP server. Claude calls these automatically based on your prompts — you just ask questions in plain English.

| Tool | What It Does | Example Prompt |
|------|-------------|---------------|
| `get_profile()` | Your complete profile — facts, preferences, working style | "What does the brain know about me?" |
| `get_project_state(project)` | Recent decisions + key facts for a project | "What's the current state of this project?" |
| `search_transcripts(query)` | FTS5 keyword search across all conversations | "What did we discuss about the laptop?" |
| `search_semantic(query)` | Meaning-based search using vector embeddings | "Find discussions about illegal gambling" |
| `get_session(session_id)` | Full transcript for one session | "Show me that conversation" |
| `get_recent_sessions()` | List of recent sessions with metadata | "What have we worked on this week?" |
| `get_recent_summaries()` | Auto-generated session recaps | "Summarize recent sessions" |
| `lookup_decision(project, topic)` | Search locked decisions by keyword | "What did we decide about the schema?" |
| `lookup_fact(project)` | Project-specific facts by category/key | "Who are the characters in this project?" |
| `get_status()` | Database health check | "What's the brain status?" |

### Keyword Search vs Semantic Search

**Keyword search** (`search_transcripts`) — matches exact words. Fast. Powered by SQLite FTS5.
```
"Fat Tony" → finds messages containing those exact words
```

**Semantic search** (`search_semantic`) — matches by meaning, even when words don't overlap. Powered by sentence-transformers (all-MiniLM-L6-v2) + numpy cosine similarity. Fully local.
```
"mob boss from East Harlem" → finds Fat Tony content by meaning
"illegal gambling" → finds "ran numbers on Pleasant Avenue"
```

---

## Architecture

```
claude-brain/
├── scripts/              # 15 Python/bash scripts
│   ├── brain-setup.py    # Interactive first-run installer
│   ├── startup_check.py  # JSONL ingestion + backup (called by hook)
│   ├── write_exchange.py # Real-time exchange capture (called by hook)
│   ├── generate_summary.py # Session summary generator (called by hook)
│   ├── ingest_jsonl.py   # Core JSONL parsing engine
│   ├── import_claude_ai.py # Claude.ai conversation importer
│   ├── brain_sync.sh     # Database backup with rotation
│   ├── brain_query.py    # Local search engine for /brain-question
│   ├── brain_search.py   # Raw transcript search for /brain-search
│   ├── brain_history.py  # Session timeline for /brain-history
│   ├── brain_recap.py    # Progress report for /brain-recap
│   ├── brain_decide.py   # Decision lookup for /brain-decide
│   ├── brain_export.py   # Data export for /brain-export
│   ├── status.py         # Database statistics
│   └── copy_chat_file.py # File versioning for chat sessions
├── hooks/                # 4 Claude Code lifecycle hooks
│   ├── session-start.sh
│   ├── user-prompt-submit.sh
│   ├── stop.sh
│   └── session-end.sh
├── mcp/
│   └── server.py         # MCP server (10 read-only tools)
├── config.yaml.example   # Reference config (real config is .gitignore'd)
├── exports/              # /brain-export output files
├── imports/              # Drop claude.ai exports here
│   └── completed/        # Successfully imported files move here
├── db-backup/            # Rotating database backups
├── logs/                 # Per-hostname log files
└── verification/         # Test specs and audit reports
```

**Storage:** The SQLite database lives on local disk (not in the synced folder) to prevent corruption from sync conflicts. Project files live in Dropbox (or your sync provider) for multi-machine access.

**Sync support:** Dropbox, OneDrive, Google Drive, iCloud, or local-only. The setup script asks which mode you want.

---

## Session Quality Scoring

Every session is automatically scored (-3 to +3) and tagged based on content patterns:

| Score | Meaning |
|-------|---------|
| +3 | Highly productive — completions, decisions, substantial work |
| 0 | Neutral — short or unremarkable |
| -3 | Worst — heavy rework, corrections, frustration |

**Tags:** `completions`, `decisions`, `substantial`, `debugging`, `corrections`, `rework`, `frustrated`

Use this to find patterns: "Show me my worst sessions and what went wrong" or "Compare my best and worst sessions."

---

## Multi-Machine Setup

claude-brain supports syncing between machines via Dropbox (or any cloud sync provider):

- **Project files** (scripts, hooks, config) live in the synced folder
- **Database** lives on local disk (SQLite + sync = corruption)
- **Backups** sync automatically (live in the synced folder)
- **JSONL reconciliation** at startup catches any exchanges from other machines

The setup script asks whether you want "synced" or "local" mode and configures paths accordingly.

---

## Requirements

| Dependency | Minimum Version | Notes |
|-----------|----------------|-------|
| Python | 3.10+ | 3.14 tested |
| Claude Code | 2.0+ | Must be installed and working |
| Node.js | 18+ | Required by Claude Code |
| pip3 | any | For installing Python packages |

**Python packages** (installed automatically by setup):
- `PyYAML` — config file parsing
- `mcp` — MCP server SDK
- `sentence-transformers` — semantic search embeddings (optional, ~200MB model download)
- `numpy` — cosine similarity for semantic search

---

## Configuration

The setup script generates `config.yaml` with your paths and projects. This file is in `.gitignore` — it never reaches GitHub.

See `config.yaml.example` for the full reference with documentation for every field.

Key settings:
- **Storage mode:** `synced` (Dropbox/OneDrive/etc.) or `local` (single machine)
- **Projects:** folder name, database prefix, human-readable label
- **Semantic search:** enabled/disabled (enabled by default, requires sentence-transformers)
- **Backup rotation:** how many backup copies to keep (default: 2)

---

## Importing Claude.ai Conversations

Claude.ai conversations are not captured by hooks (no hook system exists for the web UI). To import them:

1. Install the [AI Chat Exporter](https://chromewebstore.google.com/detail/ai-chat-exporter/) Chrome extension
2. On claude.ai, open a conversation and click the extension icon
3. Set these export options:
   - **Chat format:** JSON
   - **Chats:** checked
   - **Metadata:** checked
   - **Extended Thinking:** unchecked (not parsed, adds bulk)
   - **All Artifact options:** unchecked (not parsed)
4. Click **Export Current Conversation** and save the `.json` file to your `imports/` folder
5. Run `/brain-import` in Claude Code
6. Follow the prompts (select project, confirm)
7. Successfully imported files move to `imports/completed/`

---

## Security

- The database, JSONL archives, logs, backups, and personal content are all in `.gitignore`
- `config.yaml` is generated locally and never committed (contains your paths)
- The MCP server is read-only — no write operations exposed
- Everything runs locally — no cloud services, no API keys for memory, no data leaves your machine
- Hooks use absolute paths and run as your user

---

## License

MIT

---

## Contributing & Contact

- **Bug reports and feature requests:** [GitHub Issues](https://github.com/mikeadolan/claude-brain/issues)
- **Questions and discussion:** [GitHub Discussions](https://github.com/mikeadolan/claude-brain/discussions)
