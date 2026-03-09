# claude-brain

**Total recall for Claude Code.** Every conversation captured in full. Every decision locked. Every fact stored. Searchable across all your projects by keyword or meaning. Local SQLite, automatic hooks, zero cloud dependencies.

Most AI memory tools decide what's worth remembering — they extract summaries, discard context, and lose the details you'll need later. claude-brain remembers **everything**. Every message, every exchange, lossless, searchable forever.

---

## The Problem

Claude Code starts every session from zero. Close the terminal and everything is gone — context, decisions, preferences, project knowledge. You end up:

1. **Re-explaining who you are** every session
2. **Re-stating decisions** you already locked weeks ago
3. **Losing track** of what happened across sessions and projects
4. **Manually maintaining** history files that go stale

Other tools exist, but most use **lossy** approaches — recording tool usage, extracting AI-chosen summaries, or siloing memories per project. When you need to find exactly what was said three weeks ago across two different projects, those tools fail.

claude-brain takes a different approach: **capture everything, discard nothing, search anything.**

---

## How It Works

**Three systems, one brain — working across ALL your projects:**

1. **Hooks (automatic)** — Four Python scripts fire at every stage of your session. They capture every exchange in full, inject relevant memories into every prompt, generate summaries, and back up your data. You never need to say "save this." Nothing is lost, nothing is summarized away.

2. **MCP tools (automatic)** — Eleven read-only tools let Claude query the brain on demand. Searches span **every project** — ask "what did we decide about the API?" and Claude finds the answer whether it came from your web app project, your side project, or a general conversation three weeks ago.

3. **Slash commands (manual)** — Eleven `/brain-*` commands give you direct access. Search transcripts, check your session history, look up decisions, run diagnostics, import data, and more.

```
You open Claude Code
    → [session-start hook] loads recent session summaries as context

You type a prompt
    → [user-prompt-submit hook] searches your brain, injects top 3 relevant memories

Claude responds
    → [stop hook] captures the exchange to the database

You close the session
    → [session-end hook] generates a summary and backs up the database
```

This solves multiple reliability problems at once:
- **Context compaction** — Claude Code compresses older messages to save tokens. The brain has the full, uncompressed original.
- **Session crashes** — if Claude Code crashes mid-session, every exchange up to that point is already saved. Nothing is lost.
- **Save instructions** — you never need to tell Claude "remember this." Hooks fire at the CLI layer, outside of Claude's control. They always run.
- **Session boundaries** — close the terminal, switch machines, come back next week. The brain picks up where you left off.

---

## Quick Start

### What You Need

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and working
- Python 3.10 or newer
- pip3

### Install

```bash
git clone https://github.com/mikeadolan/claude-brain.git
cd claude-brain
python3 scripts/brain-setup.py
```

The setup script walks you through everything:
1. Checks your system (Python, pip, Claude Code, Node.js)
2. Installs Python packages (`pip install -r requirements.txt`)
3. Asks you to define your projects (name, prefix, label)
4. Creates folders and the SQLite database
5. Generates your personal `config.yaml` (never committed to git)
6. Registers hooks and the MCP server with Claude Code
7. Runs a health check to verify everything works

**After setup, just use Claude Code normally.** The brain works in the background.

---

## What Gets Captured

| Source | How | When |
|--------|-----|------|
| Claude Code conversations | Automatic (hooks) | Every exchange, real-time |
| Claude.ai conversations | `/brain-import` command | When you export and import |
| Your profile | `/brain-questionnaire` command | During setup or anytime |
| Project facts and decisions | Via scripts or MCP | As needed |

---

## Slash Commands

Type these in any Claude Code session:

| Command | What It Does |
|---------|-------------|
| `/brain-health` | Full 9-point diagnostic (database, hooks, MCP, backup, performance) |
| `/brain-status` | Quick stats — sessions, messages, per-project counts |
| `/brain-question` | Ask a natural language question and search the entire brain |
| `/brain-import` | Import a claude.ai conversation export |
| `/brain-questionnaire` | Fill out or update your personal profile |
| `/brain-setup` | Re-run setup to add projects or fix configuration |
| `/brain-search` | Raw transcript search with timestamps and excerpts |
| `/brain-history` | Session timeline — one line per session |
| `/brain-recap` | Progress report for a time range, grouped by project |
| `/brain-decide` | Fast decision lookup by number or keyword |
| `/brain-export` | Export brain data to text files |

---

## Searching Your Brain

**Ask Claude naturally** — it picks the right tool automatically:

```
"What did we discuss about the login page last week?"
"What was decided about the database schema?"
"Show me every session where we worked on deployment"
"What happened two days ago around 2pm?"
"Find conversations where things went wrong — what patterns do you see?"
```

**Or use slash commands** for direct access:

```
/brain-question "What do we know about the payment flow?"
/brain-search authentication error
/brain-history
/brain-recap
/brain-decide database
```

**Two search engines work together — across every project, not siloed:**
- **Keyword search** — exact word matching, fast. "payment API" finds messages with those words — from any project.
- **Semantic search** — meaning-based. "how users pay for things" finds payment API discussions even when those exact words never appear. Filter by project or search everything at once.

**Post-mortem and lessons learned** — because the brain captures everything, you can ask Claude to analyze your own work patterns:
```
"Look at my worst sessions and tell me what went wrong"
"What mistakes keep repeating across my projects?"
"Compare my best and worst sessions — what patterns do you see?"
```

