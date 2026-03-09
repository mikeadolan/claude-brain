# CLAUDE-BRAIN: HOW TO USE YOUR BRAIN

**Last Updated:** 2026-03-08 (v3 — added get_schema tool, LLM summaries, Adding a Project guide)
**For:** All claude-brain users

---

## TABLE OF CONTENTS

1. [What Is Claude-Brain?](#1-what-is-claude-brain)
2. [How It Works (30-Second Version)](#2-how-it-works)
3. [What Happens Automatically](#3-what-happens-automatically)
4. [How to Search Your Brain](#4-how-to-search-your-brain)
5. [MCP Tools Reference](#5-mcp-tools-reference)
6. [Session Quality & Analysis](#6-session-quality--analysis)
7. [Example Queries — What to Type in Claude Code](#7-example-queries)
8. [Importing Claude.ai Conversations](#8-importing-claudeai-conversations)
9. [Running Status and Health Checks](#9-status-and-health-checks)
10. [How Data Gets Into the Brain](#10-how-data-gets-into-the-brain)
11. [Adding a New Project](#11-adding-a-new-project)
12. [Troubleshooting](#12-troubleshooting)
13. [What the Brain Cannot Do (Yet)](#13-limitations)

---

## 1. WHAT IS CLAUDE-BRAIN?

Claude-brain is a local memory system for Claude Code. It gives Claude persistent
memory across sessions — every conversation, every decision, every fact about you
and your projects is stored in a local SQLite database and searchable via MCP tools.

Without it, every Claude Code session starts from zero. With it, Claude knows:
- Who you are (name, location, preferences, working style)
- What you've discussed before (full transcripts, searchable)
- What decisions you've locked (numbered, per-project)
- What's true about your projects (characters, timelines, status)
- What happened in recent sessions (summaries, context)

Everything stays on YOUR machine. No cloud. No API calls for memory. No cost.

---

## 2. HOW IT WORKS

```
YOU type a prompt in Claude Code
        |
        v
[user-prompt-submit hook] searches your brain for relevant memories
        |                  and injects them into Claude's context
        v
Claude sees your prompt + relevant memories from past sessions
        |
        v
Claude responds (using MCP tools to query the brain if needed)
        |
        v
[stop hook] captures the exchange and writes it to the database
        |
        v
When you exit: [session-end hook] generates a summary + backs up DB
```

**Two systems work together:**
- **Hooks** (automatic) — capture data on every exchange, inject memories on every prompt
- **MCP tools** (on-demand) — Claude calls these when it needs to look something up

You don't need to do anything special. Just use Claude Code normally. The brain
works in the background. But you CAN ask Claude to search your brain directly —
and that's where the real power is.

---

## 3. WHAT HAPPENS AUTOMATICALLY

These fire without you doing anything:

| When | What Happens | Hook |
|------|-------------|------|
| Session starts | Checks for new files to ingest, loads recent session summaries | session-start.sh |
| Every prompt you type | Searches brain for relevant memories, injects top 3 results | user-prompt-submit.sh |
| Every Claude response | Captures the exchange (your prompt + Claude's response) to DB | stop.sh |
| Session ends | Generates session summary, backs up database | session-end.sh |

**You never need to say "save this" or "remember that."** It's all captured automatically.

---

## 4. HOW TO SEARCH YOUR BRAIN

### The Simple Version

Just ask Claude in plain English. Claude Code has access to 11 MCP brain tools
and will use them when your question implies memory lookup.

**Examples that trigger brain search:**

```
"What did we discuss about the ASUS laptop?"
"Show me recent sessions for the job search project"
"What was decided about the MCP server?"
"What do you know about Fat Tony?"
"Give me my career targets"
"What happened in yesterday's session?"
```

### When Claude Doesn't Automatically Search

Sometimes Claude will answer from its own context without checking the brain.
If you want to force a brain lookup, be explicit:

```
"Search the brain for everything about Fedora 43 setup"
"Use the brain tools to find all sessions about the resume"
"Look up the decision about ChromaDB in the brain"
"Check the brain — what project facts do we have for Johnny Goods?"
```

### Search Types Available

| Type | What It Does | Best For |
|------|-------------|----------|
| **Keyword search** | FTS5 full-text search across all transcripts | Finding specific topics, names, terms |
| **Semantic search** | Meaning-based search using vector embeddings | Finding related content even when words don't match |
| **Project-filtered search** | Keyword or semantic search limited to one project | When you know which project to search |
| **Fact lookup** | Structured query of the facts table | Characters, locations, status, deliverables |
| **Decision lookup** | Search locked decisions by keyword | "What did we decide about X?" |
| **Session browse** | List recent sessions, view full transcripts | "What happened last week?" |
| **Session quality** | Filter sessions by quality score and tags | "Show me our worst sessions" |
| **Profile load** | Returns everything the brain knows about you | Session context, identity, preferences |

### Keyword Search vs Semantic Search

These are two different ways to search your transcripts:

**Keyword search** (`search_transcripts`) — matches exact words. Fast. Use when you
know the specific terms: "Fat Tony", "ChromaDB", "resume". Powered by SQLite FTS5.

**Semantic search** (`search_semantic`) — matches by meaning. "illegal gambling"
finds "ran numbers on Pleasant Avenue" even though no words overlap. Powered by
sentence-transformers (all-MiniLM-L6-v2) generating 384-dimensional embeddings,
with numpy computing cosine similarity. All local, no API calls.

**When to use which:**
- Know the exact words? → keyword search (faster)
- Looking for concepts or related content? → semantic search
- Not sure? → try keyword first, then semantic if results are thin

---

## 5. MCP TOOLS REFERENCE

These are the 11 tools Claude Code can call. You don't call them directly —
Claude calls them based on your prompt. But knowing what exists helps you
ask better questions.

### get_profile()
**What:** Returns your complete profile — all brain_facts and brain_preferences.
**When Claude uses it:** Start of session, or when asked about you personally.
**Example prompt:** "What does the brain know about me?"

**What's in there:**
- Identity (name, location, DOB, education, email, GitHub)
- Family (mother, brother, sister, grandfather, all relationships)
- Professional (career targets, skills, achievements, compensation)
- Technical setup (OS, tools, subscriptions, comfort level)
- Goals (priorities, 5-year plan, publishing plans)
- Health (schedule, leg issues, coffee habits)
- Contacts (friends, key relationships)
- Lessons learned (context limits, hallucination risks, fix-immediately rule)
- Preferences (working style, communication, values, interests)

---

### search_transcripts(query, project?, limit?, recency_bias?)
**What:** Full-text search across ALL conversation transcripts ever captured.
**When Claude uses it:** Any time you ask about past conversations or topics.
**Parameters:**
- `query` — search terms (required)
- `project` — filter to one project: jg, mb, gen, js, lt, jga, oth (optional)
- `limit` — max results, default 20 (optional)
- `recency_bias` — weight newer results higher, default false (optional)

**Example prompts:**
```
"Search transcripts for 'Fedora 43 setup'"
"Find everything we discussed about the resume in the job search project"
"What have we talked about recently regarding ChromaDB?"
"Search the brain for 'Sunday Gravy'"
```

**How the search works:**
- Uses SQLite FTS5 (full-text search) — fast, works on keywords
- Matches individual words, not exact phrases (searching "ASUS laptop" finds
  messages containing both "ASUS" and "laptop", not necessarily together)
- To search within a specific project, say so: "search the JG transcripts for..."
- Recency bias makes recent results rank higher — useful for "what did we
  just discuss" type queries

**Project prefixes:**
| Prefix | Project |
|--------|---------|
| jg | Johnny Goods (memoir execution) |
| jga | Johnny Goods Assistant (memoir planning) |
| mb | Mike-brain / Claude-brain development |
| gen | General conversations |
| js | Job search |
| lt | Leg therapy |
| oth | Other / uncategorized |

---

### lookup_fact(project, category?, key?)
**What:** Finds project-specific facts by category and/or keyword.
**When Claude uses it:** Questions about project details — characters, locations, status.
**Parameters:**
- `project` — project prefix (required)
- `category` — filter by category like "character", "chapter", "status" (optional)
- `key` — search by key name or value text (optional)

**Example prompts:**
```
"What characters are in Johnny Goods?"
"Look up the chapter titles for JG"
"What's the status of the job search deliverables?"
"What do we know about Fat Tony in the JG project?"
"What's the current setup for the gen project?"
```

**Current fact categories by project:**

| Project | Categories | Count |
|---------|-----------|-------|
| jg | book, chapter, character, location, status, timeline | 63 |
| js | deliverable, strategy, status | 15 |
| gen | setup | 6 |

---

### lookup_decision(project, topic)
**What:** Finds locked decisions by keyword search.
**When Claude uses it:** "What did we decide about X?"
**Parameters:**
- `project` — project prefix (required)
- `topic` — keyword to search in description and rationale (required)

**Example prompts:**
```
"What decisions did we make about hooks?"
"Look up the ChromaDB decision"
"What was decided about the database schema?"
"Find all decisions about config"
```

**Currently:** 34 decisions (52-85) for the mb project. Searches both
description and rationale fields.

---

### get_session(session_id)
**What:** Returns the full transcript of a specific session.
**When Claude uses it:** When you want to review a specific conversation.
**Tip:** First use `get_recent_sessions` to find the session ID, then ask to see it.

**Example prompts:**
```
"Show me recent sessions, then let me pick one to review"
"What was the full conversation in that session about the resume?"
```

---

### get_recent_sessions(project?, count?)
**What:** Lists recent sessions with metadata (date, project, message count, model).
**When Claude uses it:** "What have I been working on?" / "Show recent sessions."
**Parameters:**
- `project` — filter to one project (optional)
- `count` — how many to show, default 10 (optional)

**Example prompts:**
```
"Show me my last 10 sessions"
"What JG sessions have we had recently?"
"List all sessions from this week"
```

---

### get_recent_summaries(project?, count?)
**What:** Returns session summaries (generated automatically at session end).
**When Claude uses it:** Loading context at session start, or when you ask for recaps.
**Parameters:**
- `project` — filter to one project (optional)
- `count` — how many summaries, default 5 (optional)

**Example prompts:**
```
"Summarize my recent sessions"
"What happened in the last few brain development sessions?"
"Give me a recap of recent JG work"
```

---

### get_project_state(project)
**What:** Returns recent decisions and key facts for a project — one-stop overview.
**When Claude uses it:** When you ask about a project's current state.

**Example prompts:**
```
"What's the current state of the brain project?"
"Give me an overview of the Johnny Goods project"
"Where do things stand with job search?"
```

---

### get_status()
**What:** Database health — total sessions, messages, per-project breakdown,
backup status, DB size, semantic search status.
**When Claude uses it:** Health checks, auditing.

**Example prompts:**
```
"What's the brain status?"
"How many sessions and messages are in the database?"
"Is the backup current?"
```

---

### get_schema()
**What:** Returns the full database schema — all tables, columns, types, and row counts.
**When Claude uses it:** When it needs to understand the DB structure or write a query.

**Example prompts:**
```
"Show me the database schema"
"What tables does the brain have?"
"How many rows are in each table?"
```

---

### search_semantic(query, project?, limit?)
**What:** Searches by MEANING, not just keywords. Uses vector embeddings to find
content that's conceptually similar to your query, even when the exact words don't match.
**When Claude uses it:** When keyword search misses or when you ask about concepts.
**Parameters:**
- `query` — natural language description of what you're looking for (required)
- `project` — filter to one project (optional)
- `limit` — max results, default 10 (optional)

**Example prompts:**
```
"Search semantically for illegal gambling activities"
  -> Finds "ran numbers on Pleasant Avenue", "dice game setup", "policy economics"

"Use semantic search to find discussions about database architecture"
  -> Finds SQLite setup, schema design, table creation conversations

"Find anything related to frustrated debugging sessions"
  -> Finds conversations about rework, errors, and troubleshooting
```

**How it works:**
- Each message in the brain is converted to a 384-dimensional vector (embedding)
  using the all-MiniLM-L6-v2 model from sentence-transformers
- Your query is converted to the same kind of vector
- Cosine similarity finds the closest matches — high similarity = related meaning
- Results include a similarity score (0.0 to 1.0, higher = more relevant)
- Only messages with 50+ characters are embedded (short messages like "go" are skipped)
- Currently ~1,939 embeddings from ~2,400 content messages
- Everything runs locally — no cloud, no API calls, no cost

**Keyword vs semantic in practice:**
```
Keyword: "Fat Tony" → finds messages containing those exact words
Semantic: "mob boss from East Harlem" → finds Fat Tony content by meaning
```

---

## 6. SESSION QUALITY & ANALYSIS

Every session is automatically scored and tagged based on content patterns.
This lets you find your best and worst sessions, track rework patterns, and
build lessons learned.

### Quality Score

Each session has a `quality_score` from **-3** (worst) to **+3** (best):

| Score | Meaning |
|-------|---------|
| +3 | Highly productive — completions, decisions, substantial work |
| +2 | Productive with some friction |
| +1 | Mildly productive |
| 0 | Neutral — short or unremarkable session |
| -1 | Some friction — corrections or frustration |
| -2 | Significant friction — rework and corrections |
| -3 | Worst — heavy rework, corrections, frustration |

### Quality Tags

Sessions are tagged with one or more labels:

| Tag | What It Means |
|-----|--------------|
| `completions` | Steps or milestones were completed |
| `decisions` | Decisions were made and locked |
| `substantial` | 100+ messages — a real work session |
| `debugging` | Bug fixing or troubleshooting happened |
| `corrections` | User told Claude it was wrong/incorrect |
| `rework` | User asked to redo or start over |
| `frustrated` | Signals of frustration (caps, strong language) |

**Key insight:** The best sessions often have BOTH positive and negative tags.
"Frustrated + completions + decisions" means hard productive work. "Frustrated +
rework + corrections" with no completions means a bad session.

### How to Use Session Quality

**Find your worst sessions:**
```
"Show me sessions with the lowest quality scores"
"Which sessions had the most rework?"
"Find sessions tagged as frustrated in the JG project"
```

**Find your best sessions:**
```
"Show me the most productive sessions"
"Which sessions had the most completions and decisions?"
```

**Build lessons learned:**
```
"Look at my worst-rated sessions and tell me what went wrong"
"Compare my best and worst sessions — what patterns do you see?"
"What tags are most common in the gen project vs the mb project?"
```

---

## 7. EXAMPLE QUERIES

Here are real queries you can type in Claude Code and what happens:

### Semantic Search (by meaning)
```
"Search semantically for discussions about illegal gambling"
  -> Claude calls search_semantic("illegal gambling", project="jg")
  -> Finds "dice game setup", "policy economics", "ran numbers"
     even though "illegal gambling" never appears in the text

"Find conversations related to database architecture decisions"
  -> Claude calls search_semantic("database architecture decisions")
  -> Finds SQLite setup, schema design, table creation discussions

"Semantic search for sessions where we struggled with editing"
  -> Claude calls search_semantic("struggled with editing workflow")
  -> Finds step completion attempts, rework discussions, debugging
```

### Session Quality
```
"Show me my worst sessions and explain what went wrong"
  -> Claude queries sys_sessions ORDER BY quality_score ASC
  -> Returns sessions tagged with corrections, rework, frustrated
  -> Claude can then use get_session() to read the full transcript

"Which project has the most frustrated sessions?"
  -> Claude queries quality_tags across all sessions, grouped by project

"Compare the patterns in my best vs worst sessions"
  -> Claude queries both ends of the quality_score spectrum
  -> Analyzes tags to find what makes sessions productive or painful
```

### Personal / Profile
```
"What's my compensation target?"
  -> Claude calls get_profile(), returns professional.compensation

"What are my career priorities?"
  -> Claude calls get_profile(), returns goals section

"What's my brother's name?"
  -> Claude calls get_profile(), returns family.brother
```

### Searching Past Conversations
```
"What did we discuss about setting up Fedora 43?"
  -> Claude calls search_transcripts("Fedora 43 setup", project="gen")
  -> Returns matching transcript snippets with dates

"Find everything about the Asus laptop comparison"
  -> Claude calls search_transcripts("Asus laptop")
  -> Returns results from gen project (imported from claude.ai)

"What work did we do on chapter 1?"
  -> Claude calls search_transcripts("chapter 1", project="jg")
  -> Returns JG session snippets about Ch 1
```

### Project Facts
```
"List all the characters in Johnny Goods"
  -> Claude calls lookup_fact(project="jg", category="character")
  -> Returns 13 characters with descriptions

"What chapters are in the book?"
  -> Claude calls lookup_fact(project="jg", category="chapter")
  -> Returns Ch 1-11 with titles

"What deliverables were created for job search?"
  -> Claude calls lookup_fact(project="js", category="deliverable")
  -> Returns 5 deliverables with status
```

### Decisions
```
"What was the decision about generating summaries?"
  -> Claude calls lookup_decision(project="mb", topic="summary")
  -> Returns Decision 74 (session summaries) and Decision 81 (pure Python)

"Look up all decisions about ChromaDB"
  -> Claude calls lookup_decision(project="mb", topic="ChromaDB")
  -> Returns Decisions 75 and 77
```

### Session Review
```
"Show me my last 5 sessions"
  -> Claude calls get_recent_sessions(count=5)
  -> Lists sessions with dates, projects, message counts

"What happened in recent brain development sessions?"
  -> Claude calls get_recent_summaries(project="mb")
  -> Returns session summaries with topics, decisions, files
```

### Cross-Project
```
"Search all projects for anything about Dropbox sync"
  -> Claude calls search_transcripts("Dropbox sync") (no project filter)
  -> Returns results from mb, gen, and any other project that discussed it

"Give me the full status of the brain"
  -> Claude calls get_status()
  -> Returns session count, message count, per-project breakdown, backup info
```

---

## 8. IMPORTING CLAUDE.AI CONVERSATIONS

Conversations from claude.ai (the web interface) are NOT automatically captured
by hooks. You need to export and import them manually.

### Step 1: Export from claude.ai
- Install the **AI Chat Exporter** Chrome extension
- On claude.ai, open a conversation and click the extension icon
- Set these export options:
  - **Chat format:** JSON
  - **Chats:** checked
  - **Metadata:** checked
  - **Extended Thinking:** unchecked (not parsed, adds bulk)
  - **All Artifact options:** unchecked (not parsed)
- Click **Export Current Conversation**
- Save the .json file to: `imports/` folder in your claude-brain directory

### Step 2: Tell Claude Code to import
```
"Import the file in imports/ as gen project"
```
Or run directly:
```bash
python3 scripts/import_claude_ai.py "imports/filename.json" --project gen
```

### Step 3: Verify
The file moves to `imports/completed/` on success. Search for a term from
that conversation to confirm:
```
"Search transcripts for [something from that conversation]"
```

### Project assignment
When importing, you must specify which project the conversation belongs to:
- `--project gen` for general conversations
- `--project jg` for Johnny Goods work
- `--project js` for job search
- etc.

---

## 9. STATUS AND HEALTH CHECKS

### Full Health Check (recommended)
Ask Claude: `"/brain-health"` or run from terminal:
```bash
python3 scripts/brain_health.py
```

This runs a 9-point diagnostic:
```
=== Claude Brain Health Check ===

  [PASS] Database: 112.8 MB, integrity OK, WAL, 0.0% fragmentation
  [PASS] Space: raw_json 79.0 MB (70%), content 2.7 MB (2%), embeddings 3.6 MB (3%)
  [WARN] Data: FTS5 synced (10447), embeddings 71% (2427/3432)
  [PASS] Backup: 2 copies, newest 2h old, integrity OK
  [PASS] Performance: FTS5 0.1ms, LIKE 1.3ms, COUNT(*) 0.2ms
  [PASS] Dependencies: all 4 packages importable
  [PASS] MCP: brain-server registered for 2 projects, server.py exists
  [PASS] Hooks: 4/4 registered, all files exist
  [PASS] Config: config.yaml valid, 7 projects, all paths exist

  Score: 8/9 PASS, 1 WARN, 0 FAIL
```

**Status levels:**
- **PASS** = everything nominal
- **WARN** = works but suboptimal (embedding coverage <80%, backup >24h old)
- **FAIL** = broken (integrity fail, missing files, hooks not registered)

JSON output: `python3 scripts/brain_health.py --json`

### Quick Status
Ask Claude: `"/brain-status"` or run from terminal:
```bash
python3 scripts/status.py
```

Shows session counts, message counts, per-project breakdown, backup info, and
semantic search status. Lighter than the full health check.

### Check If Hooks Are Working
The simplest test: after a Claude Code session, check if the message count
increased. If hooks are firing, every exchange adds to the database.

### Check Backup
The brain backs up automatically at session end. Backups rotate (bak1, bak2, bak3).
Location: `db-backup/claude-brain.db.bak1`

---

## 10. HOW DATA GETS INTO THE BRAIN

| Source | How It Gets In | When |
|--------|---------------|------|
| Claude Code conversations | Hooks (automatic) | Every exchange, real-time |
| Claude.ai conversations | Manual import (import_claude_ai.py) | When you export + import |
| Your profile (facts, preferences) | Populated via scripts | During setup / manually |
| Project facts | Populated via scripts | During setup / manually |
| Decisions | Populated via scripts | During setup / manually |

### What's Stored

| Table | What | Rows (current) |
|-------|------|----------------|
| transcripts | Every message from every session | 7,134 |
| transcript_embeddings | Semantic search vectors (384-dim, float32) | 1,939 |
| sys_sessions | One row per session (metadata + quality score + tags) | 54 |
| sys_session_summaries | Auto-generated session recaps | 54 |
| brain_facts | Everything about you (cross-project) | 98 |
| brain_preferences | How you work (cross-project) | 38 |
| facts | Project-specific knowledge | 84 |
| decisions | Locked decisions per project | 34 |
| tool_results | Tool call outputs | 23 |
| sys_ingest_log | Import tracking (prevents duplicates) | 104 |
| project_registry | Project name-to-prefix mapping | 7 |

---

## 11. ADDING A NEW PROJECT

To add a new project to the brain:

### Option 1: Re-run setup (recommended)
```bash
python3 scripts/brain-setup.py
```
The setup script is idempotent — it will detect existing projects and let you add new ones.
It creates the folder, CLAUDE.md, config entry, and database registration all at once.

### Option 2: Manual steps

1. **Add to config.yaml** — add a new entry under `projects:` and `jsonl_project_mapping:`:
   ```yaml
   projects:
     - folder_name: "my-new-project"
       prefix: "mnp"
       label: "My New Project"

   jsonl_project_mapping:
     "my-new-project": "mnp"
   ```

2. **Create the folder** — inside your claude-brain root:
   ```bash
   mkdir my-new-project
   ```

3. **Create CLAUDE.md** — copy from an existing project folder, update the project name,
   prefix, and label at the top.

4. **Register the prefix** — the startup check will auto-register on next session start,
   or run manually:
   ```bash
   python3 scripts/startup_check.py
   ```

5. **Register MCP** — if you want brain access from this project folder:
   ```bash
   claude mcp add brain-server python3 /path/to/claude-brain/mcp/server.py
   ```

### Naming rules
- **folder_name:** lowercase, hyphens only (e.g., "my-project")
- **prefix:** lowercase, 2-4 chars, no trailing underscore (e.g., "mp")
- **label:** human-readable name shown in brain-import picklist

---

## 12. TROUBLESHOOTING

### "Claude isn't using the brain tools"
- **Check:** Is the MCP server registered? Run: `claude mcp list`
  You should see `brain-server` in the output.
- **Check:** Are you in a project folder that has MCP registered?
  The brain-server is registered per-project in `~/.claude.json`.
- **Fix:** If missing, register it:
  ```bash
  claude mcp add brain-server python3 /path/to/claude-brain/mcp/server.py
  ```
- **Workaround:** Be explicit: "Use the brain-server MCP tools to search for..."

### "Hooks aren't firing"
- **Check:** `claude hooks list` or look in `~/.claude/settings.json`
- **Check:** Log files in `logs/<hostname>/` — each hook has its own log
- **Common cause:** Hook path changed after moving files. Paths must be absolute.

### "Search returns no results"
- **Check status:** `python3 scripts/status.py` — are there messages in the DB?
- **Check FTS5:** The search uses keywords, not exact phrases. Try fewer/different words.
- **Check project filter:** If you said "search JG for X" but the data is in GEN,
  you won't find it. Try without a project filter.
- **Tip:** Short prompts (<15 chars) are skipped by the user-prompt-submit hook.

### "Session data is missing"
- **Check:** Did the session end normally? If Claude Code crashed, the session-end
  hook may not have fired. But the stop hook captures data on every exchange,
  so most data is still there.
- **Check:** `python3 scripts/status.py` — compare message counts before and after.

### "Import failed for claude.ai file"
- **Check:** Is it valid JSON? The file must be a claude.ai export, not a raw copy.
- **Check:** Does the file have `chat_messages` and `uuid` fields?
- **Check log:** `logs/<hostname>/import_claude_ai.log`

### "Database is locked"
- **Cause:** Another process is writing. The DB uses WAL mode with 5-second timeout.
- **Fix:** Wait a moment and try again. If persistent, check for stuck processes.

---

## 13. WHAT THE BRAIN CANNOT DO (YET)

| Limitation | Why | When It Gets Fixed |
|-----------|-----|-------------------|
| **Python 3.13+ only** | Tested on 3.13 and 3.14. Older versions untested. | Expand testing to 3.10+ post-MVP |
| **Single-user design** | One person, one database. No multi-user support. | Not planned — personal memory tool |
| **Semantic search cold-start ~4-5s** | First query loads embedding model into memory | Subsequent queries are fast (<100ms) |
| **FTS5 only (no fuzzy match)** | Typos like "sesion" won't match "session" | Post-MVP: fuzzy matching layer |
| **No auto-capture from claude.ai** | Claude.ai has no hook system | Manual export + import required |
| **No cross-machine real-time sync** | DB is local; Dropbox syncs project files but not the DB | Planned: DB in Dropbox or sync script |
| **Summaries require normal exit** | session-end hook only fires on clean exit | If Claude Code crashes, summary is lost (but exchanges are saved) |
| **No web UI** | CLI-only via Claude Code | Post-MVP consideration |
| **No automatic fact extraction** | Facts are manually populated | Post-MVP: auto-extract from conversations |
| **No lessons learned extractor** | Requires pattern mining across sessions | Post-MVP: find "mistake"/"redo"/"should have" patterns |

See `POST_MVP_ROADMAP.md` for the full roadmap and planned fixes.

---

## QUICK REFERENCE CARD

```
KEYWORD SEARCH:
  "Search the brain for [topic]"
  "Find all sessions about [topic] in [project]"

SEMANTIC SEARCH (by meaning):
  "Semantically search for [concept]"
  "Find anything related to [description]"

LOOK UP FACTS:
  "What characters are in JG?"
  "What's the status of [project]?"

CHECK DECISIONS:
  "What was decided about [topic]?"

REVIEW SESSIONS:
  "Show me recent sessions"
  "What happened in the last few sessions?"

SESSION QUALITY:
  "Show me my worst sessions"
  "Which sessions had the most rework?"
  "Compare my best and worst sessions"

MY PROFILE:
  "What does the brain know about me?"

HEALTH CHECK:
  /brain-health (full 9-point diagnostic)
  /brain-status (quick stats)

IMPORT CLAUDE.AI CHAT:
  Drop .json in imports/, then:
  "Import the file in imports/ as [project] project"
```
