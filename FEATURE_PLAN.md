# FEATURE PLAN - Three Pre-Launch Features

**Created:** 2026-03-09
**Branch backup:** `pre-feature-3-backup` (commit 88a5c6c)
**Status:** Feature 1 COMPLETE. Feature 2 DEFERRED. Feature 3 COMPLETE. Features 4-6 COMPLETE (Session 41: ChatGPT import, Tags/Topics, Gemini import).

---

## OVERVIEW

| # | Feature | Files Created | Files Modified | Dependencies |
|---|---------|--------------|----------------|--------------|
| 1 | Fuzzy Search | 1 (fuzzy_search.py) | 3 (server.py, brain_search.py, brain_query.py) + brain-setup.py | none (difflib is stdlib) |
| 2 | Auto Fact Extraction | 1 script | 1-2 | Phase 8 complete (architecture merge removes old LLM infra) |
| 3 | Email Digests | 1 script | 2 | none (smtplib is stdlib) |

**Build order:** 1 → Phase 8 (architecture merge) → 2 → 3
- Feature 1 (Fuzzy Search): COMPLETE (session 17)
- Phase 8 (Architecture Merge): COMPLETE (session 36, tag: post-architecture-merge)
- Feature 2 (Auto Fact Extraction): DEFERRED (session 35, value thin after session note rewrites)
- Feature 3 (Email Digests): IN PROGRESS - revised plan below (8 steps, 24 sub-steps)

---

## FEATURE 1: FUZZY SEARCH

**Goal:** Correct typos BEFORE the FTS query runs. Show "did you mean?" note when corrections are applied. No performance impact on correct-spelling searches.

**Design change (session 16):** Originally planned as zero-result fallback. Mike caught that typos like "sesion" return low-quality results (7 typo matches) instead of correcting to "session" (1700+ real matches). Redesigned: fuzzy correction runs BEFORE the FTS query, not after.

### Correction Rules (frequency-ratio approach)
| Scenario | Rule | Example |
|---|---|---|
| Term not in FTS index (doc=0) | Correct to first close match with doc >= 10 | "databse" → "database" |
| Term in index, rare (doc < 100) | Correct only if close match has 20x+ higher freq | "sesion" (10) → "session" (1700) |
| Term in index, established (doc >= 100) | Never corrected | "tests" (84), "chapter" (643) |

### Known Limitation - Accumulated Typos (RESOLVED)
Typos that appear in enough transcripts (doc >= 5) AND whose correct spelling has < 20x frequency won't auto-correct. Example: "deploment" (doc=4) vs "deployment" (doc=19) = 4.75x < 20x. **Resolved:** `clean_transcripts.py` fixes misspellings directly in the transcripts table. FTS5 UPDATE trigger rebuilds the index automatically. First run: 367 occurrences fixed across 349 rows.

### Steps

- [x] **1.1 - Read existing search code**
  Read `mcp/server.py` search_transcripts() and search scripts. Found THREE files need fuzzy:
  - `mcp/server.py` - MCP tool, `search_transcripts()` line 216
  - `scripts/brain_search.py` - `/brain-search` slash command, `search_fts()` line 121
  - `scripts/brain_query.py` - `/brain-question` slash command, `search_fts()` line 120
  All three have separate `build_fts_query` implementations and separate zero-result handling.
  STOP_WORDS are duplicated across all three files (slightly different sets).
  Decision: create a shared fuzzy module (`scripts/fuzzy_search.py`) to avoid tripling the code.

- [x] **1.2 - Build vocabulary extraction function**
  Created `scripts/fuzzy_search.py` with:
  - `get_vocabulary(db_path)` - extracts 9,052 terms from FTS5 vocab table (3+ chars, alpha-only, no stop words, doc >= 2)
  - `get_frequencies(db_path)` - doc frequency per term for ratio calculations
  - `_ensure_vocab_table()` - creates `transcripts_fts_vocab` (FTS5 vocab virtual table) on first call
  - Module-level cache - builds once per process, reused on subsequent calls
  - Also added `DDL_FTS_VOCAB` to `brain-setup.py` so new installations get the vocab table at setup time