**Proactive email digests** — scheduled summaries delivered to your inbox:
- Daily recaps of what you worked on across all projects
- Weekly progress reports with decisions made and next steps
- Dormant project alerts when a project hasn't been touched in weeks
- Pattern detection — "you've had 4 frustrated sessions this week, all during late-night coding"

---

## MCP Tools

Eleven read-only tools registered as the `brain-server`. Claude calls these automatically — you just ask questions.

| Tool | What It Does |
|------|-------------|
| `get_profile` | Your complete profile — facts, preferences, working style |
| `get_project_state` | Recent decisions + key facts for a project |
| `search_transcripts` | Keyword search across all conversations |
| `search_semantic` | Meaning-based search using vector embeddings |
| `get_session` | Full transcript of a specific session |
| `get_recent_sessions` | List recent sessions with metadata |
| `get_recent_summaries` | Auto-generated session recaps |
| `lookup_decision` | Search locked decisions by keyword |
| `lookup_fact` | Project-specific facts by category |
| `get_status` | Database health check |
| `get_schema` | Full database schema and row counts |

---

## Folder Structure

```
claude-brain/
├── hooks/               # 4 lifecycle hooks (automatic)
│   ├── session-start.py
│   ├── user-prompt-submit.py
│   ├── stop.py
│   └── session-end.py
├── scripts/             # 16 Python scripts
│   ├── brain-setup.py   # Interactive installer
│   └── ...              # Query, import, health, backup scripts
├── mcp/
│   └── server.py        # MCP server (11 read-only tools)
├── config.yaml.example  # Reference config (real config is gitignored)
├── requirements.txt     # Python dependencies
├── imports/             # Drop claude.ai exports here
├── exports/             # /brain-export output
├── db-backup/           # Rotating database backups
└── logs/                # Per-hostname log files
```

**Storage:** The SQLite database lives on local disk to prevent corruption. If you use multiple machines, the project files (scripts, hooks, config) can live in a synced folder like Dropbox — see [Multi-Machine Setup](#multi-machine-setup) below.

---

## Multi-Machine Setup

claude-brain supports syncing between machines via Dropbox, OneDrive, Google Drive, or iCloud:

- **Project files** (scripts, hooks, config) sync via your cloud provider
- **Database** stays on local disk (SQLite + cloud sync = corruption risk)
- **Backups** sync automatically (stored in the project folder)
- **JSONL reconciliation** at startup catches exchanges from other machines

The setup script asks whether you want "synced" or "local" mode.

---

## Importing Claude.ai Conversations

Claude.ai conversations aren't captured by hooks. To import them:

1. Install the [AI Chat Exporter](https://chromewebstore.google.com/detail/ai-chat-exporter/) Chrome extension
2. Open a conversation on claude.ai, click the extension icon
3. Export settings: **JSON** format, **Chats** and **Metadata** checked, everything else unchecked
4. Save the `.json` file to your `imports/` folder
5. In Claude Code, type `/brain-import` and follow the prompts
6. Imported files move to `imports/completed/`

---

## Requirements

| Dependency | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | Tested on 3.13 and 3.14 |
| Claude Code | 2.0+ | Must be installed and working |
| Node.js | 18+ | Required by Claude Code |
| pip3 | any | For installing Python packages |

**Python packages** (installed by setup or `pip install -r requirements.txt`):
- `PyYAML` — config file parsing
- `mcp` — MCP server SDK
- `sentence-transformers` — semantic search embeddings (optional, ~80MB model download)
- `numpy` — cosine similarity for semantic search

---

## Known Limitations

| Limitation | Detail |
|-----------|--------|
| **Single-user** | One person, one database. No multi-user support. |
| **No auto-capture from claude.ai** | Manual export + `/brain-import` required. |
| **Semantic search cold-start** | First query takes ~4-5s to load the model. Fast after that. |
| **Keyword search is exact-match** | Typos in keyword search won't match (e.g., "sesion" won't find "session"). Semantic search can still find what you mean — it matches by concept, not spelling. |
| **No cross-machine real-time DB sync** | DB is local. Project files sync; database doesn't. |

See `POST_MVP_ROADMAP.md` for the full list and planned fixes.

---

## Security

- Database, archives, logs, backups, and personal content are all in `.gitignore`
- `config.yaml` is generated locally and never committed
- The MCP server is read-only — no write operations exposed
- Everything runs locally — no cloud services, no data leaves your machine

---

## Troubleshooting

**Claude isn't using the brain tools:**
Run `claude mcp list` — you should see `brain-server`. If missing: `claude mcp add brain-server python3 /path/to/mcp/server.py`

**Hooks aren't firing:**
Check `~/.claude/settings.json` for hook entries. Check `logs/` for error output.

**Search returns no results:**
Run `/brain-status` to verify messages exist. Try fewer keywords. Remove the project filter.

**Full diagnostic:** Run `/brain-health` for a 9-point system check.

See `CLAUDE_BRAIN_HOW_TO.md` for the complete troubleshooting guide.

---

## License

MIT

---

## Contributing & Contact

- **Bug reports and feature requests:** [GitHub Issues](https://github.com/mikeadolan/claude-brain/issues)
- **Questions and discussion:** [GitHub Discussions](https://github.com/mikeadolan/claude-brain/discussions)
