# claude-brain

[![CI Tests](https://github.com/mikeadolan/claude-brain/actions/workflows/test-setup.yml/badge.svg)](https://github.com/mikeadolan/claude-brain/actions/workflows/test-setup.yml)

**Tested on:** macOS, Ubuntu, Windows (automated CI) | Fedora 43 (primary development)

**Introducing claude-brain for Claude Code - Your AI finally has a real memory.** Not just RAG, RAG and beyond. 100% lossless recall across every session and every project, no silos. Local SQLite. Keyword, semantic, and fuzzy search across everything. Emails you a daily briefing, weekly portfolio, and project status reports - no other tool does this. Zero cloud dependencies. Your data never leaves your machine. Zero token burn. Unlimited potential.

**Watch the explainer video:** [claude-brain in 85 seconds](https://youtu.be/yf1RIo1MtBI)

---

## The Pain

Claude Code starts every session from zero. Close the terminal and everything is gone.

- **Re-explain who you are** every single session
- **Re-state decisions** you already locked weeks ago
- **Lose track** of what happened across sessions and projects
- **MEMORY.md has a 200-line cap** - Claude's built-in memory is a Post-It note
- **Context compaction throws away** your earlier conversation mid-session
- **Projects are siloed** - what you discussed in one project is invisible in another

Other tools exist, but most use lossy approaches - extracting AI-chosen summaries, discarding context, siloing memories per project. When you need to find exactly what was said three weeks ago across two different projects, those tools fail.

---

## RAG and Beyond

claude-brain is a RAG system - but that's just one layer. Here's what "beyond" means:

| What | How |
|------|-----|
| **RAG (context injection)** | Every prompt gets relevant memories injected automatically - hooks search your history before Claude sees your message |
| **Full lossless capture** | Other tools extract "memories" and throw away the raw data. We keep every word. Nothing summarized away, nothing lost. |
| **Cross-project search** | Ask about a decision from your API project while working on your frontend. No silos - one brain across everything. |
| **Three search modes** | Keyword (exact), semantic (meaning-based), and fuzzy (typo-correcting). "sesion" auto-corrects to "session" before the query runs. |
| **Structured knowledge** | Numbered decisions, project facts, session quality scores, project health tracking - not just unstructured text blobs |
| **Proactive intelligence** | The brain emails YOU. Daily standups, weekly portfolios, dormant project alerts. RAG waits for you to ask. This doesn't. |
| **100% local** | SQLite on your machine. No API calls for search. No cloud. No cost. No one sees your data. Zero token burn. |

**Beyond Auto Memory.** Claude Code's built-in auto memory stores project preferences in a markdown file. claude-brain goes further: full lossless capture of every conversation, structured decisions and facts, cross-project search, multi-platform import (ChatGPT, Gemini, Claude.ai), and semantic search across your complete history. Auto memory is a notepad. This is the database.

---

## See It In Action

**Your Monday 8am inbox:**

```
Subject: [Weekly] Mar 05-Mar 12: 47 sessions across 3 projects

This week you logged 47 sessions across 3 projects (up 12% from
last week). Most active: myapp (28 sessions). Alert: docs dormant
for 5 days.

         This Week   Last Week   Change
Sessions     47          42       +12%
Messages   8,241       6,893      +20%
Decisions     5           3       +67%

Project    Health  Sessions  Messages  Trend
myapp      [GREEN]    28      5,104    +15%
api        [GREEN]    12      2,241     -8%
docs       [RED]       0          0   dormant
```

**Your daily standup (every weekday 8am):**

```
Subject: [brain] Daily: 3 sessions, 892 msgs | Mar 12

[ON TRACK] myapp
  Pick Up Here: Implement rate limiting on /api/upload endpoint
  Blockers: CI pipeline timeout on integration tests
  In Progress: Auth refactor (80%), rate limiting (not started)

[AT RISK] api-service
  Pick Up Here: Fix flaky CI tests blocking deploy
  Yesterday: Investigated CI timeout issue (1 session, 341 msgs)

No Activity Yesterday:
  docs - quiet for 5 days. Next: Update API reference for v2 endpoints
```

**Three email templates** - daily standup, weekly digest, project deep dive. Dark mode optional. Schedule via cron and forget.

---

## Quick Start

![Install Demo](assets/brain-install-demo.gif)

**One-line install** (checks prerequisites, clones, installs dependencies, runs setup):

```bash
curl -fsSL https://raw.githubusercontent.com/mikeadolan/claude-brain/main/install.sh | bash
```

**Manual install** (if you prefer to do it yourself):

```bash
git clone https://github.com/mikeadolan/claude-brain.git
cd claude-brain
python3 scripts/brain-setup.py
```

The setup walks you through everything - projects, database, hooks, MCP, email, health check.

**Requirements:** Python 3.10+, Claude Code 2.0+, pip3.

### Updating

The brain checks for updates automatically on every session start. When an update is available, you will see:

```
Brain Update Available
To update: cd /your/install/path && git pull && pip3 install -r requirements.txt
```

The path shown is your actual install location. Copy and paste the command to update. Updates never happen automatically.

### Working in a Project

After setup, each project has its own folder inside the claude-brain directory. To start working:

```bash
cd ~/path/to/claude-brain/my-website/   # go to any project folder
claude                                   # start Claude Code -- brain is live
```

That's all you need to do. The brain works automatically in the background:
- Your last session's notes are loaded
- Every message you send is searched against your full history
- Claude can query decisions, facts, and transcripts from all projects
- Everything you discuss is captured to the database in real-time

**Multiple projects at once:** Open a second terminal or editor window, navigate to a different project folder, and run `claude` again. Both sessions have independent conversations with full brain access. See `CLAUDE_BRAIN_HOW_TO.md` Section 10 for the complete multi-project workflow.

---

## Three Pillars

### 1. Hooks - Automatic Capture

Four Python scripts fire at every stage of your session. You never need to say "save this."

```
You open Claude Code
    → session-start hook loads context + project summaries

You type a prompt
    → user-prompt-submit hook searches brain, injects top matches

Claude responds
    → stop hook captures the exchange to the database

You close the session
    → session-end hook backs up the database
```

### 2. Search - Three Engines, Zero Silos

Every search works across ALL your projects:

- **Keyword:** exact word matching, fast - "payment API" finds messages with those words from any project
- **Semantic:** meaning-based - "how users pay" finds payment discussions even when those words never appear
- **Fuzzy:** typo-correcting - "sesion" auto-corrects to "session" before the query runs

```
"What did we discuss about the login page last week?"
"What was decided about the database schema?"
"Show me every session where we worked on deployment"
"Find conversations where things went wrong - what patterns do you see?"
```

### 3. Email Digests - The Brain Reaches Out

No other AI memory tool does this. Schedule and forget - your inbox becomes your dashboard.

| Template | Command | What You Get |
|----------|---------|-------------|
| **Daily Standup** | `--daily` | Per-project "Pick Up Here" with next steps, blockers, accomplishments, 7-day trend |
| **Weekly Digest** | (default) | Executive summary, week-over-week trends, health portfolio, top accomplishments, dormant alerts |
| **Project Deep Dive** | `--project mb` | Full status: health metrics, in-progress, risks, decisions, architecture |

**10 use cases:**

| Use Case | What It Does |
|----------|-------------|
| **Morning Kickoff** | Daily standup at 8am - know exactly where you left off |
| **Stakeholder Update** | Forward the weekly digest to a manager or collaborator |
| **Dormant Project Rescue** | Alerts when a project goes quiet |
| **Decision Audit Trail** | Weekly record of every decision made |
| **Sprint Retrospective** | End-of-sprint deep dive - what got done, what's blocked |
| **Onboarding a Collaborator** | Forward the project deep dive - instant context |
| **Accountability Partner** | Auto-send weekly digest to a friend or mentor |
| **Personal Changelog** | Monthly digest archived to email |
| **Context Resume** | After 48+ hours away - here's where everything stands |
| **Portfolio View** | One email, all projects at a glance |

---

## Four Data Sources

No other AI memory tool does this. One brain, every platform:

| Source | How | Format |
|--------|-----|--------|
| **Claude Code** | Automatic (hooks) | Real-time, every exchange captured |
| **Claude.ai** | `/brain-import` + Chrome extension | JSON export per conversation |
| **ChatGPT** | `import_chatgpt.py` + data export | Full account export from OpenAI |
| **Gemini** | `import_gemini.py` + Google Takeout | HTML export from Google |

Every message is tagged with its source (`claude_code`, `claude_ai`, `chatgpt`, `gemini`) so you always know where it came from. Search works across all sources seamlessly.

### Tags and Topic Discovery

Sessions are auto-tagged by topic during import (e.g., `coding`, `finance`, `family`, `memoir`). Browse your sessions by topic:

```
/brain-topics              # Show all tags with counts
/brain-topics finance      # Show all sessions tagged 'finance'
```

Edit tags anytime -- just tell Claude: "tag this session as finance, coding." For bulk tagging, use `/brain-tag-review` to generate a spreadsheet, edit tags, and update the database.

---

## Slash Commands

Type these in any Claude Code session:

| Command | What It Does |
|---------|-------------|
| `/brain-health` | Full 9-point diagnostic |
| `/brain-status` | Quick stats - sessions, messages, projects |
| `/brain-question` | Natural language question across the brain |
| `/brain-search` | Raw transcript search with timestamps |
| `/brain-history` | Session timeline - one line per session |
| `/brain-recap` | Progress report for a time range |
| `/brain-decide` | Decision lookup by number or keyword |
| `/brain-export` | Export brain data to text files |
| `/brain-import` | Import conversations (Claude.ai, ChatGPT, Gemini) |
| `/brain-topics` | Browse sessions by tag -- drill into any topic |
| `/brain-tag-review` | Batch tag review -- generate spreadsheet, edit, update |
| `/brain-questionnaire` | Fill out or update your profile |
| `/brain-setup` | Re-run setup to add projects |
| `/brain-consistency` | Automated doc/data consistency check |

---

## MCP Tools

Eleven read-only tools registered as `brain-server`. Claude calls these automatically - you just ask questions.

| Tool | What It Does |
|------|-------------|
| `get_profile` | Your complete profile - facts, preferences, working style |
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
├── scripts/             # 29 Python scripts
│   ├── brain-setup.py   # Interactive installer
│   ├── brain_digest.py  # Email digests (daily/weekly/project)
│   └── ...              # Query, import, health, backup scripts
├── mcp/
│   └── server.py        # MCP server (11 read-only tools)
├── config.yaml.example  # Reference config (real config is gitignored)
├── requirements.txt     # Python dependencies
├── imports/             # Drop exports here (claude.ai, ChatGPT, Gemini)
├── exports/             # /brain-export output
├── db-backup/           # Rotating database backups
└── logs/                # Per-hostname log files
```

---

## Multi-Project Support

claude-brain works across multiple projects from a single database. Each project gets its own folder with a CLAUDE.md file. Claude has full memory access from any of them -- search, decisions, facts, and session history all cross project boundaries.

To add a new project after initial setup:

```bash
cd ~/path/to/claude-brain          # must be in the claude-brain root folder
python3 scripts/add-project.py     # creates a new project subfolder here
```

The script creates the folder, CLAUDE.md, config entry, database registration, and MCP registration. See `CLAUDE_BRAIN_HOW_TO.md` Section 10 for the full multi-project workflow.

---

## Web Search Integration

claude-brain handles local memory. For web search (current docs, error messages, best practices), add a web search MCP server alongside brain-server. Any MCP-compatible web search tool works. For example, [Exa](https://exa.ai/) provides semantic web search with 2,000 free queries/month:

```bash
claude mcp add exa-search npx -y exa-mcp-server
```

The `add-project.py` script detects web search MCPs registered on your root path and offers to register them for new projects automatically.

---

## Multi-Machine Setup

claude-brain supports syncing between machines via Dropbox, OneDrive, Google Drive, or iCloud:

- **Project files** (scripts, hooks, config) sync via your cloud provider
- **Database** stays on local disk (SQLite + cloud sync = corruption risk)
- **Backups** sync automatically (stored in the project folder)
- **JSONL reconciliation** at startup catches exchanges from other machines

The setup script asks whether you want "synced" or "local" mode.

---

## Importing Conversations from Other Platforms

### Claude.ai

1. Install the [AI Chat Exporter](https://chromewebstore.google.com/detail/claude-exporter-save-clau/elhmfakncmnghlnabnolalcjkdpfjnin) Chrome extension
2. Open a conversation on claude.ai, click the extension icon
3. Export settings: **JSON** format, **Chats** and **Metadata** checked, everything else unchecked
4. Save the `.json` file to your `imports/` folder
5. In Claude Code, type `/brain-import` and follow the prompts

### ChatGPT

1. Go to ChatGPT Settings > Data Controls > Export data
2. Wait for the email (1-2 days), download the zip
3. Extract the zip to `imports/chatgpt-export/`
4. Scan and review:
```bash
cd ~/path/to/claude-brain
python3 scripts/import_chatgpt.py --scan imports/chatgpt-export/
```
5. Review the generated xlsx -- edit project and tag assignments
6. Import:
```bash
python3 scripts/import_chatgpt.py --import imports/chatgpt-export/ --map imports/chatgpt_import_map.xlsx
```

### Gemini

1. Go to [takeout.google.com](https://takeout.google.com)
2. Deselect all, select **My Activity**, then click "All activity data included" and check only **Gemini Apps**
3. Create export, wait for email, download zip
4. Extract to `imports/gemini-export/`
5. Scan and review:
```bash
cd ~/path/to/claude-brain
python3 scripts/import_gemini.py --scan imports/gemini-export/
```
6. Review the generated xlsx -- edit project and tag assignments
7. Import:
```bash
python3 scripts/import_gemini.py --import imports/gemini-export/ --map imports/gemini_import_map.xlsx
```

All imports are safe to re-run. Already-imported conversations are skipped automatically.

---

## Requirements

| Dependency | Version | Notes |
|-----------|---------|-------|
| Python | 3.10+ | Tested on 3.13 and 3.14 |
| Claude Code | 2.0+ | Must be installed and working |
| Node.js | 18+ | Required by Claude Code |
| pip3 | any | For installing Python packages |

**Python packages** (installed by setup or `pip install -r requirements.txt`):
- `PyYAML` - config file parsing
- `mcp` - MCP server SDK
- `sentence-transformers` - semantic search embeddings (optional, ~80MB model download)
- `numpy` - cosine similarity for semantic search

---

## Known Limitations

| Limitation | Detail |
|-----------|--------|
| **Single-user** | One person, one database. No multi-user support. |
| **No auto-capture from claude.ai** | Manual export + `/brain-import` required. |
| **Semantic search cold-start** | First query takes ~4-5s to load the model. Fast after that. |
| **No cross-machine real-time DB sync** | DB is local. Project files sync; database doesn't. |

See `POST_MVP_ROADMAP.md` for the full list and planned fixes.

---

## Security

- Database, archives, logs, backups, and personal content are all in `.gitignore`
- `config.yaml` is generated locally and never committed
- The MCP server is read-only - no write operations exposed
- Everything runs locally - no cloud services, no data leaves your machine

---

## Troubleshooting

**Claude isn't using the brain tools:**
Run `claude mcp list` - you should see `brain-server`. If missing: `claude mcp add brain-server python3 /path/to/mcp/server.py`

**Hooks aren't firing:**
Check `~/.claude/settings.json` for hook entries. Check `logs/` for error output.

**Search returns no results:**
Run `/brain-status` to verify messages exist. Try fewer keywords.

**Full diagnostic:** Run `/brain-health` for a 9-point system check.

See `CLAUDE_BRAIN_HOW_TO.md` for the complete user guide.

---

## License

MIT

---

## Contributing & Contact

Created by [Mike Dolan](https://github.com/mikeadolan).

- **Bug reports and feature requests:** [GitHub Issues](https://github.com/mikeadolan/claude-brain/issues)
- **Questions and discussion:** [GitHub Discussions](https://github.com/mikeadolan/claude-brain/discussions)
