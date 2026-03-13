# CLAUDE-BRAIN MVP — PROJECT TRACKER

**Created:** 2026-03-03
**Last Updated:** 2026-03-13 (Session 40: Documentation Cleanup section 9.27-9.33 added, checklist updated)
**Source Plan:** CLAUDE_BRAIN_MVP_PLAN.txt (root)

Status Key: `[x]` Done | `[ ]` Not started | `[>]` In progress | `[-]` Skipped/Deferred

---

## PHASE 0: Governance & Process

| # | Step | Status | Date | Notes |
|---|------|--------|------|-------|
| 0.1 | Create PROJECT_TRACKER.md | [x] | 2026-03-03 | This file |
| 0.2 | Create verification/fixtures/ folder | [x] | 2026-03-03 | For test data |
| 0.2a | Create FOLDER_SCHEMA.md (living) | [x] | 2026-03-03 | Replaces outdated claude-brain_folder_schema.txt |
| 0.3 | Create verification/TEST_SPECIFICATIONS.md | [x] | 2026-03-03 | 100 test cases across 11 components |
| 0.4 | Create verification/SCRIPT_CONTRACTS.md | [x] | 2026-03-03 | 8 scripts + 4 hooks + MCP server. ChromaDB blocker flagged. |
| 0.5 | Create DEPENDENCIES.md (living) | [x] | 2026-03-03 | All packages, tools, services. Version matrix. ChromaDB blocker options. |
| 0.6 | Create .gitignore | [x] | 2026-03-03 | Prevents personal data from reaching GitHub. Must exist before git init. |
| 0.7 | Add build-phase decisions log to tracker | [x] | 2026-03-03 | See DECISIONS section below. |

---

## PHASE 1: Infrastructure (Session B)

| # | Step | Status | Date | Audit | Notes |
|---|------|--------|------|-------|-------|
| 1.1 | Create missing folders | [x] | 2026-03-02 | Pass | Created /home/mikedolan/claude-brain-local/ |
| 1.2 | Deploy config.yaml | [x] | 2026-03-02 | Pass | Replaced old config with config_mvp.yaml content |
| 1.3 | Create SQLite database (10 tables, 5 indexes, FTS5) | [x] | 2026-03-02 | 58/58 | Audit: verification/AUDIT_REPORT_2026-03-03_phase1_database.txt |
| 1.4 | Install semantic search dependencies | [x] | 2026-03-02 | Pass | chromadb, sentence-transformers, mcp installed via pip3 |

---

## PHASE 2: Core Scripts (Session B)

| # | Step | Status | Date | Audit | Notes |
|---|------|--------|------|-------|-------|
| 2.1 | Build ingest_jsonl.py | [x] | 2026-03-06 | 57/57 | Fixtures (10 files) + script (309 lines) + test suite. Handles all 6 JSONL types, image blocks, Windows paths. |
| 2.2 | Test ingestion against real JSONL files | [x] | 2026-03-06 | 92/92 | 41 main + 28 subagent + 23 tool-result. 5062 records, 0 errors, 0 integrity issues. |
| 2.3 | Build startup_check.py | [x] | 2026-03-06 | 25/25 | Folder verify, file discovery, ingest delegation, backup with rotation + integrity check. |
| 2.4 | Build write_exchange.py | [x] | 2026-03-06 | 31/31 | Live capture, session upsert, ChromaDB gated. T-WRITE-04 deferred (ChromaDB blocked). |
| 2.5 | Build generate_summary.py | [x] | 2026-03-06 | 22/22 | Pure Python (no LLM). Structured summary: topic, counts, decisions, files. 50-line cap. |

---

## PHASE 3: Support Scripts (Session B)

| # | Step | Status | Date | Audit | Notes |
|---|------|--------|------|-------|-------|
| 3.1 | Build import_claude_ai.py | [x] | 2026-03-06 | 24/24 | Parses claude.ai JSON, maps sender, dedup, moves to completed/. |
| 3.2 | Build brain_sync.sh | [x] | 2026-03-06 | 15/16 | Rotating backup, integrity check (python fallback). 1 cosmetic test assertion. |
| 3.3 | Build status.py | [x] | 2026-03-06 | 17/17 | Human + JSON output. Sessions, messages, projects, backup, semantic status. |
| 3.4 | Build copy_chat_file.py | [x] | 2026-03-06 | 14/14 | Copies to chat-files/{date}_{time}_{session[:8]}/. Validates project prefix. |

---

## PHASE 4: Hooks & Full Ingest (Session C)

| # | Step | Status | Date | Audit | Notes |
|---|------|--------|------|-------|-------|
| 4.1 | Build session-start.sh hook | [x] | 2026-03-07 | Pass | 68 lines. Runs startup_check.py, queries sys_session_summaries, returns additionalContext JSON. No set -e (must always output valid JSON). |
| 4.2 | Build user-prompt-submit.sh hook | [x] | 2026-03-07 | Pass | 117 lines. FTS5 search on user prompt (ChromaDB fallback). Skips <15 char prompts, filters stop words, caps 8 keywords. Top 3 results. |
| 4.3 | Build stop.sh hook | [x] | 2026-03-07 | Pass | 33 lines. Detects session JSONL from CWD encoding, calls write_exchange.py. |
| 4.4 | Build session-end.sh hook | [x] | 2026-03-07 | Pass | 47 lines. Detects session ID + project prefix, calls generate_summary.py and brain_sync.sh. |
| 4.5 | Register hooks in ~/.claude/settings.json | [x] | 2026-03-07 | Pass | All 4 hooks registered with empty matcher (fires for all projects). Absolute paths. |
| 4.6 | Run full ingest of all archived files | [x] | 2026-03-07 | Pass | 94 files ingested via session-start.sh hook test. 43 sessions, 5583 transcripts. Config mapping fix: added "claude-brain": "mb". Fixed 7 sessions (1232 transcripts) from oth→mb. |
| 4.7 | Run status.py to verify ingest | [x] | 2026-03-07 | Pass | 43 sessions, 5583 transcripts across all projects. O.2 resolved: hook stdin/stdout protocol verified. |

