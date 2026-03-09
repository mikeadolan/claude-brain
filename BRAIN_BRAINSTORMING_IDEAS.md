# BRAIN EXPANSION — BRAINSTORMING IDEAS

**Created:** 2026-03-09 (Session 9)
**Context:** Brain v0.1 is 51/52 steps complete. 116 sessions, 13,377 transcripts, 115 LLM summaries, semantic search, structured facts/decisions across 5 weeks and 4 active projects. Discussing what the brain can do beyond v0.1.

---

## TIER 1: Force Multipliers (change how you work)

### 1. Monday Morning Briefing (cron + email)
**Status:** APPROVED — build this session
A Python script runs at 7am Monday via cron. Queries the brain for all sessions in the past week, groups by project, and emails a digest:
- What got done per project
- Decisions made
- What was left unfinished (sessions that ended with "next step" notes)
- Projects that went dormant (no activity in 7+ days)

Zero tokens. Pure Python + SMTP. Highest-ROI feature.

### 2. Dormant Project Alerts (cron)
**Status:** APPROVED — build this session
Same mechanism as #1. If a project has no session in X days, send a nudge email. "Johnny Goods: no activity in 12 days. Last session was Step 8C-R1." Keeps things from falling through the cracks.

---

## TIER 2: Intelligence Layer (brain gets smarter)

### 3. Project Handoff Generator
One command: `/brain-handoff jg` — generates a complete briefing document from brain data. Timeline of sessions, key decisions, current state, open items, file inventory. Useful for bringing someone up to speed or restarting after a long break.

### 4. Decision Audit Trail
Link decisions to sessions where they were made. Track reversals (e.g., "Decision 77 was ChromaDB, Decision 89 replaced it"). Query: "show me every decision about search" or "what decisions got reversed and why?"

### 5. Cross-Session Pattern Detection
Mine 115+ summaries for patterns:
- "You've hit token limits in 8 sessions — all on claude.ai, all Steps 3+"
- "You spend 40% of JG sessions on infrastructure, not writing"
- "Every brain session runs 45+ minutes"

The brain tells you things about your own workflow you can't see.

### 6. Personal Code Pattern Memory
"How did I set up MCP servers?" "What was the cosine similarity approach?" Instead of re-reading old code, the brain has every code block ever discussed. A smarter /brain-question tuned for code retrieval.

---

## TIER 3: Platform Play (brain becomes infrastructure)

### 7. OpenClaw Killer — Universal Memory Layer
**Status:** HIGH INTEREST — exploring architecture and business model
The big one. Brain currently only works in Claude Code. But the MCP server + SQLite architecture could serve:
- claude.ai (via MCP in web client, if/when Anthropic enables it)
- API calls (any script can query the DB directly)
- Other AI tools (anything that speaks MCP or HTTP)

Foundation already exists. Gap is an HTTP API wrapper around the MCP tools — a simple Flask/FastAPI server exposing the same 10 functions as REST endpoints. Then anything can query the brain.

See dedicated section below for deep-dive on this idea.

### 8. Multi-Project Intelligence
"Find every time I discussed API authentication across all projects." Cross-project search already works but is underutilized. Dedicated command for finding unexpected connections between projects.

---

## TIER 4: Content-Specific (johnny-goods power tools)

### 9. Writing Research Assistant
With 5,015+ JG transcripts in the brain: "Find every time we discussed Fat Tony's relationship with Johnny's father" or "What did we decide about the timeline for Chapter 7?" Partially working via /brain-question, could be purpose-built for manuscript research.

### 10. Session Replay
"Show me what happened in the session where we rewrote Chapter 3." Full transcript retrieval, not just summary. For when you need the actual back-and-forth.

---

## DEEP DIVE: #7 — OpenClaw Killer

### The OpenClaw Problem
OpenClaw does flat text snippets stored in the cloud. Every AI session gets the same blob injected.
No structure, no search, no project separation, no semantic understanding. It's a notepad with auto-inject.

**OpenClaw's known pain points:**
- Memory fills up fast (limited slots)
- No way to search — whole blob or nothing
- No structure — everything is a flat string
- No project isolation
- Cloud-hosted — your data lives on someone else's server
- Paid tiers for more memory slots