- [x] **1.3 - Build fuzzy match function**
  `fuzzy_correct(terms, db_path)` in `scripts/fuzzy_search.py`:
  - Uses `difflib.get_close_matches()` with cutoff 0.6, up to 5 candidates per term
  - Frequency-ratio approach: compares doc counts to distinguish typos from real words
  - Returns `(corrected_terms, corrections_map)` - corrections map is `{original: corrected}`
  - STOP_WORDS superset from all 5 search files consolidated in this module
  - Performance: 48ms cold cache, 28ms warm

- [x] **1.4 - Integrate into MCP server search_transcripts()**
  Modified `mcp/server.py`:
  - Added `import re`, `import sys`, `from scripts.fuzzy_search import fuzzy_correct`
  - Refactored `_build_fts_query` into `_is_fts5_syntax`, `_extract_keywords`, `_keywords_to_fts`
  - Extracted `_run_fts_query` and `_format_results` helper functions
  - Fuzzy runs BEFORE FTS: extract keywords → fuzzy_correct → build FTS query → run
  - FTS5 syntax queries bypass fuzzy entirely (passthrough)
  - If corrections made, prepends `**Did you mean:** 'sesion' → 'session'` header

- [x] **1.5 - Integrate into scripts/brain_search.py AND scripts/brain_query.py**
  Both scripts updated:
  - `brain_search.py` - imports `fuzzy_correct`, corrects keywords before `search_fts()`, prints "Did you mean:" line
  - `brain_query.py` - imports `fuzzy_correct`, corrects keywords before all searches, adds corrections to `format_results()` output
  - Both use corrected keywords for ALL search types (FTS, semantic, decisions, facts)

- [x] **1.6a - Transcript cleanup tool (clean_transcripts.py)**
  Created `scripts/clean_transcripts.py` - recurring maintenance tool that auto-detects and fixes misspellings in transcript content.
  - 6-layer typo detection: (1) dictionary check on term, (2) tech exclusion list, (3) ED=1 only, (4) similarity cutoff 0.85, (5) morphological variant filter, (6) dictionary check on correction target
  - FTS5 UPDATE trigger rebuilds index automatically - no manual rebuild needed
  - First run: 367 occurrences fixed across 349 rows (including "deploment"→"deployment", "sesion"→"session")
  - Imports `STOP_WORDS` and `clear_cache` from `fuzzy_search.py`

- [x] **1.6 - Test fuzzy search**
  All 8 tests PASS:
  1. Known typos: "sesion", "databse", "configration", "embeding" → corrected with "did you mean?" note
  2. Correct spelling: "session", "database", "project" → no correction, normal results
  3. Gibberish: "xyzqqq" → no correction, returns whatever FTS finds (or empty)
  4. Multi-word: "sesion summary" → corrects "sesion", keeps "summary"
  5. FTS5 syntax: `"session" OR "chapter"` → passthrough, no fuzzy
  6. Similar real words: "tests", "chapters", "version" → NOT corrected (established words)
  7. MCP server.py integration: "Did you mean" header, FTS5 passthrough, correct spelling clean
  8. brain_search.py and brain_query.py: "Did you mean" output working
  Performance: 48ms cold, 28ms warm - no degradation on correct-spelling queries.

- [x] **1.7 - Audit and commit**
  Re-read all 6 modified files cover to cover. No issues found. All imports correct, parameterized SQL throughout, no dead code. Committed.

---

## FEATURE 2: AUTO FACT EXTRACTION

**Goal:** Script that scans conversations, sends them to an LLM, and writes structured facts to the database automatically.
**Prerequisite:** Phase 8 (Architecture Merge) must be complete. generate_summary.py and OpenRouter summary infra deleted (session 22). Consumer scripts migrated to sys_sessions.notes (session 23). sys_session_summaries table dropped (session 25). Remaining Phase 8 steps: schema migration (F2), gap detection (F3), project summaries (F4). Feature 2 will use a clean LLM call approach (direct Anthropic API or similar).

### Steps

- [ ] **2.1 - Design LLM call approach (post-Phase 8)**
  generate_summary.py and OpenRouter config already removed (session 22). Design the new LLM call mechanism for fact extraction. Options: direct Anthropic API, or Claude Code subprocess. Read the `facts` table schema.

