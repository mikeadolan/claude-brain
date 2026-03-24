# CLAUDE-BRAIN: HOW TO USE YOUR BRAIN

**For:** All claude-brain users

---

## TABLE OF CONTENTS

1. [What Is Claude-Brain?](#1-what-is-claude-brain)
2. [How It Works](#2-how-it-works)
3. [How to Search Your Brain](#3-how-to-search-your-brain)
4. [MCP Tools Reference](#4-mcp-tools-reference)
5. [Session Quality & Analysis](#5-session-quality--analysis)
6. [Example Queries - What to Type in Claude Code](#6-example-queries)
7. [Importing Conversations from Other Platforms](#7-importing-conversations-from-other-platforms)
8. [Running Status and Health Checks](#8-status-and-health-checks)
8.5. [**Email Digests** - The brain emails YOU (no other tool does this)](#85-email-digests)
9. [How Data Gets Into the Brain](#9-how-data-gets-into-the-brain)
10. [Multi-Project Workflow](#10-multi-project-workflow)
11. [Troubleshooting](#11-troubleshooting)
12. [What the Brain Cannot Do (Yet)](#12-limitations)

---

> **Note:** The examples throughout this guide use made-up projects to show how the
> brain works in practice. Your projects will be different - maybe you're building a
> mobile app (`app` prefix), tracking a job search (`js` prefix), writing a novel
> (`nv` prefix), or managing freelance clients (`fr` prefix). Whatever you're working
> on, you define your own projects during setup and the brain adapts to you.

---

## 1. WHAT IS CLAUDE-BRAIN?

**Your AI finally has a real memory.** Not just RAG - RAG and beyond.

claude-brain gives Claude Code 100% lossless recall across every session and every project. No silos. Every word captured, every decision tracked, every project connected. It searches by keyword, meaning, or fuzzy match. It emails you a morning briefing before you open your laptop. Zero cloud dependencies - your data never leaves your machine.

**Without it:** Claude Code starts every session from zero. Close the terminal, everything is gone. MEMORY.md has a 200-line cap. Context compaction throws away your earlier conversation. Projects are siloed.

**With it, Claude knows:**
- **Who you are** - name, preferences, working style, career goals
- **What you've discussed** - every conversation, searchable by keyword, meaning, or fuzzy match
- **What you've decided** - numbered, locked decisions that Claude won't re-ask
- **What's true about your projects** - features, architecture, timelines, status
- **What happened recently** - session summaries, project health, next steps
- **What connects your projects** - cross-project search finds related work, shared patterns, decisions
- **What you should do today** - proactive email briefings with per-project next steps and blockers

Everything stays on YOUR machine. No cloud. No API calls for memory. Zero token burn.

### What Can You Actually Do With It?

The brain isn't just a passive archive. You can actively search it, query it, and
get answers from your own history. Here are real things you can ask:

**Simple keyword searches:**
```
"Search the brain for authentication"
"Find sessions about Docker"
"Look up the payment API"
```

**Complex natural language queries:**
```
"What did we work on two days ago around 2pm?"
"Show me every decision we made about the database"
"Find conversations where I was frustrated - what went wrong?"
"Compare my most productive sessions to my worst ones"
"What's the full history of this project from the beginning?"
```

**Meaning-based searches** (finds related content even when words don't match):
```
"How do users pay for things?" → finds payment API discussions
"Sessions about server problems" → finds deployment errors, timeouts, Docker issues
```

**Cross-project intelligence** (searches across ALL your projects, not siloed):
```
"Search all projects for anything about Docker"
"What decisions have we made about APIs across every project?"
"Find sessions where we discussed deployment - any project"
"What patterns show up in my worst sessions across all projects?"
```

**Post-mortem and lessons learned** (let the AI extract real patterns from your history):
```
"Look at my worst-rated sessions and tell me what went wrong"
"What mistakes keep repeating across my projects?"
"Compare my best and worst sessions - what patterns do you see?"
"What lessons should I take from the last month of work?"
"Find every time I had to redo something - what caused it?"
```

**Proactive email digests** - the brain reaches out to YOU (see Section 8.5):
```
Daily:   Per-project "Pick Up Here" + blockers + accomplishments at 8am
Weekly:  Executive summary, RAG portfolio, trends, dormant alerts - forwardable
Project: Full status report for one project - health, risks, decisions, architecture
```

**Personal profile queries:**
```
"What are my career priorities?"
"What does the brain know about me?"
"What's my preferred working style?"
```

You can search from two places:
1. **Just ask Claude** - type a question naturally and Claude calls the right brain tool
2. **Slash commands** - type `/brain-question`, `/brain-search`, `/brain-history`,
   `/brain-recap`, `/brain-decide`, or any of the 14 brain commands for direct access

---

## 2. HOW IT WORKS

**Three systems work together:**

### Hooks (automatic - you do nothing)
Four Python scripts fire at every stage of your Claude Code session. They capture
data and inject memories without you lifting a finger.

| When | What Happens | Hook |
|------|-------------|------|
| Session starts | Ingests new files, loads recent session summaries as context | session-start.py |
| Every prompt you type | Searches brain for relevant memories, injects top 3 into Claude's context | user-prompt-submit.py |
| Every Claude response | Captures the full exchange (your prompt + Claude's response) to the database | stop.py |
| Session ends | Backs up the database | session-end.py |

**You never need to say "save this" or "remember that."** Every exchange is captured
automatically, in full - not summarized, not filtered, not reduced to tool observations.
Every prompt gets relevant memories injected. It just works.

### MCP Tools (automatic - Claude calls these on its own)
Eleven read-only tools let Claude query the brain on demand. When you ask a question
that implies memory lookup, Claude picks the right tool and searches for you - across
**all** your projects, not just the one you're in. You don't need to know which tool
to use - just ask in plain English.

### Slash Commands (manual - you type these when you want direct access)
Eleven slash commands give you direct control over the brain. Use these when you
want to search, check status, import data, or run diagnostics yourself:

| Command | What It Does |
|---------|-------------|
| `/brain-question` | Ask anything - searches keywords, meaning, facts, and decisions all at once |
| `/brain-search` | Raw transcript search with timestamps and excerpts |
| `/brain-history` | Session timeline - one line per session with date, project, and topic |
| `/brain-recap` | Progress report for a time range (today, this week, last N days) |
| `/brain-decide` | Fast decision lookup by number or keyword |
| `/brain-health` | Full 9-point diagnostic (database, hooks, MCP, backup, performance) |
| `/brain-status` | Quick stats - sessions, messages, per-project counts |
| `/brain-import` | Import conversations (Claude.ai, ChatGPT, Gemini) |
| `/brain-questionnaire` | Fill out or update your personal profile |
| `/brain-setup` | Re-run setup to add projects or fix configuration |
| `/brain-export` | Export brain data to timestamped text files |

---

## 3. HOW TO SEARCH YOUR BRAIN

Every search works across **all your projects** by default. You can filter to a
specific project when you want to, but out of the box, the brain finds answers
wherever they live - whether it was a web app session, a side project, or a
general conversation from weeks ago.

There are three ways to search, from easiest to most specific:

### Way 1: Just Ask Claude (easiest)

Type a question in plain English. Claude automatically picks the right brain tool.

```
"What did we discuss about the login page?"
"Show me recent sessions for the recipe app project"
"What was decided about the database schema?"
"What happened two days ago in the afternoon?"
"Find conversations where deployment failed"
```

If Claude answers from its own context instead of checking the brain, be explicit:
```
"Search the brain for everything about the deployment setup"
"Use the brain tools to find all sessions about the resume"
"Check the brain - what project facts do we have for the recipe app?"
```

### Way 2: Slash Commands (direct access)

Type these yourself for instant, specific results. All 14 brain commands:

| Command | When to Use It | Example |
|---------|---------------|---------|
| `/brain-question` | General questions - searches everything at once | "What do we know about the payment flow?" |
| `/brain-search` | Raw transcript search with full excerpts | "authentication error" |
| `/brain-history` | See a timeline of your sessions | Shows date, project, topic per session |
| `/brain-recap` | Summarize what you've done over a time range | "Give me this week's progress" |
| `/brain-decide` | Look up a specific decision | "12" or "database" |
| `/brain-health` | Full 9-point system diagnostic | Checks DB, hooks, MCP, backup, performance |
| `/brain-status` | Quick database stats | Session counts, message counts, per-project |
| `/brain-import` | Import conversations (Claude.ai, ChatGPT, Gemini) | Claude.ai: drop JSON in `imports/`. ChatGPT/Gemini: ask Claude or run import scripts directly. |
| `/brain-questionnaire` | Fill out or update your profile | Name, preferences, goals, working style |
| `/brain-setup` | Re-run setup to add projects or fix config | Safe to re-run anytime |
| `/brain-export` | Save brain data to text files | Exports profile, decisions, or search results |
| `/brain-topics` | Browse sessions by tag | Shows tag counts, drill into "finance", "memoir", etc. |
| `/brain-tag-review` | Batch tag review via spreadsheet | Generates xlsx, you edit tags, then update DB |
| `/brain-consistency` | Automated consistency check | Verifies all counts, paths, data integrity |

### Way 3: MCP Tools (Claude calls these - you just ask)

Behind the scenes, Claude has 11 read-only tools. You don't need to call them
directly, but knowing what's available helps you ask better questions:

| Tool | What It Does |
|------|-------------|
| `search_transcripts` | Keyword search across all conversations |
| `search_semantic` | Meaning-based search (finds related content even when words differ) |
| `lookup_fact` | Project-specific facts by category |
| `lookup_decision` | Locked decisions by keyword |
| `get_profile` | Your complete profile - facts, preferences, working style |
| `get_project_state` | Decisions + facts for a project in one call |
| `get_session` | Full transcript of a specific session |
| `get_recent_sessions` | List recent sessions with metadata |
| `get_recent_summaries` | Auto-generated session recaps |
| `get_status` | Database stats and health |
| `get_schema` | Full database schema and row counts |

### Keyword Search vs Semantic Search

Two different search engines working together, both searching across all projects:

**Keyword search** - matches exact words. Fast. Type "payment API" and it finds
messages containing those words. Good for specific terms, names, error messages.

**Semantic search** - matches by meaning. Type "how users pay for things" and it
finds payment API discussions even though those exact words never appear. Good for
concepts, vague memories, and "I know we talked about something like..."

**When to use which:**
- Know the exact words? → keyword search (faster)
- Looking for concepts or related content? → semantic search
- Not sure? → `/brain-question` runs both automatically

---

## 4. MCP TOOLS REFERENCE

These are the 11 tools Claude Code can call. You don't call them directly -
Claude calls them based on your prompt. But knowing what exists helps you
ask better questions.

### get_profile()
**What:** Returns your complete profile - all brain_facts and brain_preferences.
**When Claude uses it:** Start of session, or when asked about you personally.
**Example prompt:** "What does the brain know about me?"

**What's in there** (populated via `/brain-questionnaire` during setup):
- Identity (name, location, education, contact info)
- Family and relationships
- Professional (career targets, skills, achievements)
- Technical setup (OS, tools, comfort level)
- Goals (priorities, plans)
- Lessons learned (what works, what doesn't)
- Preferences (working style, communication, values)

---

### search_transcripts(query, project?)
**What:** Full-text search across ALL conversation transcripts ever captured - every project, every session, every message. Returns up to 20 results ranked by relevance.
**When Claude uses it:** Any time you ask about past conversations or topics.
**Parameters:**
- `query` - search terms (required)
- `project` - filter to one project by prefix, e.g. `gen`, `app`, `js` (optional)

**Example prompts:**
```
"Search transcripts for 'React router setup'"
"Find everything we discussed about the resume in the job search project"
"What have we talked about recently regarding the payment API?"
"Search the brain for 'user onboarding flow'"
```

**How the search works:**
- Uses SQLite FTS5 (full-text search) - fast, works on keywords
- Matches individual words, not exact phrases (searching "login page" finds
  messages containing both "login" and "page", not necessarily together)
- To search within a specific project, say so: "search the app transcripts for..."
- Recency bias makes recent results rank higher - useful for "what did we
  just discuss" type queries

**Project prefixes** (examples - yours are created during setup):
| Prefix | Project |
|--------|---------|
| gen | General conversations |
| wp | Website project |
| js | Job search |
| bk | Book project |

Your prefixes are defined in `config.yaml` under `projects:`. To see your current
projects, run `/brain-status` or check `config.yaml`.

---

### lookup_fact(project, category?, key?)
**What:** Finds project-specific facts by category and/or keyword.
**When Claude uses it:** Questions about project details - characters, locations, status.
**Parameters:**
- `project` - project prefix (required)
- `category` - filter by category like "character", "chapter", "status" (optional)
- `key` - search by key name or value text (optional)

**Example prompts:**
```
"What API endpoints are defined for the recipe app?"
"Look up the feature list for the app project"
"What's the status of the job search deliverables?"
"What do we know about the payment service in the app project?"
"What's the current setup for the gen project?"
```

**Example fact categories** (yours depend on what you populate):

| Project | Categories | Example |
|---------|-----------|---------|
| app | feature, endpoint, status, architecture | 30+ facts about your app |
| js | deliverable, strategy, status | Resume versions, target companies |
| gen | setup | Machine config, tools |

---

### lookup_decision(project, topic)
**What:** Finds locked decisions by keyword search.
**When Claude uses it:** "What did we decide about X?"
**Parameters:**
- `project` - project prefix (required)
- `topic` - keyword to search in description and rationale (required)

**Example prompts:**
```
"What decisions did we make about the API design?"
"Look up the decision about authentication"
"What was decided about the database schema?"
"Find all decisions about deployment"
```

Decisions accumulate as you work. Searches both description and rationale fields.

---

### get_session(session_id)
**What:** Returns the full transcript of a specific session.
**When Claude uses it:** When you want to review a specific conversation.
**Tip:** First use `get_recent_sessions` to find the session ID, then ask to see it.

**Example prompts:**
```
"Show me recent sessions, then let me pick one to review"
"What was the full conversation in that session about the API?"
```

---

### get_recent_sessions(project?, count?)
**What:** Lists recent sessions with metadata (date, project, message count, model).
**When Claude uses it:** "What have I been working on?" / "Show recent sessions."
**Parameters:**
- `project` - filter to one project (optional)
- `count` - how many to show, default 10 (optional)

**Example prompts:**
```
"Show me my last 10 sessions"
"What app project sessions have we had recently?"
"List all sessions from this week"
```

---

### get_recent_summaries(project?, count?)
**What:** Returns session summaries (generated automatically at session end).
**When Claude uses it:** Loading context at session start, or when you ask for recaps.
**Parameters:**
- `project` - filter to one project (optional)
- `count` - how many summaries, default 5 (optional)

**Example prompts:**
```
"Summarize my recent sessions"
"What happened in the last few app project sessions?"
"Give me a recap of recent job search work"
```

---

### get_project_state(project)
**What:** Returns recent decisions and key facts for a project - one-stop overview.
**When Claude uses it:** When you ask about a project's current state.

**Example prompts:**
```
"What's the current state of the app project?"
"Give me an overview of the recipe app"
"Where do things stand with job search?"
```

---

### get_status()
**What:** Database health - total sessions, messages, per-project breakdown,
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
**What:** Returns the full database schema - all tables, columns, types, and row counts.
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
- `query` - natural language description of what you're looking for (required)
- `project` - filter to one project (optional)
- `limit` - max results, default 10 (optional)

**Example prompts:**
```
"Search semantically for user authentication problems"
  -> Finds "OAuth token expired", "session cookie rejected", "login redirect loop"
     even though "authentication" never appears in those messages

"Use semantic search to find discussions about database architecture"
  -> Finds SQLite setup, schema design, table creation conversations

"Find anything related to frustrated debugging sessions"
  -> Finds conversations about rework, errors, and troubleshooting
```

**How it works:**
- Each message in the brain is converted to a 384-dimensional vector (embedding)
  using the all-MiniLM-L6-v2 model from sentence-transformers
- Your query is converted to the same kind of vector
- Cosine similarity finds the closest matches - high similarity = related meaning
- Results include a similarity score (0.0 to 1.0, higher = more relevant)
- Only messages with 50+ characters are embedded (short messages like "go" are skipped)
- Everything runs locally - no cloud, no API calls, no cost

**Keyword vs semantic in practice:**
```
Keyword: "payment API" → finds messages containing those exact words
Semantic: "how users pay for things" → finds payment API content by meaning
```

---

## 5. SESSION QUALITY & ANALYSIS

Every session is automatically scored and tagged based on content patterns.
This lets you find your best and worst sessions, track rework patterns, and
build lessons learned.

### Quality Score

Each session has a `quality_score` from **-3** (worst) to **+3** (best):

| Score | Meaning |
|-------|---------|
| +3 | Highly productive - completions, decisions, substantial work |
| +2 | Productive with some friction |
| +1 | Mildly productive |
| 0 | Neutral - short or unremarkable session |
| -1 | Some friction - corrections or frustration |
| -2 | Significant friction - rework and corrections |
| -3 | Worst - heavy rework, corrections, frustration |

### Quality Tags

Sessions are tagged with one or more labels:

| Tag | What It Means |
|-----|--------------|
| `completions` | Steps or milestones were completed |
| `decisions` | Decisions were made and locked |
| `substantial` | 100+ messages - a real work session |
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
"Find sessions tagged as frustrated in the app project"
```

**Find your best sessions:**
```
"Show me the most productive sessions"
"Which sessions had the most completions and decisions?"
```

**Build lessons learned:**
```
"Look at my worst-rated sessions and tell me what went wrong"
"Compare my best and worst sessions - what patterns do you see?"
"What tags are most common in the app project vs the gen project?"
```

---

## 6. EXAMPLE QUERIES

Here are example queries you can type in Claude Code and what happens behind the scenes:

### Semantic Search (by meaning)
```
"Search semantically for user authentication problems"
  -> Claude calls search_semantic("user authentication problems", project="app")
  -> Finds "OAuth token expired", "session cookie rejected", "login redirect"
     even though "authentication" never appears in those messages

"Find conversations related to database architecture decisions"
  -> Claude calls search_semantic("database architecture decisions")
  -> Finds SQLite setup, schema design, table creation discussions

"Semantic search for sessions where we struggled with deployment"
  -> Claude calls search_semantic("struggled with deployment")
  -> Finds CI/CD pipeline errors, Docker config issues, server timeouts
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
"What are my career priorities?"
  -> Claude calls get_profile(), returns goals section

"What does the brain know about me?"
  -> Claude calls get_profile(), returns full profile

"What's my preferred working style?"
  -> Claude calls get_profile(), returns preferences
```

### Searching Past Conversations
```
"What did we discuss about setting up the dev environment?"
  -> Claude calls search_transcripts("dev environment setup", project="app")
  -> Returns matching transcript snippets with dates

"Find everything about the React router migration"
  -> Claude calls search_transcripts("React router")
  -> Returns results from the app project

"What work did we do on the onboarding flow?"
  -> Claude calls search_transcripts("onboarding flow", project="app")
  -> Returns session snippets about user onboarding
```

### Project Facts
```
"What API endpoints are defined for the app?"
  -> Claude calls lookup_fact(project="app", category="endpoint")
  -> Returns all registered endpoints with descriptions

"What are the main features we've built?"
  -> Claude calls lookup_fact(project="app", category="feature")
  -> Returns feature list with status

"What deliverables were created for job search?"
  -> Claude calls lookup_fact(project="js", category="deliverable")
  -> Returns resume versions, cover letters, etc.
```

### Decisions
```
"What was the decision about the tech stack?"
  -> Claude calls lookup_decision(project="app", topic="tech stack")
  -> Returns the locked decision with rationale

"Look up all decisions about deployment"
  -> Claude calls lookup_decision(project="app", topic="deployment")
  -> Returns deployment-related decisions
```

### Session Review
```
"Show me my last 5 sessions"
  -> Claude calls get_recent_sessions(count=5)
  -> Lists sessions with dates, projects, message counts

"What happened in recent app project sessions?"
  -> Claude calls get_recent_summaries(project="app")
  -> Returns session summaries with topics, decisions, files
```

### Cross-Project
```
"Search all projects for anything about Docker"
  -> Claude calls search_transcripts("Docker") (no project filter)
  -> Returns results from app, gen, and any other project that discussed it

"Give me the full status of the brain"
  -> Claude calls get_status()
  -> Returns session count, message count, per-project breakdown, backup info
```

---

## 7. IMPORTING CONVERSATIONS FROM OTHER PLATFORMS

claude-brain can import from four sources. Claude Code conversations are captured automatically by hooks. The other three require manual export and import.

### 7.1 Claude.ai (Web Interface)

**Export:**
1. Install the **AI Chat Exporter** Chrome extension
2. On claude.ai, open a conversation and click the extension icon
3. Export settings: **JSON** format, **Chats** and **Metadata** checked, everything else unchecked
4. Save the `.json` file to your `imports/` folder

**Import:**
```
/brain-import
```
Or from the terminal: `python3 scripts/import_claude_ai.py "imports/filename.json" --project gen`

### 7.2 ChatGPT (Full Account Export)

**Export:**
1. Go to ChatGPT → Settings → Data Controls → Export data
2. Click "Export" -- you'll get a confirmation email
3. Wait 1-2 days for the export to process
4. When you get the email, click the download link
5. Save the zip to your `imports/` folder
6. Extract: `unzip the-file.zip -d imports/chatgpt-export/`

**Scan and review:**
```bash
cd ~/path/to/claude-brain
python3 scripts/import_chatgpt.py --scan imports/chatgpt-export/
```
This generates `imports/chatgpt_import_map.xlsx` with three tabs:
- **Conversations** -- one row per conversation with auto-suggested project and tags (yellow columns, edit these)
- **Project Reference** -- all your project prefixes
- **Tag Reference** -- available tags with descriptions

Review the xlsx. Edit the project and tags columns. Delete rows you don't want.

**Import:**
```bash
python3 scripts/import_chatgpt.py --import imports/chatgpt-export/ --map imports/chatgpt_import_map.xlsx
```

Safe to re-run. Already-imported conversations are skipped automatically.

### 7.3 Gemini (Google Takeout)

**Export:**
1. Go to [takeout.google.com](https://takeout.google.com)
2. Click "Deselect all"
3. Scroll to **My Activity** (NOT "Gemini") and check it
4. Click "All activity data included" inside that row
5. In the popup, deselect all, then check only **Gemini Apps**. Click OK.
6. Scroll down, click "Next step", then "Create export"
7. Wait for the email (a few hours to a day)
8. Download the zip, save to `imports/`
9. Extract: `unzip takeout-*.zip -d imports/gemini-export/`

**Important:** Selecting just "Gemini" gives you an empty file. You must go through **My Activity > Gemini Apps** to get your conversation history.

**Scan and review:**
```bash
cd ~/path/to/claude-brain
python3 scripts/import_gemini.py --scan imports/gemini-export/
```
Same xlsx workflow as ChatGPT. Gemini exports individual exchanges (not sessions), so the script groups exchanges within 30 minutes of each other into sessions automatically.

**Import:**
```bash
python3 scripts/import_gemini.py --import imports/gemini-export/ --map imports/gemini_import_map.xlsx
```

### 7.4 Tags and Topic Discovery

Every import auto-suggests tags based on conversation content (e.g., `coding`, `finance`, `family`, `memoir`). You review and edit tags in the xlsx before importing.

**Browse by topic:**
```
/brain-topics              # Show all tags with session counts
/brain-topics finance      # Show all sessions tagged 'finance'
/brain-topics --project jg # Tags for one project only
```

**Batch tag review** (for sessions imported without tags, like Claude Code sessions):
```
/brain-tag-review          # Generates a spreadsheet of untagged sessions
```
Edit the spreadsheet, then run the update command shown in the output.

**Inline tag editing** (for fixing one session):
Just tell Claude: "tag this session as finance, coding" or "change the tags on yesterday's session to legal, family." Claude finds the session and updates it directly. No commands needed.

---

## 8. STATUS AND HEALTH CHECKS

### Full Health Check (recommended)
Ask Claude: `"/brain-health"` or run from terminal:
```bash
python3 scripts/brain_health.py
```

This runs a 9-point diagnostic:
```
  [PASS] Database: 174.5 MB, integrity OK, WAL, 0.0% fragmentation
  [PASS] Space: raw_json 124.7 MB (71%), content 5.7 MB (3%), embeddings 7.9 MB (5%)
  [PASS] Data: FTS5 synced (15027), embeddings 100% (5425/5426), summaries 100%
  [PASS] Backup: 2 copies, newest 24m old, integrity OK
  [PASS] Performance: FTS5 0.1ms, LIKE 16.0ms, COUNT(*) 0.3ms
  [PASS] Dependencies: all 4 packages importable
  [PASS] MCP: brain-server registered for 8 projects, server.py exists
  [PASS] Hooks: 4/4 registered, all files exist
  [PASS] Config: config.yaml valid, 8 projects, all paths exist

  Score: 9/9 PASS
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

## 8.5. EMAIL DIGESTS

The brain can email you proactive status reports - daily, weekly, or per-project. No other AI memory tool does this. Schedule via cron and forget.

### Setup

**1. Gmail App Password (required):**
1. Go to myaccount.google.com → Security → 2-Step Verification (must be ON)
2. At the bottom of the 2-Step page, click "App passwords"
3. Create one for "Mail" on "Other (custom name)" → name it "claude-brain"
4. Copy the 16-character password
5. Add to your config.yaml:

```yaml
email:
  enabled: true
  from_address: "your-email@gmail.com"
  to_address: "your-email@gmail.com"
  gmail_app_password: "xxxx xxxx xxxx xxxx"
```

**2. Test it works:**
```bash
python3 scripts/brain_digest.py --test          # Test SMTP connection
python3 scripts/brain_digest.py --daily --dry-run   # Preview daily (no send)
python3 scripts/brain_digest.py --dry-run       # Preview weekly (no send)
python3 scripts/brain_digest.py --daily --dark  # Dark mode (any template)
```

**Dark mode:** Add `--dark` to any command for dark-themed emails. Or set it permanently in config.yaml:
```yaml
email:
  dark_mode: true
```

**3. Schedule via cron (crontab -e):**
```
# Daily standup - weekdays at 8am
0 8 * * 1-5 /usr/bin/python3 /path/to/scripts/brain_digest.py --daily >> ~/claude-brain-local/digest.log 2>&1

# Weekly digest - Monday at 8am
0 8 * * 1 /usr/bin/python3 /path/to/scripts/brain_digest.py >> ~/claude-brain-local/digest.log 2>&1
```

Or run `python3 scripts/brain-setup.py` - it offers to configure email and install cron for you.

### Three Templates

**Daily Standup** (`--daily`) - 150-250 words, fits one screen:
- BLUF summary: "10 sessions across 2 projects yesterday"
- Per-project blocks: RAG health badge, "Pick Up Here" (from project next steps), blockers (red), in-progress
- Decisions made (if any)
- Quiet projects (no activity yesterday, with last session date)
- Metrics with 7-day rolling average comparison
- Subject: `[brain] Daily: 10 sessions, 5,419 msgs | Mar 12`

**Weekly Digest** (default, no flag) - 300-500 words, forwardable:
- Executive summary BLUF: "This week you logged 47 sessions... All projects on track."
- Week-over-week trend table (sessions/messages/decisions + delta %)
- Project portfolio with RAG health, status (Active/Paused), 1-line context, trend arrows
- Top accomplishments extracted from session notes
- Dormant project alerts (amber, with next steps)
- Decisions, last session notes, roadmap, brain stats, inception-to-date
- Subject: `[Weekly] Mar 05-Mar 12: 47 sessions across 1 projects`

**Project Deep Dive** (`--project mb`) - 500-800 words, full status report:
- RAG health badge header + project stats (since date, total sessions)
- Executive summary (from project summary in database)
- Health metrics: sessions (7d with trend), messages, decisions, summary freshness
- In Progress, Risks & Blockers, Next Steps (all from project summary)
- Recent sessions (last 5-7 with topics)
- Key decisions (last 10)
- Architecture snapshot
- Subject: `[mb] Status: ON TRACK - Personal memory system for Claude Code | Mar 12`

### Example Output (Daily Standup)

```
Subject: [brain] Daily: 3 sessions, 892 msgs | Mar 12

Daily Standup - Wednesday, Mar 12

3 sessions across 2 projects yesterday (myapp, api-service) with 892 messages.

[ON TRACK] myapp
  Pick Up Here: Implement rate limiting on /api/upload endpoint
  In Progress: Auth refactor (80%), rate limiting (not started)
  Yesterday (2 sessions): Auth middleware refactor · API endpoint tests

[AT RISK] api-service
  Pick Up Here: Fix flaky CI tests blocking deploy
  Blockers: CI pipeline fails intermittently on integration tests
  Yesterday (1 session): Investigated CI timeout issue

No Activity Yesterday:
  docs - last session Mar 8
```

---

## 9. HOW DATA GETS INTO THE BRAIN

| Source | How It Gets In | When |
|--------|---------------|------|
| Claude Code conversations | Hooks (automatic) | Every exchange, real-time |
| Claude.ai conversations | Manual import (import_claude_ai.py) | When you export + import |
| ChatGPT conversations | Full data export (import_chatgpt.py) | When you export from OpenAI + import |
| Gemini conversations | Google Takeout HTML (import_gemini.py) | When you export from Google + import |
| Your profile (facts, preferences) | Populated via scripts | During setup / manually |
| Project facts and decisions | Populated via scripts | During setup / manually |

### What's Stored

> **Note:** The row counts below are from one active brain to show scale. Your
> numbers will be different - a fresh install starts at zero and grows as you work.

| Table | What | Example rows |
|-------|------|----------------|
| transcripts | Every message from every session (4 sources) | 44,000+ |
| transcript_embeddings | Semantic search vectors (384-dim, float32) | 7,500+ |
| sys_sessions | One row per session (metadata + quality score + tags) | 1,300+ |
| brain_facts | Everything about you (cross-project) | 98 |
| brain_preferences | How you work (cross-project) | 41 |
| facts | Project-specific knowledge | 171 |
| decisions | Locked decisions per project | 58 |
| tool_results | Tool call outputs | 144 |
| sys_ingest_log | Import tracking (prevents duplicates) | 480 |
| project_registry | Project name-to-prefix mapping | 8 |

---

## 10. MULTI-PROJECT WORKFLOW

claude-brain is designed to work across multiple projects. Each project gets its own folder inside the claude-brain directory, and Claude has full memory access from any of them.

### Starting a Session in Any Project

This is the core workflow. Once a project is set up (see "Adding a New Project" below), here's exactly how to use it:

**From the terminal:**

```bash
# 1. Navigate to your project folder
cd ~/Dropbox/Documents/AI/Claude/claude-brain/my-website/

# 2. Launch Claude Code
claude

# 3. That's it. The brain is live. Just start talking.
```

**From a code editor (VS Code, Zed, Cursor, etc.):**

1. Open your editor
2. Open the project folder (File > Open Folder, then pick `claude-brain/my-website/`)
3. Open the built-in terminal (usually Ctrl+` or View > Terminal)
4. Type `claude` and press Enter
5. The brain is live. Start working.

**Running multiple projects at the same time:**

You can have separate Claude Code sessions running in different projects simultaneously. Each one has its own independent conversation with full brain access.

1. Open a second editor window (Ctrl+Shift+N in most editors, or File > New Window)
2. In that new window, open a different project folder (File > Open Folder)
3. Open the terminal in that window
4. Type `claude` and press Enter
5. Now you have two Claude sessions, each in their own project, both with brain access

Both sessions share the same database. If you make a decision in one project, Claude in the other project can find it. All sessions share your account's rate limit, so running multiple heavy sessions will use your quota faster.

### What Happens Automatically When You Start a Session

You don't need to configure anything or run any commands. When you type `claude` in a project folder, four things happen behind the scenes:

1. **CLAUDE.md loads** -- your project folder has a file called CLAUDE.md. Claude reads this automatically at the start of every session. It contains your project name, brain connection rules, and any project-specific instructions you've added.

2. **Session-start hook fires** -- a background script runs that:
   - Reads your NEXT_SESSION.md file (if you left notes from last time)
   - Loads your last session's notes from the database
   - Flags any unfinished items from your previous session
   - Injects all of this into Claude's context so it knows where you left off

3. **Memory search hook activates** -- on every message you send, a background script searches your brain database for relevant past conversations and silently injects them into Claude's context. You don't see this happening, but Claude does.

4. **MCP tools become available** -- Claude can search your transcripts, look up decisions, check project facts, and query your profile. It does this on its own when it needs information. You can also ask directly: "What did we decide about the database?" or "Show me sessions from last week."

### What You'll See

When your first session starts in a new project, Claude will:
- Greet you and confirm it has brain access
- Show you any notes from your last session (if any exist)
- Be ready to search your full conversation history across all projects

If something isn't working, run `/brain-health` to check all 9 diagnostic points.

### Adding a New Project

Use the standalone add-project script (no need to re-run the full setup). You must be in the claude-brain root folder:

```bash
cd ~/path/to/claude-brain          # go to your claude-brain root folder
python3 scripts/add-project.py     # creates a new project subfolder here
```

The script will:
1. Read your existing config.yaml (won't duplicate projects)
2. Ask for folder name, prefix, and label
3. Create the project folder with a CLAUDE.md (includes session protocols)
4. Update config.yaml with the new project
5. Register the project in the database (project_registry table)
6. Register the brain-server MCP so Claude can access the brain from that folder
7. Detect other MCP servers on your root path (like web search) and offer to register them too

Alternatively, re-run the full setup script -- it's safe to run anytime:

```bash
python3 scripts/brain-setup.py
```

### Naming Rules

| Field | Rule | Example |
|-------|------|---------|
| Folder name | Lowercase, hyphens only | `my-website`, `book-project` |
| Prefix | Lowercase, 2-3 characters | `mw`, `bk`, `gen` |
| Label | Plain English, any format | `My Website`, `Book Project` |

### What CLAUDE.md Does in Each Project Folder

Every project folder has a CLAUDE.md that Claude Code auto-loads at session start. It contains:

- **Project identity** -- name, prefix, label
- **Brain connection** -- tells Claude the MCP tools exist and how to use them
- **Session protocols** -- start-session and end-session checklists (see below)
- **Project-specific rules** -- anything unique to that project

This is what makes the brain work across projects. Without CLAUDE.md, Claude doesn't know the brain exists in that folder.

### Session Protocols (Start and End)

Session protocols keep your brain accurate and your context continuous across sessions.

**Start-session protocol** (runs automatically via hook + CLAUDE.md instructions):
- Hook injects last session notes, unfinished items, and a verification checklist
- Claude searches the brain for recent context
- Claude reads the project tracker (if applicable)
- Claude presents unfinished items for you to review before starting new work

**End-session protocol** (triggered when you say "end session"):
- Session notes are written to the database
- Project summary is updated
- Governance files are updated (tracker, feature plan)
- You're asked: "Anything you want Claude to know next session?"
- Your answer is saved to NEXT_SESSION.md (see below)
- Changes are committed and pushed

Without the end protocol, session notes never get written and tomorrow's Claude starts from scratch. Without the start protocol, Claude skips context it already has. Both matter.

### NEXT_SESSION.md (Cross-Session Memory)

NEXT_SESSION.md is how you pass messages to your next session with zero friction:

1. At end of session, Claude asks: "Anything you want Claude to know next session?"
2. Your answer (plus a session summary) is written to NEXT_SESSION.md in the project folder
3. Next session, the session-start hook reads NEXT_SESSION.md automatically and injects it into Claude's context

You never have to type "read the notes file" or paste anything. The hook handles it. The file is gitignored (it's personal context, not code).

### The Manual Way (advanced)

If you prefer to add a project without the script:

1. **Edit `config.yaml`** -- add entries under `projects:` and `jsonl_project_mapping:`:
   ```yaml
   projects:
     - folder_name: "my-website"
       prefix: "mw"
       label: "My Website"

   jsonl_project_mapping:
     "my-website": "mw"
   ```

2. **Create the folder** inside your claude-brain directory:
   ```bash
   mkdir my-website
   ```

3. **Create a CLAUDE.md** inside the new folder -- copy from an existing project
   folder and update the project name, prefix, and label. Include the session
   protocol checklist tables.

4. **Register MCP** so Claude can access the brain from this folder:
   ```bash
   claude mcp add brain-server python3 /path/to/claude-brain/mcp/server.py
   ```

5. **Restart Claude Code** -- the startup hook will register the new project automatically.

---

## 11. TROUBLESHOOTING

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
- **Check:** Log files in `logs/<hostname>/` - each hook has its own log
- **Common cause:** Hook path changed after moving files. Paths must be absolute.

### "Search returns no results"
- **Check status:** `python3 scripts/status.py` - are there messages in the DB?
- **Check FTS5:** The search uses keywords, not exact phrases. Try fewer/different words.
- **Check project filter:** If you said "search JG for X" but the data is in GEN,
  you won't find it. Try without a project filter.
- **Tip:** Short prompts (<15 chars) are skipped by the user-prompt-submit hook.

### "Session data is missing"
- **Check:** Did the session end normally? If Claude Code crashed, the session-end
  hook may not have fired. But the stop hook captures data on every exchange,
  so most data is still there.
- **Check:** `python3 scripts/status.py` - compare message counts before and after.

### "Import failed for claude.ai file"
- **Check:** Is it valid JSON? The file must be a claude.ai export, not a raw copy.
- **Check:** Does the file have `chat_messages` and `uuid` fields?
- **Check log:** `logs/<hostname>/import_claude_ai.log`

### "Database is locked"
- **Cause:** Another process is writing. The DB uses WAL mode with 5-second timeout.
- **Fix:** Wait a moment and try again. If persistent, check for stuck processes.

---

## 12. WHAT THE BRAIN CANNOT DO (YET)

| Limitation | Why | When It Gets Fixed |
|-----------|-----|-------------------|
| **Python 3.10+** | Tested on 3.13 and 3.14. Older 3.10+ versions should work but are untested. | Expand testing matrix |
| **Single-user design** | One person, one database. No multi-user support. | Not planned - personal memory tool |
| **Semantic search cold-start ~4-5s** | First query loads embedding model into memory | Subsequent queries are fast (<100ms) |
| ~~**Keyword search is exact-match**~~ | ~~Typos won't match~~ | **DONE** - Fuzzy search auto-corrects typos before the FTS query. "sesion" now finds "session". |
| **No auto-capture from claude.ai** | Claude.ai has no hook system | Manual export + import required |
| **No cross-machine real-time sync** | DB is local; Dropbox syncs project files but not the DB | Planned: DB in Dropbox or sync script |
| **Summaries require normal exit** | session-end hook only fires on clean exit | If Claude Code crashes, summary is lost (but exchanges are saved) |
| **No web UI** | CLI-only via Claude Code | Post-MVP consideration |
| **No automatic fact extraction** | Project facts and decisions are populated via setup questionnaire and scripts. The brain captures all conversations (so the data exists), but doesn't yet auto-extract structured facts from them. | Deferred - value thin after session note quality improvements. Search paths cover recall. |
| **No lessons learned extractor** | Requires pattern mining across sessions | Post-MVP: find "mistake"/"redo"/"should have" patterns |

See `POST_MVP_ROADMAP.md` for the full roadmap and planned fixes.

---

## QUICK REFERENCE CARD

### Ask Claude (natural language)
```
"Search the brain for [topic]"
"Find anything related to [concept]"
"What was decided about [topic]?"
"What happened in yesterday's session?"
"Show me my worst sessions and what went wrong"
"What does the brain know about me?"
"What's the current state of the [project] project?"
```

### Slash Commands (direct access)
```
/brain-question    Ask anything - runs keyword + semantic + facts + decisions
/brain-search      Raw transcript search with excerpts
/brain-history     Session timeline (one line per session)
/brain-recap       Progress report by project for a time range
/brain-decide      Decision lookup by number or keyword
/brain-health      Full 9-point system diagnostic
/brain-status      Quick database stats
/brain-import      Import conversations (Claude.ai, ChatGPT, Gemini)
/brain-topics      Browse sessions by tag -- drill into any topic
/brain-tag-review  Batch tag review -- generate spreadsheet, edit, update
/brain-questionnaire   Fill out or update your profile
/brain-setup       Re-run setup to add projects or fix config
/brain-export      Export brain data to text files
/brain-consistency Automated doc + data consistency check
```

---

## Questions, Bugs, and Feature Requests

- **Bug reports:** [GitHub Issues](https://github.com/mikeadolan/claude-brain/issues)
- **Feature requests:** [GitHub Issues](https://github.com/mikeadolan/claude-brain/issues)
- **Questions and discussion:** [GitHub Discussions](https://github.com/mikeadolan/claude-brain/discussions)