---

## PHASE 5: MCP Server (Session C)

| # | Step | Status | Date | Audit | Notes |
|---|------|--------|------|-------|-------|
| 5.1 | Build MCP server (mcp/server.py) — 10 functions | [x] | 2026-03-07 | Pass | 348 lines. FastMCP SDK. 10 read-only tools: get_profile, get_project_state, search_transcripts, get_session, get_recent_sessions, lookup_decision, lookup_fact, get_recent_summaries, search_semantic, get_status. ChromaDB gated. Recency bias on search_transcripts + lookup_fact. |
| 5.2 | Register MCP server with Claude Code | [x] | 2026-03-07 | Pass | Added to ~/.claude.json for johnny-goods and claude-brain projects. Removed from mike-brain (not a separate project). |
| 5.3 | Test every MCP function | [x] | 2026-03-07 | 9/10 | All 9 non-semantic functions tested via JSON-RPC. "chapter" search returned results. "Fat Tony" lookup fixed (values updated to include character names). |
| 5.4 | Test semantic search (meaning-based queries) | [x] | 2026-03-07 | Pass | Decision 89: ChromaDB replaced with SQLite+numpy. 2,377 transcripts embedded. Cosine similarity verified. "illegal gambling" and "Fat Tony" queries return relevant results. |
| 5.5 | Deploy CLAUDE.md to each project folder (7 projects) | [x] | 2026-03-07 | Pass | 6 project CLAUDE.md files deployed (jg, jga, gen, js, lt, oth). mike-brain excluded (not a separate project). Brain connection template in each. |
| 5.6 | Integration test: full session lifecycle | [x] | 2026-03-07 | Pass | Full lifecycle simulated: SessionStart → UserPromptSubmit → Stop → SessionEnd. All data flows verified. |
| 5.7 | Test user-prompt-submit hook (memory injection) | [x] | 2026-03-07 | Pass | FTS5 search verified — "chapter" and "session" queries returned relevant results. "ASUS laptop" returned nothing (expected: that data is in claude.ai import, not yet imported). |
| 5.8 | Fix issues found | [x] | 2026-03-07 | Pass | Fixed: config mapping "claude-brain"→"mb", 7 sessions retagged oth→mb, Fat Tony lookup values updated, mike-brain/CLAUDE.md removed. |

---

## PHASE 6: Data Population (Session D)

| # | Step | Status | Date | Audit | Notes |
|---|------|--------|------|-------|-------|
| 6.1 | Populate brain_facts from questionnaire | [x] | 2026-03-07 | Pass | 98 brain_facts (8 categories), 38 brain_preferences (4 categories), 47 JG project facts (4 categories). Source: MIKES_BRAIN_QUESTIONNAIRE.txt with Y/R corrections. |
| 6.2 | Populate decisions table (75+ locked decisions) | [x] | 2026-03-07 | Pass | 32 decisions (52-83) inserted. Source: MVP Plan Section 11 (52-76) + Tracker BUILD-PHASE DECISIONS (77-83). MCP lookup verified. |
| 6.3 | Populate facts table (JG characters, timeline, etc.) | [x] | 2026-03-07 | Pass | 84 total facts: JG 63 (13 char, 11 ch, 17 book, 6 status, 3 parts, 5 char, 4 timeline, 4 location), JS 15 (5 deliverable, 6 strategy, 4 status), GEN 6 (setup). MCP lookup verified. |
| 6.4 | Test cross-project search | [x] | 2026-03-07 | 9/10 | 10-point test suite: cross-project FTS5, filtered search, recency bias, facts/decisions span, FTS5 sync, session coverage. 1 false-fail: empty content 65% is expected (tool_result records have no text). All MCP tools verified. |
| 6.5 | Test session continuity (close, reopen, hook recovery) | [x] | 2026-03-07 | 8/8 | Live session verified: 268+ msgs committed, WAL clean, previous summary exists, backup 1.5hrs old, all 4 hooks registered + tested. session-start returns context, user-prompt-submit returns FTS5 memories. |
| 6.6 | Investigate memory/ folders from Windows archive | [x] | 2026-03-07 | Pass | 5 memory/ folders found in jsonl-archive/windows/projects/ — all empty. Placeholder dirs created by Claude Code auto-memory but never populated. O.1 resolved. |
| 6.7 | Laptop switch test (if second laptop available) | [-] | 2026-03-07 | Deferred | Second laptop not set up. Will test when available. Not blocking Go Live. |

---

## PHASE 7: Go Live & Open Source (Session E+)

| # | Step | Status | Date | Audit | Notes |
|---|------|--------|------|-------|-------|
| 7.1 | Create CLAUDE_BRAIN_HOW_TO.md (complete user guide) | [x] | 2026-03-07 | Pass | 11 sections: overview, automatic hooks, search types, all 10 MCP tools with examples, import guide, status checks, troubleshooting, limitations, quick reference card. |
| 7.2 | Live brain test — 10 specific queries with expected results | [x] | 2026-03-07 | 10/10 | 4 bugs found+fixed: FTS5 AND→OR, apostrophe escape, hook project bias, CLAUDE.md routing rules. All 10 test queries return correct results. MCP fix verified via direct Python (server restart needed). |
| 7.3 | Run brain in JG project — verify cross-project MCP works | [x] | 2026-03-07 | 7/7 | get_profile, get_project_state, lookup_fact, lookup_decision, search_transcripts — all pass. Cross-project search verified. MCP fix live. |
| 7.4 | Create brain-setup.py (first-run installer for new users) | [x] | 2026-03-08 | Pass | Built (~1432 lines, 8 phases). 5 slash commands (brain- prefix). /brain-import tested (2 files, 23 msgs). /brain-status tested (bug found+fixed: conn.close before semantic query). /brain-question built (brain_query.py, Decision 94). |
| 7.5 | Create README.md (GitHub landing page) | [x] | 2026-03-07 | Pass | 15 sections: problem, architecture, quick start, hooks, slash commands, MCP tools, folder tree, requirements. No personal data. |
| 7.6 | Security audit — review .gitignore, scan for personal data leaks | [x] | 2026-03-07 | Pass | 27+ files cleaned. .gitignore expanded (+30 rules). All fixtures/docs sanitized. Final scan: 32 files, zero personal data. |
| 7.7 | Git init + first commit + create GitHub repo + push | [x] | 2026-03-08 | Pass | gh auth fixed (PAT method, Decision 98). Repo: github.com/mikeadolan/claude-brain (PRIVATE, Decision 96). 3 commits pushed. Co-Authored-By removed (Decision 97). |
| 7.8 | Beta tester onboarding — friend clones, runs setup, tests | [ ] | | | Mac user. Verify setup script works, HOW_TO is clear, brain populates from scratch. |
| 7.9 | Document known limitations and post-MVP roadmap | [x] | 2026-03-08 | Pass | POST_MVP_ROADMAP.md rewritten: 12 known limitations (4 categories), stale entries fixed, resolved items marked done. README.md updated with limitations section. |