- [ ] **2.2 - Design the extraction prompt**
  Write the LLM prompt that takes a session transcript and returns structured facts as JSON.
  - Output format: `[{"project": "app", "category": "technology", "key": "frontend", "value": "React 19 with TypeScript"}]`
  - Categories: technology, architecture, feature, endpoint, decision, preference, pattern, status
  - Prompt must instruct: extract only concrete facts, not opinions or speculation
  - Prompt must handle multi-project sessions (extract facts for each project mentioned)

- [ ] **2.3 - Build scripts/extract_facts.py**
  Create the script:
  - Read config.yaml for API key and DB path
  - Query sessions that haven't been processed yet (tracking table or marker)
  - For each unprocessed session: fetch transcript, send to LLM, parse JSON response
  - Deduplicate against existing facts (same project+category+key = skip or update)
  - Insert new facts into the `facts` table
  - Mark session as processed
  - Progress reporting: "Processing session 5/20... extracted 3 new facts"

- [ ] **2.4 - Add extraction tracking**
  Decide tracking approach:
  - Option A: New column `facts_extracted` in `sys_sessions` (simple, no new table)
  - Option B: New table `fact_extraction_log` (more flexible, tracks per-fact source)
  - Pick one, implement it. Must be idempotent - re-running skips already-processed sessions.

- [ ] **2.5 - Test auto extraction**
  - Run on 3-5 recent sessions manually
  - Verify extracted facts are accurate and well-categorized
  - Verify dedup works (run again on same sessions, no duplicates)
  - Verify facts show up in `lookup_fact()` MCP queries
  - Test with a session that has no extractable facts (should handle gracefully)
  - Test with no API key configured (should fail with clear error message)

- [ ] **2.6 - Add slash command or hook integration (optional)**
  Decide: should extraction run automatically at session-end? Or manual-only?
  - Manual: user runs `/brain-extract` or `python3 scripts/extract_facts.py`
  - Automatic: session-end hook calls extract_facts after generating summary
  - Recommendation: start manual, add automatic later if it works well

- [ ] **2.7 - Audit and commit**
  Review all changes. Check for API key security (not logged, not exposed). Commit.

---

## FEATURE 3: EMAIL DIGESTS (Revised 2026-03-12, Session 36)

**Goal:** Premade email templates that show the brain reaching OUT to the user - weekly digests, daily standups, project deep dives. This is a competitive differentiator: no other AI memory tool does proactive outreach. Key selling point for open source launch.