**What the brain already does better:**
- Structured data (facts, decisions, preferences — not flat text)
- Semantic search (meaning-based, not just keyword)
- Project-aware (jg sessions don't pollute js context)
- FTS5 full-text search across all transcripts
- LLM-generated session summaries, searchable
- 10 MCP tools for targeted retrieval
- Proactive outreach (email digests — OpenClaw can't do this)

### Strategy: Open Source Acquisition Play

**The logic chain:**
1. Open source it, free, "your data stays local" as the core pitch
2. Get stars, forks, community contributions
3. Become the de facto memory layer for Claude Code users
4. Anthropic / OpenAI / others have three choices:
   - Build it themselves (but we're already there with community momentum)
   - Integrate it (partnership / hire)
   - Acquire it (buy the project + hire the person who understands the problem)

**Why this beats SaaS monetization:**
- No hosting liability, no user data storage, no compliance burden
- Don't compete with Anthropic — get them to notice
- Open source builds trust and adoption faster than any marketing
- Negotiate from strength ("2K stars, active community") not weakness
- One person can't run a SaaS with user data — that's a full-time company

**Why this is credible (not fantasy):**
- The brain works end-to-end (auto-capture via hooks, MCP serves it back, no manual tagging)
- Architected properly (SQLite + local-first + semantic search, not a hack)
- Solves a real pain point every Claude Code user has (context loss between sessions)
- Extensible (MCP server means any AI tool can plug in)

**The risk:** Anthropic builds it themselves. Counter: if they were going to, they would have.
The fact that OpenClaw exists and is popular = demand Anthropic isn't filling. An established
open source alternative with community gives leverage, not less. That's when the phone rings.

### What the brain does that OpenClaw can't
1. **Proactive intelligence** — emails you weekly digests, dormant project alerts (brain reaches OUT to you)
2. **Semantic search** — "find discussions about authentication" finds results even if that word wasn't used
3. **Project isolation** — 5 projects, zero cross-contamination unless you ask for it
4. **Structured memory** — facts, decisions, preferences with categories, not flat text blobs
5. **Session awareness** — knows what happened when, can generate timelines and handoff docs
6. **Unlimited local storage** — SQLite handles millions of rows, no paid tiers
7. **Privacy by design** — data never leaves your machine

---

## CLARIFICATION: Email Automation (#1 + #2)

This is NOT email as a platform for AI memory (that's what OpenClaw does across messaging platforms).

This is the brain emailing YOU proactive status reports:
- **Monday briefing:** Weekly digest of all project activity, decisions, dormant projects
- **Dormant alerts:** "Johnny Goods: no activity in 12 days"
- **Mechanism:** cron job on your machine, Python script queries local DB, sends via Gmail SMTP
- **Cost:** Zero tokens, zero API calls, pure local script

This matters for the open source play because it shows the brain is a different CATEGORY
of tool, not just "better OpenClaw." OpenClaw injects memory into sessions. The brain
reaches out to you proactively.

---

## WORK ITEM: Convert Hooks from Bash to Python (Windows Support)

**Why:** Hooks are bash scripts. Windows users can't run them without WSL. Rewriting
as pure Python makes Linux/Mac/Windows all work with zero platform-specific code.

**Current state of each hook:**

| Hook | Bash lines | Python lines (inline) | Bash-specific logic | Conversion |
|------|-----------|----------------------|---------------------|------------|
| session-start.sh | 10 | 80 | ROOT resolve, stdin drain, empty fallback | Easy |
| user-prompt-submit.sh | 9 | 140 | ROOT resolve, stdin read, empty fallback | Easy |
| stop.sh | 17 | 0 (calls write_exchange.py) | Path encoding (sed), file listing (ls -t), JSONL detection | Medium |
| session-end.sh | 20 | 10 (inline project detect) | Same as stop.sh + calls brain_sync.sh | Medium |

**What needs to happen:**
1. Convert 4 hooks from .sh to .py (~2 hours)
2. Convert brain_sync.sh to Python (~30 min)
3. Replace bash-specific patterns:
   - `sed 's|^/|-|; s|/|-|g'` → `os.path` manipulation
   - `ls -t *.jsonl | head -1` → `glob + sorted by mtime`
   - `cat > /dev/null` → `sys.stdin.read()`
4. Update hook registration in ~/.claude/settings.json (.sh → .py)
5. Confirm Claude Code executes Python hooks on all platforms
6. Test on Linux, Mac (beta tester), Windows (need a box or WSL)

**Key insight:** All 4 bash scripts are thin wrappers around Python that's already written.
The conversion is straightforward — half-day of work, not a rewrite.

**brain_sync.sh** also needs conversion (backup script called by session-end). Currently
bash with sqlite3 CLI fallback. Python equivalent is simpler (shutil.copy2 + sqlite3 integrity_check).

---

## PRIORITY ORDER (Mike's input, Session 9)
1. Email automation (#1 + #2) — build now, proves the brain is a different category
2. Hook conversion (bash → Python) — required for Windows support
3. OpenClaw killer (#7) — open source acquisition play, not SaaS
4. Onboarding polish — brain-setup.py must be bulletproof (Windows + Mac + Linux)
5. Go public on GitHub (currently private)
6. Community push (Claude Code Discord, r/ClaudeAI, Hacker News)
7. Everything else — revisit after adoption