---

## SUMMARY

| Phase | Description | Steps | Done | Remaining |
|-------|------------|-------|------|-----------|
| 0 | Governance & Process | 8 | 8 | 0 |
| 1 | Infrastructure | 4 | 4 | 0 |
| 2 | Core Scripts | 5 | 5 | 0 |
| 3 | Support Scripts | 4 | 4 | 0 |
| 4 | Hooks & Full Ingest | 7 | 7 | 0 |
| 5 | MCP Server | 8 | 8 | 0 |
| 6 | Data Population | 7 | 6 | 1 (deferred) |
| 7 | Go Live & Open Source | 9 | 8 | 1 |
| **TOTAL** | | **52** | **51** | **1** |

---

## FUTURE WORK — Remove MCP Server

**Problem:** Claude Code has an upstream bug (GitHub #5506, #1935, #7718, #18127) that shows "1 MCP server failed" on every /exit for ALL MCP servers — including Anthropic's own reference implementation. Cannot be fixed server-side. Bug has been open since CC v1.0.63 (mid-2025), repeatedly auto-closed by bot.

**Solution:** Remove MCP server entirely. Replace with direct Python script calls via Bash.
- Every MCP tool already has a script equivalent (brain_query.py, status.py, etc.)
- Hooks already inject context automatically (session-start, user-prompt-submit)
- Slash commands already provide manual access (/brain-search, /brain-decide, etc.)
- Gains: no error on /exit, ~5s faster startup, simpler architecture, one less dependency
- Loss: Claude can't silently query brain mid-conversation (must use Bash calls to scripts instead)
- Keep mcp/server.py in repo as optional for users who want it

**Steps (when ready):**
1. Remove MCP server registration from ~/.claude.json
2. Ensure every MCP tool has a callable script equivalent
3. Update CLAUDE.md routing to use scripts instead of MCP tools
4. Update brain-setup.py to skip MCP registration
5. Update docs (README, HOW_TO, ARCHITECTURE)
6. Test full session lifecycle without MCP

---

## POST-MVP DEFERRED — Slash Commands

Do NOT build these in v0.1. Add after MVP is complete.

| Command | Description | Notes |
|---------|------------|-------|
| `/brain-forget` | Delete specific records from database | Needs confirmation dialogs and undo capability. Too dangerous for v0.1. |
| `/brain-tag` | Tag management for conversations | Decision 54, already deferred. |
| `/brain-sync` | Manual sync trigger | Hooks handle automatically. Terminal command brain-sync already exists. |
| `/brain-health` | Full 9-point health check (database, space, data sync, backup, performance, deps, MCP, hooks, config) | DONE (session 6). Renamed from /brain-doctor (Decision 100). scripts/brain_health.py. |

---

## BUILD-PHASE DECISIONS

Decisions made during the build (continues from planning decisions 52-76 in MVP Plan v4).

| # | Decision | Date | Context |
|---|----------|------|---------|
| 77 | ChromaDB blocked on Python 3.14 — all semantic search code gated behind try/except. Scripts work fully without it. Re-evaluate at Step 2.4. | 2026-03-03 | pydantic v1 incompatible with Python 3.14. Options: install Python 3.13, wait for fix, replace with SQLite+numpy, or defer. |
| 78 | sqlite3 CLI not needed — status.py covers all DB visibility. Downgraded to optional. | 2026-03-03 | Mike is architect, not coder. No manual SQL queries needed. |
| 79 | gh CLI installed and authenticated (mikeadolan). Git + gh = complete GitHub workflow for open source. | 2026-03-03 | MIT license, github.com/mikeadolan/claude-brain |
| 80 | .gitignore created before git init. Personal data (DB, JSONL, logs, chapters, chat-files) excluded from version control. | 2026-03-03 | Security-critical for public repo. |
| 81 | generate_summary.py uses pure Python (no LLM). claude -p hangs when called from inside a Claude Code session. Structured mechanical summary instead. | 2026-03-06 | O.3 confirmed: nested claude sessions blocked. Fallback: extract topic, counts, decisions, file refs. |
| 82 | Added "claude-brain": "mb" to config.yaml jsonl_project_mapping. CWD folder is claude-brain, not mike-brain. Sorted before mike-brain entry. | 2026-03-07 | 7 sessions (1232 transcripts) were tagged 'oth' before fix. Corrected via SQL UPDATE on sys_sessions + transcripts. |
| 83 | mike-brain/ folder kept as-is with .gitignore exclusion. Not a separate project — no CLAUDE.md, no MCP registration. Will rename or exclude before GitHub push. | 2026-03-07 | Contains legacy Windows-era configs, archives, history. Added to .gitignore. |
| 84 | import_claude_ai.py bug fix: content extraction from claude.ai JSON. Top-level `text` field is empty in newer exports; actual content is in `content[]` blocks (list of dicts with `text` key). Fixed to prefer `content[]` blocks, fall back to `text` field. | 2026-03-07 | 676/716 gen transcripts had empty content before fix. After fix: 66/716 empty (normal — thinking blocks have no text). All 8 claude.ai imports re-imported with correct content. |
| 85 | Phase 7 rewritten from 5 vague steps to 9 concrete steps. brain-setup.py moved IN to MVP scope (was deferred as Decision 55). Beta tester on Mac — setup script must support Linux + macOS. Step 6.7 (laptop switch) deferred. | 2026-03-07 | Friend wants to beta test. Can't ship without installer + user guide + security audit. HOW_TO.md is step 7.1 and drives all testing. |
| 86 | MCP search_transcripts rewritten: auto-converts natural language to FTS5 OR queries. Strips stop words, escapes apostrophes, caps 10 keywords. Preserves explicit FTS5 syntax (OR/AND/NOT/quotes) as pass-through. | 2026-03-07 | Multi-word queries returned 0 results (AND logic). Apostrophes caused FTS5 syntax errors. Both fixed. |
| 87 | user-prompt-submit hook improved: CWD-based project detection biases 2/3 results toward current project. Falls back to global search for remaining slots. Deduplicates by content prefix. | 2026-03-07 | Hook was returning results from wrong projects. Now biases toward the project folder you're working in. |
| 88 | All 5 project CLAUDE.md files updated with explicit TOOL ROUTING section. Maps natural language patterns to specific MCP tools. Replaces vague "SEARCH PRIORITY" with concrete routing table. | 2026-03-07 | Claude needs explicit instructions to pick the right MCP tool. Routing table covers all common query patterns. "brain" keyword NOT required. |
| 89 | Replace ChromaDB with SQLite+numpy for semantic search. New table `transcript_embeddings` in existing DB. sentence-transformers generates 384-dim embeddings, numpy does cosine similarity. Eliminates Python 3.14 blocker, reduces deps from ~20 to 2, identical search quality. | 2026-03-07 | ChromaDB overkill for <100K records. Both sentence-transformers and numpy work on 3.14. Simpler for open source. 10K cosine sim = 9.4ms. |
| 90 | brain-setup.py: interactive project creation with lowercase + hyphens only enforcement. Auto-generate prefix. At least 1 project required, defaults to "general". | 2026-03-07 | Beta tester is non-technical. Interactive loop more user-friendly than editing config files. |
| 91 | config.yaml added to .gitignore. brain-setup.py generates it from scratch with detected paths. Ship config.yaml.example for reference. Zero personal data in generated config. | 2026-03-07 | Prevents personal paths/data from reaching GitHub. |
| 92 | brain-setup.py: 7 phases (pre-flight+deps, project setup, directories, database, config, registration, health check). Idempotent — safe to re-run to add projects. | 2026-03-07 | Clean structure, each phase flows into the next. Claude Code required (hard stop if missing). |
| 93 | Custom slash commands must use brain- prefix to avoid conflicts with built-in Claude Code skills. /import renamed to /brain-import. All 4 commands: brain-import, brain-status, brain-setup, brain-questionnaire. | 2026-03-07 | /import triggered the claude-api skill (keyword "import" matched skill trigger). Built-in skills take priority over custom commands. |
| 94 | /brain-question uses local Python script (brain_query.py) instead of subagent. Subagent approach cost 30K tokens + showed UI noise. Script does FTS5 + semantic search locally (zero API tokens), returns formatted results for Claude to synthesize (~3-5K tokens total). 5th slash command added. | 2026-03-08 | Subagent was 46 seconds, 30K tokens. Script is <5 seconds, ~3K tokens. MCP stays available for Claude's autonomous brain access. |
| 95 | No personal identity in public repo. LICENSE copyright = "claude-brain contributors". Contact via GitHub Issues + Discussions only. No personal name or email in README or LICENSE. | 2026-03-07 | Mike deferred identity decision. GitHub handle visible via repo ownership but not embedded in files. |
| 96 | Repo starts PRIVATE for beta testing. Will switch to public when Mike is ready. Do NOT create public repos without asking. | 2026-03-08 | Claude created repo as public without asking — mistake. Immediately switched to private. |
| 97 | No Co-Authored-By lines in commits. Mike is sole visible author on GitHub. Do not add AI attribution to commits. | 2026-03-08 | Co-Authored-By caused "claude Claude" to appear as a contributor on the GitHub repo page. Removed via filter-branch. |
| 98 | gh auth on Fedora uses PAT method (--with-token), not device flow (--web). xdg-open fails silently on Fedora — browser never opens, CLI polls forever. | 2026-03-08 | Three failed attempts with device flow. PAT works immediately. Token stored in gnome-keyring. |
| 99 | API key for LLM summaries stored directly in config.yaml (gitignored). Supports Anthropic + OpenRouter providers. Falls back to pure Python if no key. Avoids env var confusion for non-coders. | 2026-03-08 | Direct API call to OpenRouter/Anthropic bypasses claude -p hang (resolves Decision 81). ~$1/month for Haiku. |
| 100 | Renamed /brain-doctor to /brain-health (simpler, more intuitive). 9-point health check: database, disk space, data sync, backup, performance, dependencies, MCP, hooks, config. | 2026-03-08 | Deferred from POST_MVP. brain-doctor was working title. |
| 101 | /brain-health deployed as 11th slash command. scripts/brain_health.py (~310 lines). 9/9 diagnostic checks pass. | 2026-03-08 | Last deferred slash command built. 11 total commands. |
| 102 | session-history.md retired. Archived to memory/archive/. End-session protocol no longer appends to it. Brain DB (sys_session_summaries + sys_sessions.notes) replaces it entirely. /brain-recap and /brain-history provide on-demand access. | 2026-03-08 | 330-line manual log duplicated what brain DB stores better. Saves time each end-session. |
| 103 | Bash-to-Python migration uses git branches for full backup. main-backup-pre-migration includes gitignored files. Work on migration/bash-to-python branch. One file at a time: write, test, compare, audit, lock. | 2026-03-09 | Cross-platform support (Linux + Mac + Windows WSL). |
| 104 | Migration Phase F complete. 5 .sh files deleted, 5 .py replacements live. Merged to main (31efb0a). Backup branch on GitHub. Embeddings backfilled to 100% (batch_embed.py). brain_health 9/9 PASS. | 2026-03-09 | First 9/9 clean health check. |
| 110 | Fuzzy correction runs BEFORE FTS query, not after zero results. Typos like "sesion" return low-quality results from the FTS index. Correcting before the query ensures users get real results. | 2026-03-09 | Mike caught critical design flaw during session 16. |
| 111 | Frequency-ratio approach for fuzzy correction. Term not in vocab → auto-correct. Term rare (doc<100) + close match 20x+ freq → correct. Established (doc>=100) → never correct. | 2026-03-09 | Prevents false corrections between real word variants (tests/test, chapters/chapter). |
| 112 | FTS5 vocab table (transcripts_fts_vocab) added to schema. Virtual table over FTS5 index for fuzzy matching dictionary. Added to brain-setup.py DDL. | 2026-03-09 | Created via fts5vocab(transcripts_fts, row). Provides term + doc count. |
| 113 | Transcript cleanup tool (clean_transcripts.py) fixes typos at the source. Recurring maintenance. Auto-detects via dictionary + ED=1 + frequency. Modifies transcripts.content directly — FTS5 trigger rebuilds index. | 2026-03-09 | Mike's idea: fix the data, don't work around it. 6-layer filtering. First run: 367 fixes across 349 rows. |

---

## OPEN ITEMS (from plan Section 13)

| # | Item | Status | Notes |
|---|------|--------|-------|
| O.1 | memory/ folders in Windows JSONL archive — what's in them? | Resolved | 5 folders, all empty. Placeholder dirs from Claude Code auto-memory on Windows, never populated. |
| O.2 | Hook stdin/stdout protocol — verify JSON format | Resolved | Verified in Phase 4. stdin: `cat` or `$(cat)`. stdout: valid JSON only. All other output to stderr/dev/null. |
| O.3 | generate_summary.py — verify Claude Haiku callable from hook | Resolved | Decision 81: claude -p hangs inside sessions. Pure Python fallback used. |
| O.4 | OpenRouter — verify works in Claude Code on Fedora | Resolved | Works but unsupported. Decision: migrate to Amazon Bedrock (session 21). |

---

## PHASE 8: Architecture Merge — Notes/Summaries Unification (Session 20+)

**Full execution plan:** ARCHITECTURE_MERGE_PLAN.md (root)
**Prerequisite for:** Feature 2, Feature 3, pre-public launch

| # | Step | Status | Date | Notes |
|---|------|--------|------|-------|
| 8.0 | Safety net: commit session 19 fixes, tag, backup config, create branch | [-] | 2026-03-11 | SKIPPED — obsolete. Phase 8 steps done incrementally on main across sessions 22-28. |
| 8.1 | Schema migration: add 4 columns to project_registry | [x] | 2026-03-11 | summary, summary_updated_at, status TEXT DEFAULT 'active', health TEXT DEFAULT 'green'. Live DB altered + brain-setup.py DDL updated. |
| 8.2 | Delete generate_summary.py, remove OpenRouter config | [x] | 2026-03-10 | Done in session 22 (bug fix). generate_summary.py git rm'd, summary_llm removed from config.yaml + config.yaml.example + brain-setup.py. |
| 8.3 | Update session-end.py (remove summary generation call) | [x] | 2026-03-10 | Done in session 22 (bug fix). session-end.py rewritten — brain_sync.py detached only, no summary call. |
| 8.4 | Update session-start.py (gap detection, project summary injection) | [x] | 2026-03-11 | Gap detection (missing notes warning) + project summary from project_registry.summary. Both inject into additionalContext. |
| 8.5 | Update 7 consumer scripts | [x] | 2026-03-10 | Done in session 23. All scripts migrated to sys_sessions.notes. |
| 8.6 | Update brain-setup.py (remove summaries DDL, add new columns) | [x] | 2026-03-10 | Done in session 23. |
| 8.7 | Test full suite, DROP TABLE sys_session_summaries, test again | [x] | 2026-03-11 | Done in session 25. Table dropped, brain_health 9/9 PASS. |
| 8.8 | Populate project summaries for active projects | [x] | 2026-03-12 | All 7 projects regenerated from new session notes in session 35. mb, jg, gen, js (full summaries), jga, lt, oth (placeholders). |
| 8.9 | Update 6 doc files + end-session protocol | [x] | 2026-03-11 | Done in session 25. 6 files updated. |
| 8.10 | Final test, commit, merge to main, tag | [x] | 2026-03-12 | 15/15 tests pass. Tag: post-architecture-merge (619e62a). Session 36. |
| 8.11 | Rewrite 111 old notes with Opus 4.6 | [x] | 2026-03-12 | 113/113 COMPLETE. Sessions 1-10 in s29, 11-15 in s31, 16-75 in s32, 76-95 in s34, 96-113 in s35. All project summaries refreshed in s35. |

---

## BUG TRACKER (Sessions 22-27)

| Bug | Description | Status | Session | Notes |
|-----|------------|--------|---------|-------|
| B1 | sys_session_summaries refs after table drop | FIXED | 25 | All scripts migrated to sys_sessions.notes |
| B2 | 6 doc files had stale refs | FIXED | 25 | ARCHITECTURE.md, SESSION_PROTOCOLS.md, etc. |
| B3 | (reserved) | — | — | — |
| B4 | Variable naming summary→notes | FIXED | 25 | Renamed in 7 scripts |
| B5 | Hook JSON format wrong | FIXED | 26 | Must use hookSpecificOutput wrapper. Commit c5a0e78 |
| B6 | user-prompt-submit reads wrong input field | FIXED | 28 | Reads `user_prompt` (string) now. Commit c10773b. 4 doc files updated. |
| B7 | Debug logs stopped after March 7 | FIXED | 28 | Mike added `--debug` to ~/bin/cc. Changelog confirms 2.1.71 made debug opt-in. Validate logs next session. |
| B8 | "1 MCP server failed" on /exit | WONTFIX | 34 | Upstream CC bug. See B9. |
| B9 | "1 MCP server failed" — brain-server SIGINT at /exit | WONTFIX | 34 | **Upstream Claude Code bug.** Affects ALL MCP servers (Python, Node, Rust) including Anthropic's own reference server. CC sends SIGINT, waits only 100ms, escalates to SIGTERM, counts as "failed". GitHub issues #5506, #1935, #7718, #18127 — all auto-closed by bot. Cannot be fixed server-side. Solution: remove MCP server entirely (see FUTURE WORK below). |

---

## PHASE 9: Pre-Public Launch Checklist

**Goal:** Everything needed before switching repo from PRIVATE to PUBLIC.
**Depends on:** Phase 8 complete + Features 2 & 3 complete.

### Code Quality & Review
| # | Step | Status | Notes |
|---|------|--------|-------|
| 9.1 | Deep code review — all scripts, hooks, MCP server | [x] | Session 36: 27 files, 8 checks. Zero stale refs, zero SQL injection, zero bare excepts, zero TODOs. 12 potentially dead imports (harmless). 2 username refs in utility scripts (known). |
| 9.2 | Fix #3: Z suffix timestamps (open from session 19) | [x] | Session 36: verified — all DB writes use timezone.utc, all loggers use time.gmtime, display dates use local time (correct). Already fixed in sessions 22-28. |
| 9.3 | Run brain_health.py — must be 9/9 PASS | [x] | Session 36: 9/9 PASS. |
| 9.4 | Run clean_transcripts.py — clean up any new typos | [x] | Session 36: 60 typos fixed (121 occurrences across 106 rows). 5 false positives added to exclusion list (cpython, popen, printf, sprintf, assed). |
| 9.5 | Security audit — scan all files for personal data, API keys, paths | [x] | Session 36: personal paths removed from ARCHITECTURE.md, git history scrubbed via filter-repo (Gmail app password + OpenRouter API key removed). |

### Documentation
| # | Step | Status | Notes |
|---|------|--------|-------|
| 9.6 | README.md — complete rewrite for public audience | [x] | Session 36: reviewed — all counts accurate (4 hooks, 11 tools, 11 commands), email section with 3 templates + 10 use cases, no stale refs. No rewrite needed — updated incrementally during Feature 3. |
| 9.7 | CLAUDE_BRAIN_HOW_TO.md — review for completeness | [x] | Session 36: reviewed — 12 sections + quick ref card. Fixed 2 stale items in limitations (fuzzy search DONE, fact extraction DEFERRED). Email section 8.5 with dark mode. Zero dead script refs. |
| 9.8 | config.yaml.example — verify all options documented | [x] | Session 36: all sections present, email section with dark_mode field. |
| 9.9 | CHANGELOG.md — create or update with all features | [x] | Session 36: v0.2.0 added (P.1) — Feature 3, Feature 1, Phase 8, infrastructure. |
| 9.10 | LICENSE — verify MIT, no personal info beyond what's intended | [x] | Session 36: MIT, "claude-brain contributors" (Decision 95). Clean. |

### Documentation Cleanup (Session 40 -- items never tracked until now)
| # | Step | Status | Notes |
|---|------|--------|-------|
| 9.27 | FOLDER_SCHEMA.md full rewrite -- massively out of date | [x] | Session 41: Complete rewrite. All 10 substeps verified. 24 scripts, 11 MCP tools, archive/ folder, no ChromaDB/sys_session_summaries refs. |
| 9.28 | CROSS_REFERENCES.md -- remove NEXT_SESSION_START_PROMPT.txt refs | [x] | Session 40: 3 entries removed (lines 28, 43, 105). impact_check confirms 0 refs in CROSS_REFERENCES.md. |
| 9.29 | SESSION_PROTOCOLS.md -- end-session step 4 still references old file | [x] | Session 41: Fixed line 65, added "ask user" + NEXT_SESSION.md steps + checklist row to match CLAUDE.md protocol. |
| 9.30 | HOW_TO Section 10 rewrite -- multi-project workflow | [ ] | See substeps below. |
| 9.31 | "cc" to "claude" sweep across all docs | [ ] | See substeps below. |
| 9.32 | README -- add multi-project mention + web search MCP recommendation | [ ] | See substeps below. |
| 9.33 | Test add-project.py live | [ ] | See substeps below. |
| 9.34 | GitHub contributor still shows "claude" -- investigate and fix | [x] | Session 41: Root cause = 3 old remote branches + 4 tags never force-pushed after filter-repo. pre-feature-3-backup had 1 Co-Authored-By commit. Deleted all 7 remote refs. Only main remains. Cache rebuilding (up to 24h). |

#### 9.27 Substeps: FOLDER_SCHEMA.md rewrite
- [ ] Add `archive/` folder (contains moved NEXT_SESSION_START_PROMPT.txt)
- [ ] Add 8 missing scripts: add-project.py, impact_check.py, write_session_notes.py, write_project_summary.py, clean_transcripts.py, batch_embed.py, brain_health.py, build_competitive_analysis_docx.py
- [ ] Add 8+ missing docs: CROSS_REFERENCES.md, SESSION_PROTOCOLS.md, ARCHITECTURE.md, CHANGELOG.md, README.md, FEATURE_PLAN.md, LICENSE, NEXT_SESSION.md
- [ ] Remove NEXT_SESSION_START_PROMPT.txt from root tree (moved to archive/)
- [ ] Remove all ChromaDB references (local section, hook chain, MCP component) -- removed in Decision 89
- [ ] Remove sys_session_summaries references (DROPPED session 25)
- [ ] Update script count (was 16, now 23+)
- [ ] Update MCP server description (11 tools not 10)
- [ ] Update file counts table
- [ ] Update "Last Updated" date

#### 9.30 Substeps: HOW_TO Section 10 rewrite
- [ ] Explain how to USE brain from other project folders (cd there, type claude)
- [ ] Explain add-project.py for adding a single project without full re-setup
- [ ] Explain what CLAUDE.md does in each project folder
- [ ] Explain session protocols (start/end) and why they matter
- [ ] Explain NEXT_SESSION.md system (auto-injected, zero user friction)

#### 9.31 Substeps: "cc" to "claude" sweep
- [ ] Grep all user-facing docs for "cc" used as command name
- [ ] Update HOW_TO (main target)
- [ ] Update README (main target)
- [ ] Leave cc-updated.sh as-is (Mike's personal script)
- [ ] Leave ~/bin/cc refs in MEMORY.md (Mike-specific)

#### 9.32 Substeps: README update
- [ ] Add mention of multi-project support
- [ ] Recommend web search MCP (bring-your-own, Exa as example)
- [ ] Reference add-project.py for adding projects after initial setup

#### 9.33 Substeps: Test add-project.py live
- [ ] Run script against a real new project folder
- [ ] Verify: creates CLAUDE.md with correct template (including updated checklist)
- [ ] Verify: updates config.yaml with new project
- [ ] Verify: registers project in DB (project_registry)
- [ ] Verify: registers brain-server MCP for new project path
- [ ] Verify: detects other MCPs (like Exa) and offers to register

### Pre-Public Verification
| # | Step | Status | Notes |
|---|------|--------|-------|
| 9.11 | Verify all external URLs in docs (README, HOW_TO, etc.) | [x] | Session 38: 8 URLs audited, 3 fixed (Chrome extension ID, Anthropic docs redirect, GitHub Discussions enabled). Zero broken links. |
| 9.12 | Fresh clone simulation — walk through HOW_TO as a new user | [ ] | Simulate new user experience: clone, setup, first session, verify brain populates. BLOCKED on 9.27-9.33 (docs must be clean first). |

### Beta Testing
| # | Step | Status | Notes |
|---|------|--------|-------|
| 9.13 | Friend (Mac) clones repo, runs brain-setup.py | [ ] | Phase 7.8 — the original beta test step. |
| 9.14 | Friend runs through HOW_TO from scratch | [ ] | Fresh eyes. What's confusing? What breaks? |
| 9.15 | Fix all issues found in beta test | [ ] | |

### Marketing & Launch Strategy
| # | Step | Status | Notes |
|---|------|--------|-------|
| 9.16 | Identity decision: use real name (Mike Dolan) or handle? | [x] | Session 38: real name. LICENSE updated to "Mike Dolan", README creator line added. Decision 95 superseded. |
| 9.17 | Social media setup: determine which platforms needed | [ ] | Twitter/X? Reddit? LinkedIn? What's the Claude community on? |
| 9.18 | Research: find ALL YouTube videos about Claude Code + memory | [ ] | Contact creators, offer early access / demo. |
| 9.19 | Research: find ALL relevant communities (Reddit, Discord, forums) | [ ] | r/ClaudeAI, Anthropic Discord, Claude Code GitHub Discussions, etc. |
| 9.20 | Research: how to approach Hacker News | [ ] | HN launch strategy: timing, title, Show HN format, comment engagement. |
| 9.21 | Research: how to contact Boris (Claude Code creator) | [ ] | Direct outreach — GitHub, Twitter, Anthropic channels. |
| 9.22 | Prepare launch post / announcement text | [ ] | Short, clear, focused on the problem it solves. No hype. |
| 9.23 | Create demo video or GIF showing brain in action | [ ] | Visual proof. Shows setup → session → memory in action. |
| 9.24 | Switch repo from PRIVATE to PUBLIC | [ ] | THE moment. Only after everything above is done. |
| 9.25 | Post to communities (HN, Reddit, YouTube creators, Boris) | [ ] | Coordinated — don't spray everywhere at once. |
| 9.26 | Monitor issues/discussions for first 48 hours | [ ] | First impressions matter. Respond fast. |

---

## UPDATE LOG

| Date | What Changed |
|------|-------------|
| 2026-03-03 | Created tracker. Phase 1 complete. Starting Phase 0 governance. |
| 2026-03-03 | Added FOLDER_SCHEMA.md (living folder map). Replaces old snapshot. |
| 2026-03-03 | Added TEST_SPECIFICATIONS.md. 100 tests across 11 components. |
| 2026-03-03 | Added SCRIPT_CONTRACTS.md. All interfaces defined. ChromaDB Python 3.14 blocker discovered. |
| 2026-03-03 | Added DEPENDENCIES.md. Full machine audit. sqlite3 CLI + gh CLI flagged as missing. Phase 0 complete. |
| 2026-03-03 | Created .gitignore. Added BUILD-PHASE DECISIONS section (decisions 77-80). Governance review complete. |
| 2026-03-03 | Moved MVP Plan v4 from mike-brain/ to root. Fixed all references. |
| 2026-03-03 | Renamed plan to CLAUDE_BRAIN_MVP_PLAN.txt (version inside file, not filename). |
| 2026-03-03 | Archived BUILD_SESSION_BRIEFING.txt and START_PROMPT.txt — replaced by PROJECT_TRACKER.md + --continue. |
| 2026-03-06 | Step 2.1 complete: ingest_jsonl.py built + tested (57/57). 10 fixture files created. Validated against real production JSONL. |
| 2026-03-06 | Step 2.2 complete: Full ingest of 92 real files. 5062 records (5039 transcripts + 23 tool_results), 41 sessions, 0 errors. Projects: jg=2946, mb=1008, js=981, gen=101, oth=3. |
| 2026-03-06 | Step 2.3 complete: startup_check.py built + tested (25/25). Inline backup with rotation + integrity. Imports ingest_jsonl as module. |
| 2026-03-06 | Step 2.4 complete: write_exchange.py built + tested (31/31). Session upsert, dedup, ChromaDB embedding gated behind try/except. |
| 2026-03-06 | Step 2.5 complete: generate_summary.py built + tested (22/22). Pure Python, no LLM. Decision 81: claude -p blocked inside sessions. Phase 2 COMPLETE. |
| 2026-03-06 | Phase 3 COMPLETE: import_claude_ai.py (24/24), brain_sync.sh (15/16), status.py (17/17), copy_chat_file.py (14/14). All 4 support scripts built + tested. |
| 2026-03-07 | Phase 4 COMPLETE: All 4 hooks built (session-start.sh, user-prompt-submit.sh, stop.sh, session-end.sh). Registered in ~/.claude/settings.json. Full ingest: 94 files, 43 sessions, 5583 transcripts. Config mapping fix + oth→mb retag. O.2 resolved. |
| 2026-03-07 | Phase 5 COMPLETE: MCP server built (348 lines, 10 tools). Registered for jg + mb projects. All functions tested (9/10 — semantic deferred). 6 project CLAUDE.md files deployed. Integration test passed. Fat Tony lookup fix. mike-brain/ resolved (Decision 83). |
| 2026-03-07 | Step 6.1 complete: brain_facts (98 rows, 8 categories), brain_preferences (38 rows, 4 categories), JG project facts (47 rows, 4 categories). Source: MIKES_BRAIN_QUESTIONNAIRE.txt. Decisions 82-83 added. |
| 2026-03-07 | Steps 6.2-6.7 + 7.1-7.2 complete. import_claude_ai.py bug fix (Decision 84). 8 claude.ai imports (615 msgs). Decisions table (34 rows), facts table (84 rows). Phase 7 rewritten (9 steps, Decision 85). HOW_TO.md created. Live brain test: 4 bugs found+fixed (Decisions 86-88). MCP search rewrite, hook project bias, CLAUDE.md routing tables. 44/52 steps done. |
| 2026-03-07 | Step 7.3 complete (cross-project MCP test 7/7). Decisions 89-92: ChromaDB replaced with SQLite+numpy (Decision 89), brain-setup.py design locked (Decisions 90-92). transcript_embeddings table created. Migration plan ready for execution. 45/52 steps done. |
| 2026-03-07 | Decision 89 executed: ChromaDB fully replaced with SQLite+numpy in write_exchange.py, server.py, user-prompt-submit.sh, status.py, config.yaml, config_minimal.yaml. Zero ChromaDB references in code. 2,377 transcripts batch-embedded. Semantic search verified. Step 5.4 resolved (was deferred). 46/52 steps done. |
| 2026-03-07 | Step 7.4 in progress: brain-setup.py built (~1432 lines). 4 slash commands created (brain- prefix). Decision 93: /import → /brain-import to avoid built-in skill conflict. .gitignore updated (Decision 91). Needs testing before marking complete. |
| 2026-03-08 | Step 7.4 COMPLETE: /brain-import tested (2 Mom files, 23 msgs into gen), /brain-status tested (bug fixed: semantic search after conn.close). brain_query.py built (~280 lines) for /brain-question. Decision 94: local script replaces subagent (30K→3K tokens). status.py bug fixed. 5 slash commands total. 47/52 steps done. |
| 2026-03-07 | Steps 7.5+7.6 COMPLETE. README.md created (15 sections). Security audit: 27+ files cleaned, .gitignore expanded (+30 rules), all fixtures sanitized, final scan clean (32 files, 0 personal data). Step 7.7 partially done: commit f6e9c7d (33 files, 8184 lines), push blocked — gh auth login fails (browser activates but CLI never saves token). Decision 95. 49/52 steps done. |
| 2026-03-08 | Step 7.7 COMPLETE. gh auth fixed via PAT method (Decision 98). Repo created PRIVATE (Decision 96). Co-Authored-By removed from all commits (Decision 97). 3 commits pushed. exports/ added to .gitignore. README + HOW_TO updated with exact AI Chat Exporter settings. 50/52 steps done. |
| 2026-03-08 | Step 7.9 COMPLETE. POST_MVP_ROADMAP.md rewritten: 12 known limitations across 4 categories (platform, search, data capture, feature gaps), stale entries fixed (brain-doctor→DONE, LLM summaries→RESOLVED, MEMORY.md trimming→DONE), decision log extended (99, 100, 102). README.md + HOW_TO.md updated with limitations. FOLDER_SCHEMA.md + DEPENDENCIES.md stale refs fixed. 51/52 steps done. |
| 2026-03-08 | Bug fixes: write_session_notes.py prefix matching for truncated IDs. startup_check.py auto-repairs missing summaries on startup. import_claude_ai.py generates LLM summaries inline during import. 2 missing summaries regenerated. |
| 2026-03-09 | Bash-to-Python migration COMPLETE (sessions 11-15). Phases A-F across 5 sessions. 5 .sh files → 5 .py replacements. 9 docs updated. All hooks live on Python. Merged to main (31efb0a). Backup branch on GitHub. Embeddings backfilled to 100% (batch_embed.py). brain_health: first 9/9 PASS. Decisions 103-104. |
| 2026-03-11 | Session 27: B6/B7/B8 diagnosed. B6: hook reads wrong input field (prompts vs user_prompt) — hook NEVER WORKED live. B7: debug logs stopped (2.1.70→2.1.71 auto-update, needs --debug flag). B8: MCP partially diagnosed, needs B7 first. No code changes — diagnosis only. Bug tracker section added. |
| 2026-03-11 | Session 28: B6 FIXED (c10773b). B7 FIXED by Mike (--debug added to cc). B8 likely resolved (only brain-server running). Both B7/B8 need debug log validation next session. |