**Strategic context (from BRAIN_BRAINSTORMING_IDEAS.md, session 9):**
- "Proactive outreach" is 1 of 6 things we have that nobody else does
- Email was positioned as a force multiplier and competitive differentiator
- Monday Morning Briefing (#1) and Dormant Project Alerts (#2) both APPROVED in session 9
- Mike's inception-to-date idea: "so someone can see all the work they did" - the forwardable email

**What already exists (built in session 9, updated through session 28):**
- `scripts/brain_digest.py` (580 lines) - weekly digest with 12 query functions
- Sections: inception-to-date portfolio, this-week stats with trends, session highlights, decisions, dormant alerts, roadmap, brain stats, last session notes
- Gmail SMTP delivery working, `--dry-run`, `--test`, `--days` flags
- Cron: Monday 8am weekly digest
- Email config in config.yaml (gitignored)

**What's missing (the actual work):**
- Only 1 email type (weekly). Need 2-3 premade templates with `--daily` and `--project` flags.
- No use case ideas in docs for open source users
- config.yaml.example may not have email section
- brain-setup.py may not have email config step
- README/HOW_TO don't fully cover email setup

### EMAIL DESIGN SPEC (session 36)

**Full design document:** `email-digest-design-spec.md` (root) - 839 lines covering BLUF methodology,
all 3 template structures, HTML email constraints, subject line formulas, engagement psychology,
10 use case ideas, and data contract payloads. Created by Chrome Claude from web research.

**Key principles (summary - see full spec for details):**
1. **BLUF - Bottom Line Up Front.** Most important thing is the FIRST thing. Not buried.
2. **Actionable, not informational.** Every email answers: "What should I DO next?"
3. **Subject line IS the BLUF** - must convey core status without opening the email. Always include a variable.
4. **One screen pane** for daily. 1.5-2 scrolls for weekly. 2-3 for deep dive.
5. **RAG uses inline background-color on `<td>`, NOT emoji** - emoji rendering unreliable across clients.
6. **Conditional sections** - blockers only appear when they exist. Absence is also information.
7. **Postmark frequency rule** - daily = minimal chrome, weekly = moderate, deep dive = full report.
8. **150-250 words daily, 300-500 weekly, 500-800 deep dive.**
9. **Send daily 8-9 AM, weekly Monday AM.**
10. **Quiet day handling** - always send (preserve habit loop), but adapt content.

### DATA → EMAIL MAPPING (what we have and where each piece goes)

**project_registry fields:**
| Field | What it contains | Used in Daily | Used in Weekly | Used in Deep Dive |
|---|---|---|---|---|
| `health` | green/yellow/red | RAG badge per project ✓ | Portfolio table RAG column (NOT DONE) | RAG header (NOT BUILT) |
| `status` | active/paused | Filter: skip paused | Filter: show paused separately (NOT DONE) | Show in header (NOT BUILT) |
| `summary` | Rich text, 300-7000 chars | Extracts: Next Steps, Blockers, In Progress ✓ | NOT USED AT ALL - should power exec summary + portfolio context | Full summary shown (NOT BUILT) |
| `summary_updated_at` | Last update timestamp | Not needed | Freshness indicator (NOT DONE) | Show last update (NOT BUILT) |
| `label` | Human-readable project name | ✓ | ✓ | ✓ |

**project_registry.summary sections (available for extraction):**
| Section | Available in mb/jg | Used in Daily | Used in Weekly | Used in Deep Dive |
|---|---|---|---|---|
| `## Summary` | ✓ | Not needed (too long) | Portfolio table hover/excerpt (NOT DONE) | Full display (NOT BUILT) |
| `## Accomplishments` | ✓ | Not needed | Top Accomplishments section (NOT DONE) | Full display (NOT BUILT) |
| `## In Progress` | ✓ | ✓ | Portfolio table context (NOT DONE) | Full display (NOT BUILT) |
| `## Risks & Blockers` | ✓ | ✓ (as Blockers) | Feeds dormant alerts + risk summary (NOT DONE) | Structured table (NOT BUILT) |
| `## Next Steps` | ✓ | ✓ (as Pick Up Here) | Upcoming section (NOT DONE) | Full display (NOT BUILT) |
| `## Decisions` | ✓ | Not needed | Key decisions listed | Project decisions (NOT BUILT) |
| `## Architecture` | ✓ | Not needed | Not needed | Architecture snapshot (NOT BUILT) |
| `## Recent Sessions` | ✓ | Not needed | Session highlights | Session feed (NOT BUILT) |

**Other DB tables used:**
| Table | Data | Daily | Weekly | Deep Dive |
|---|---|---|---|---|
| `sys_sessions` | Session counts, messages, notes, timestamps | ✓ | ✓ | ✓ |
| `decisions` | Numbered decisions with descriptions | ✓ (if any) | ✓ | ✓ (filtered to project) |
| `facts` | Structured facts per project (roadmap items) | Not needed | Roadmap section ✓ | Relevant facts (NOT BUILT) |
| `brain_facts` | Personal brain facts | Not needed | Not needed | Not needed |
| `transcript_embeddings` | Embedding count | Not needed | Brain stats ✓ | Not needed |

### Steps

#### PHASE A: HTML Foundation (spec sections 5, 6 - do this FIRST, all templates use it)

- [x] **3.A1 - Build safe HTML email skeleton as shared base** (DONE session 36)
  - [x] 3.A1a - Replaced `<style>` in `<head>` with ALL inline style constants (S_H1, S_TD, S_METRIC, etc.)
  - [x] 3.A1b - DOCTYPE, xmlns, xmlns:o, MSO conditional comments
  - [x] 3.A1c - `<meta color-scheme>` + `<meta supported-color-schemes>` for dark mode
  - [x] 3.A1d - Hidden preheader div with dynamic content per template
  - [x] 3.A1e - MSO conditional `<table width="600">` wrapper for Outlook
  - [x] 3.A1f - Table-based outer wrapper (role=presentation) for Outlook
  - [x] 3.A1g - #1a1a1a text color, Arial/Helvetica/sans-serif font stack
  - [x] 3.A1h - `build_email_wrapper(title, preheader, content)` shared function - all 3 templates use it
  - [ ] 3.A1i - Plain-text fallback still generic - defer to Phase F (low priority)
  - [x] 3.A1j - All 3 templates tested: daily (4,825 chars), weekly (33,007 chars), test (2,645 chars)
  - [x] 3.A1k - Zero CSS classes remain, zero `<style>` blocks, 10/10 spec checks pass
  - [x] 3.A1l - Live send to Gmail: daily + weekly both delivered

#### PHASE B: Daily Standup (spec section 2 - already started, needs completion)

- [x] **3.B1 - Complete daily standup per spec** (DONE session 36)
  - [x] 3.B1a - Research: BLUF, military email, Geekbot/Range/Standuply patterns (design spec created)
  - [x] 3.B1b - Per-project blocks with RAG badge from `project_registry.health`, Pick Up Here from `## Next Steps`, Blockers from `## Risks & Blockers`, In Progress from `## In Progress`
  - [x] 3.B1c - Dynamic subject line: `[brain] Daily: {stat} | {date}` per spec section 6
  - [x] 3.B1d - Preheader text in wrapper (stats summary)
  - [x] 3.B1e - Preheader uses first Pick Up Here item: "Pick up: 8.10: final test/tag to close Phase 8"
  - [x] 3.B1f - 7-day rolling average: metrics show ↑/↓/≈ vs daily avg (e.g., "↑ vs 6.7/day avg")
  - [x] 3.B1g - Quiet day: always sends, shows per-project RAG + quiet streak + Next Steps from summary
  - [x] 3.B1h - Word count: 183 words (within 150-250 target)
  - [x] 3.B1i - Live send to Gmail: delivered. Pending beta tester feedback.

#### PHASE C: Weekly Digest Overhaul (spec section 3 - nearly every section needs work)

The weekly is the "forwardable portfolio view" - designed to be sent to a manager/stakeholder.
Currently it's a raw data dump with zero project context. Needs major overhaul.

**New section order for weekly (per spec section 3):**
1. Executive Summary BLUF (NEW - 2-3 sentences answering: activity level? most active? alerts?)
2. Week-over-Week Trend Table (NEW - sessions/msgs/decisions this vs last, with delta %)
3. Project Portfolio Table (OVERHAUL - add RAG from `health`, status from `status`, 1-line from `## Summary`)
4. Top Accomplishments (NEW - 3-5 bullets from session notes "What Was Done" sections)
5. Dormant Alerts (RESTYLE - amber not red, include last session context)
6. Decisions Made (KEEP - already works)
7. Last Session Notes (KEEP - already works)
8. On Deck / Roadmap (KEEP - already works)
9. Brain Stats (KEEP - move to bottom)
10. Footer (UPDATE - add "Forward this report" nudge)

Inception-to-date table MOVES DOWN - it's reference data, not the BLUF. Goes after brain stats.

- [x] **3.C1 - Add Executive Summary BLUF (the "forwardable paragraph")** (DONE session 36)
  - [x] 3.C1a - Query: total sessions, delta vs last week, most active project, dormant count
  - [x] 3.C1b - Formula: "This week you logged {N} sessions across {P} projects ({delta}% from last week). Most active: {project}. {alert}."
  - [x] 3.C1c - Alert logic: dormant → name them. All clear → "All projects on track."
  - [x] 3.C1d - Position as FIRST section (above everything)
  - [x] 3.C1e - Dynamic subject: `[Weekly] Mar 05-Mar 12: 47 sessions across 1 projects`
  - [x] 3.C1f - Preheader: first 100 chars of exec summary

- [x] **3.C2 - Add week-over-week trend comparison table** (DONE session 36)
  - [x] 3.C2a - New queries: `get_previous_week_decisions()`, `get_per_project_previous_stats()`
  - [x] 3.C2b - 4-column table: Metric | This Week | Last Week | Δ% (green/red)
  - [x] 3.C2c - Positioned after exec summary, before portfolio

- [x] **3.C3 - Overhaul portfolio table with project context** (DONE session 36)
  - [x] 3.C3a - RAG column: inline background-color `<td>` from `project_registry.health` (NOT emoji)
  - [x] 3.C3b - Status: PAUSED badge (amber) for paused projects
  - [x] 3.C3c - 1-line context: first sentence of `## Summary` from `project_registry.summary`
  - [x] 3.C3d - Trend arrow per project: ↑/↓ vs last week using `get_per_project_previous_stats()`
  - [x] 3.C3e - Forwardable headers: "", "Project", "Sessions", "Messages", "Trend"
  - [x] 3.C3f - Sorted by sessions desc

- [x] **3.C4 - Add Top Accomplishments section (3-5 bullets)** (DONE session 36)
  - [x] 3.C4a - Extracts from session notes "What Was Done" sections
  - [x] 3.C4b - Top 5, filtered to lines > 20 chars
  - [x] 3.C4c - Positioned after portfolio table

- [x] **3.C5 - Restyle dormant project alerts** (DONE session 36)
  - [x] 3.C5a - Amber background (#FFF3CD) with left border (#F59E0B)
  - [x] 3.C5b - Includes "Next:" from project summary Next Steps section
  - [x] 3.C5c - Trigger changed to 3 days (was 7)

- [x] **3.C6 - Reorder sections** (DONE session 36)
  - [x] 3.C6a - Inception table moved to bottom (was position #1)
  - [x] 3.C6b - Inception table upgraded: added RAG health column, Status column (Active/PAUSED), sorted active-first

- [x] **3.C7 - Add "Forward this report" nudge in footer** (DONE session 36)
  - [x] 3.C7a - "This report is designed to be forwarded to stakeholders."

- [x] **3.C8 - Word count check** (DONE session 36)
  - [x] 3.C8a - Weekly: 1,259 words (over 300-500 target, but justified by rich project data - inception table + accomplishments + session notes + roadmap. Trim if beta tester says too long.)
  - [x] 3.C8b - Daily: 172 words (within 150-250 target)

- [x] **3.C9 - Test weekly overhaul** (DONE session 36)
  - [x] 3.C9a - Dry-run: 11 sections in correct order, RAG badges, exec summary, trend table, forward nudge - all verified
  - [x] 3.C9b - Live send to Gmail: delivered, Mike reviewed, "looks good, will need feedback from beta tester"

#### PHASE D: Project Deep Dive (spec section 4 - new template, richest use of project data)

This is where `project_registry.summary` shines - the full 5-7K character summary gets unpacked
into a structured project status report. This email is the "forward to your manager" format.

**Section order (per spec section 4 + our data model):**
1. Project header + RAG badge → `project_registry.health` + `label`
2. Executive summary → `project_registry.summary` ## Summary section (verbatim, it's already 2-3 sentences)
3. Health metrics (4 KPIs) → `sys_sessions` counts + `decisions` count + derived blockers
4. In Progress → `project_registry.summary` ## In Progress section
5. Recent sessions (5-7) → `sys_sessions` with notes topics
6. Risks & Blockers → `project_registry.summary` ## Risks & Blockers section
7. Next Steps → `project_registry.summary` ## Next Steps section
8. Key Decisions → `decisions` table filtered to this project
9. Architecture → `project_registry.summary` ## Architecture section
10. Footer with notification prefs

- [x] **3.D1 - Build project deep dive template (`--project <prefix>`)** (DONE session 36)
  - [x] 3.D1a - `--project` flag added, mutually exclusive with `--daily`
  - [x] 3.D1b - `get_project_deep_dive_data()`: queries project_registry + sessions + decisions + trends
  - [x] 3.D1c - `build_project_html()` with 9 sections: RAG header, exec summary, health metrics (4 KPIs with trend), In Progress, Recent Sessions (5-7), Risks & Blockers (red styling), Next Steps (blue styling), Key Decisions (last 10), Architecture
  - [x] 3.D1d - Subject: `[mb] Status: ON TRACK - Personal memory system for Claude Code... | Mar 12`
  - [x] 3.D1e - Preheader: first sentence of ## Summary
  - [x] 3.D1f - Tested lt (298 char summary) - renders cleanly with fewer sections (3.6K chars)
  - [x] 3.D1g - Word count: mb=562 (within 500-800 target)
  - [x] 3.D1h - `--project mb --dry-run`: 13/13 checks pass, 7 sections, 12,462 chars
  - [x] 3.D1i - `--project jg --dry-run`: works, 11,244 chars, different data
  - [x] 3.D1j - Live send mb to Gmail: delivered

#### PHASE E: Use Cases, Config, Docs

- [x] **3.E1 - Write email use case ideas for docs (from spec section 8)** (DONE session 36)
  - [x] 3.E1a - 10 use cases written to README.md: Morning Kickoff, Stakeholder Update, Dormant Rescue, Decision Audit, Sprint Retro, Onboarding, Accountability, Personal Changelog, Context Resume, Portfolio View. Plus 3 template summary table.
    1. Context Resume Digest - "here's where you left off" after 48+ hours
    2. Decision Log Weekly - all decisions made that week
    3. Technical Debt Radar - TODOs, repeated workarounds never addressed
    4. Knowledge Gap Alert - "you've asked about {topic} in 5 sessions"
    5. Dependency Drift Report - stale dependencies flagged
    6. Code Review Prep - all sessions related to a branch/PR
    7. Onboarding Digest - project primer from session context
    8. Sprint Retrospective - time distribution, blockers, velocity
    9. Personal Productivity Insights - peak hours, session length, focus areas
    10. Stale Context Cleanup - old memory entries to review/archive

- [x] **3.E2 - Update config.yaml.example** (DONE session 36)
  - [x] 3.E2a - Email section added with enabled, from_address, to_address, gmail_app_password
  - [x] 3.E2b - Gmail App Password setup instructions (5-step guide in comments)
  - [x] 3.E2c - Cron examples for all 3 templates in comments

- [x] **3.E3 - Update brain-setup.py** (DONE session 36)
  - [x] 3.E3a - No email config existed - added Phase 7 "EMAIL DIGESTS (optional)"
  - [x] 3.E3b - Interactive: ask email? → Gmail address → App Password → test SMTP → write to config.yaml → offer daily + weekly cron setup
  - [x] 3.E3c - Phases renumbered 1-9 (was 1-8). Email is phase 7, Registration→8, Health→9.

- [x] **3.E4 - Add cron entries for new templates** (DONE session 36)
  - [x] 3.E4a - brain-setup.py offers to install daily cron: `0 8 * * 1-5 ...--daily`
  - [x] 3.E4b - brain-setup.py offers to install weekly cron: `0 8 * * 1 ...`
  - [x] 3.E4c - brain_digest.py docstring updated with all cron examples

- [x] **3.E5 - Update documentation** (DONE session 36)
  - [x] 3.E5a - README.md: 3-template table + 10 use cases (done in E1)
  - [x] 3.E5b - HOW_TO: new section 8.5 - Gmail setup, test commands, cron, all 3 templates described, subject line examples
  - [x] 3.E5c - Example daily output in HOW_TO showing per-project RAG, Pick Up Here, Blockers, Quiet projects

#### PHASE F: Quality & Ship

- [x] **3.F0 - Dark mode support (optional `--dark` flag)** (DONE session 36)
  - [x] 3.F0a - Light default, dark optional per best practice
  - [x] 3.F0b - `--dark` flag added to argparse
  - [x] 3.F0c - `apply_dark_mode()` function overrides 20+ style globals: dark bg (#1a1a1a/#2d2d2d), light text (#e0e0e0), muted borders (#444), blue accent (#6caceb), dark highlight (#1e3a5f), dark danger (#3d2020)
  - [x] 3.F0d - Called in main() if `--dark` OR `config.email.dark_mode: true`
  - [x] 3.F0e - 8/8 dark checks pass, light mode unaffected, all 3 templates work in both modes
  - [x] 3.F0f - Config option: `email.dark_mode` supported (reads from config.yaml)

- [x] **3.F1 - Cross-cutting spec compliance** (DONE session 36)
  - [x] 3.F1a - Subject lines: Daily 46, Weekly 47, Project 45 chars (all under 50, trimmed from 53/93)
  - [x] 3.F1b - All subjects contain numbers (variable content every day)
  - [x] 3.F1c - "To change frequency: edit crontab -e" added to all 3 footers
  - [x] 3.F1d - Conditional: red only in daily/project when real blockers exist, zero in weekly
  - [x] 3.F1e - Amber only for dormant/paused projects. Red only for real blockers/risks.

- [x] **3.F2 - Email rendering verification** (DONE session 36)
  - [x] 3.F2a - Daily sent to Gmail web - delivered
  - [x] 3.F2b - Weekly sent to Gmail web - delivered
  - [x] 3.F2c - Project deep dive sent to Gmail web - delivered
  - [x] 3.F2d - Plain-text fallback: generic but functional (content-specific deferred to post-build)
  - [x] 3.F2e - Dark mode: no #000000 text (PASS), uses #1a1a1a (PASS), color-scheme meta (PASS) - all 3 templates

- [x] **3.F3 - Final audit and commit** (DONE session 36)
  - [x] 3.F3a - Code integrity: 5 scripts compile, 7 functional tests pass (3 templates + dark + summary + hook + GO-check)
  - [x] 3.F3b - Stale refs: 12 new functions all referenced, 2 old functions zero refs
  - [x] 3.F3c - Docs: added dark mode to HOW_TO section 8.5 + config.yaml.example. README has 3 templates + 10 use cases.
  - [x] 3.F3d - Credentials: zero real credentials in tracked files (all are examples/docs)
  - [x] 3.F3e - brain_health.py: 9/9 PASS
  - [x] 3.F3f - Committed and pushed

---

## POST-BUILD

After all 3 features are built:

- [ ] **P.1 - Update CHANGELOG.md** with all three features
- [ ] **P.2 - Update POST_MVP_ROADMAP.md** - mark fuzzy search, auto-extraction, email as DONE
- [ ] **P.3 - Run full brain_health.py** - verify 9/9 PASS still holds
- [ ] **P.4 - Final README.md and HOW_TO review** - make sure docs match what's built
- [ ] **P.5 - Final commit and push to main**

---

## FUTURE FEATURES (captured, not scheduled)

- **DOCX Report Generation** - use `docxtpl` (Jinja2 template engine for Word) to generate
  professional DOCX project status reports from brain data. Design a template once in
  LibreOffice (fonts, headers, margins, page numbers), then Python injects data.
  Could add `--format docx` flag to brain_digest.py. Install: `pip install docxtpl`.
  Captured session 36.

---

## DECISION LOG

| # | Decision | Rationale |
|---|----------|-----------|
| 105 | Project prefix standardized to 2-3 characters | 2 covers most cases (js, bk, wp); 3 for longer names (gen, app). 4 is too long for something typed frequently. 1 is ambiguous. |
| 106 | Build order: fuzzy → auto-facts → email | Fuzzy is smallest/fastest. Auto-facts enriches DB before email needs it. Email is the capstone. |
| 107 | Fuzzy search uses difflib (stdlib) | Zero new dependencies. get_close_matches() is battle-tested. No reason to add a pip package for this. |
| 108 | Auto fact extraction is manual-first | Run via script, not auto-triggered at session-end. Lets us verify quality before automating. Can add hook integration later. |
| 109 | Email uses smtplib (stdlib) | Zero new dependencies. Works with Gmail, Outlook, any SMTP provider. No need for a third-party email library. |
| 110 | Fuzzy correction runs BEFORE FTS query, not after zero results | Typos like "sesion" return low-quality results from the FTS index (7 typo matches). Correcting before the query ensures users get the real results (1700+ for "session"). Mike caught this. |
| 111 | Frequency-ratio approach for fuzzy correction | Static doc-frequency thresholds break as typos accumulate in the index. Ratio approach: term not in vocab → auto-correct; term rare (doc < 100) but close match has 20x+ freq → correct; established (doc >= 100) → never correct. Prevents false corrections between real word variants (tests/test, chapters/chapter). |
| 112 | FTS5 vocab table (`transcripts_fts_vocab`) added to schema | Virtual table over the FTS5 index. Provides term + doc count for fuzzy matching dictionary. Created via `fts5vocab(transcripts_fts, row)`. Added to brain-setup.py DDL. |
| 113 | Transcript cleanup tool (`clean_transcripts.py`) fixes typos at the source | Recurring maintenance tool. Auto-detects typos via dictionary + ED=1 + frequency ratio. Modifies `transcripts.content` directly - FTS5 UPDATE trigger rebuilds index. 6-layer filtering prevents false positives. Mike's idea: fix the data, don't work around it. |
