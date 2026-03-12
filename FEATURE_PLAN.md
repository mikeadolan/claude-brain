# FEATURE PLAN — Three Pre-Launch Features

**Created:** 2026-03-09
**Branch backup:** `pre-feature-3-backup` (commit 88a5c6c)
**Status:** Feature 1 COMPLETE. Feature 2 BLOCKED by Phase 8 (Architecture Merge). Next: Phase 8.

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
- Feature 3 (Email Digests): IN PROGRESS — revised plan below (8 steps, 24 sub-steps)

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

### Known Limitation — Accumulated Typos (RESOLVED)
Typos that appear in enough transcripts (doc >= 5) AND whose correct spelling has < 20x frequency won't auto-correct. Example: "deploment" (doc=4) vs "deployment" (doc=19) = 4.75x < 20x. **Resolved:** `clean_transcripts.py` fixes misspellings directly in the transcripts table. FTS5 UPDATE trigger rebuilds the index automatically. First run: 367 occurrences fixed across 349 rows.

### Steps

- [x] **1.1 — Read existing search code**
  Read `mcp/server.py` search_transcripts() and search scripts. Found THREE files need fuzzy:
  - `mcp/server.py` — MCP tool, `search_transcripts()` line 216
  - `scripts/brain_search.py` — `/brain-search` slash command, `search_fts()` line 121
  - `scripts/brain_query.py` — `/brain-question` slash command, `search_fts()` line 120
  All three have separate `build_fts_query` implementations and separate zero-result handling.
  STOP_WORDS are duplicated across all three files (slightly different sets).
  Decision: create a shared fuzzy module (`scripts/fuzzy_search.py`) to avoid tripling the code.

- [x] **1.2 — Build vocabulary extraction function**
  Created `scripts/fuzzy_search.py` with:
  - `get_vocabulary(db_path)` — extracts 9,052 terms from FTS5 vocab table (3+ chars, alpha-only, no stop words, doc >= 2)
  - `get_frequencies(db_path)` — doc frequency per term for ratio calculations
  - `_ensure_vocab_table()` — creates `transcripts_fts_vocab` (FTS5 vocab virtual table) on first call
  - Module-level cache — builds once per process, reused on subsequent calls
  - Also added `DDL_FTS_VOCAB` to `brain-setup.py` so new installations get the vocab table at setup time

- [x] **1.3 — Build fuzzy match function**
  `fuzzy_correct(terms, db_path)` in `scripts/fuzzy_search.py`:
  - Uses `difflib.get_close_matches()` with cutoff 0.6, up to 5 candidates per term
  - Frequency-ratio approach: compares doc counts to distinguish typos from real words
  - Returns `(corrected_terms, corrections_map)` — corrections map is `{original: corrected}`
  - STOP_WORDS superset from all 5 search files consolidated in this module
  - Performance: 48ms cold cache, 28ms warm

- [x] **1.4 — Integrate into MCP server search_transcripts()**
  Modified `mcp/server.py`:
  - Added `import re`, `import sys`, `from scripts.fuzzy_search import fuzzy_correct`
  - Refactored `_build_fts_query` into `_is_fts5_syntax`, `_extract_keywords`, `_keywords_to_fts`
  - Extracted `_run_fts_query` and `_format_results` helper functions
  - Fuzzy runs BEFORE FTS: extract keywords → fuzzy_correct → build FTS query → run
  - FTS5 syntax queries bypass fuzzy entirely (passthrough)
  - If corrections made, prepends `**Did you mean:** 'sesion' → 'session'` header

- [x] **1.5 — Integrate into scripts/brain_search.py AND scripts/brain_query.py**
  Both scripts updated:
  - `brain_search.py` — imports `fuzzy_correct`, corrects keywords before `search_fts()`, prints "Did you mean:" line
  - `brain_query.py` — imports `fuzzy_correct`, corrects keywords before all searches, adds corrections to `format_results()` output
  - Both use corrected keywords for ALL search types (FTS, semantic, decisions, facts)

- [x] **1.6a — Transcript cleanup tool (clean_transcripts.py)**
  Created `scripts/clean_transcripts.py` — recurring maintenance tool that auto-detects and fixes misspellings in transcript content.
  - 6-layer typo detection: (1) dictionary check on term, (2) tech exclusion list, (3) ED=1 only, (4) similarity cutoff 0.85, (5) morphological variant filter, (6) dictionary check on correction target
  - FTS5 UPDATE trigger rebuilds index automatically — no manual rebuild needed
  - First run: 367 occurrences fixed across 349 rows (including "deploment"→"deployment", "sesion"→"session")
  - Imports `STOP_WORDS` and `clear_cache` from `fuzzy_search.py`

- [x] **1.6 — Test fuzzy search**
  All 8 tests PASS:
  1. Known typos: "sesion", "databse", "configration", "embeding" → corrected with "did you mean?" note
  2. Correct spelling: "session", "database", "project" → no correction, normal results
  3. Gibberish: "xyzqqq" → no correction, returns whatever FTS finds (or empty)
  4. Multi-word: "sesion summary" → corrects "sesion", keeps "summary"
  5. FTS5 syntax: `"session" OR "chapter"` → passthrough, no fuzzy
  6. Similar real words: "tests", "chapters", "version" → NOT corrected (established words)
  7. MCP server.py integration: "Did you mean" header, FTS5 passthrough, correct spelling clean
  8. brain_search.py and brain_query.py: "Did you mean" output working
  Performance: 48ms cold, 28ms warm — no degradation on correct-spelling queries.

- [x] **1.7 — Audit and commit**
  Re-read all 6 modified files cover to cover. No issues found. All imports correct, parameterized SQL throughout, no dead code. Committed.

---

## FEATURE 2: AUTO FACT EXTRACTION

**Goal:** Script that scans conversations, sends them to an LLM, and writes structured facts to the database automatically.
**Prerequisite:** Phase 8 (Architecture Merge) must be complete. generate_summary.py and OpenRouter summary infra deleted (session 22). Consumer scripts migrated to sys_sessions.notes (session 23). sys_session_summaries table dropped (session 25). Remaining Phase 8 steps: schema migration (F2), gap detection (F3), project summaries (F4). Feature 2 will use a clean LLM call approach (direct Anthropic API or similar).

### Steps

- [ ] **2.1 — Design LLM call approach (post-Phase 8)**
  generate_summary.py and OpenRouter config already removed (session 22). Design the new LLM call mechanism for fact extraction. Options: direct Anthropic API, or Claude Code subprocess. Read the `facts` table schema.

- [ ] **2.2 — Design the extraction prompt**
  Write the LLM prompt that takes a session transcript and returns structured facts as JSON.
  - Output format: `[{"project": "app", "category": "technology", "key": "frontend", "value": "React 19 with TypeScript"}]`
  - Categories: technology, architecture, feature, endpoint, decision, preference, pattern, status
  - Prompt must instruct: extract only concrete facts, not opinions or speculation
  - Prompt must handle multi-project sessions (extract facts for each project mentioned)

- [ ] **2.3 — Build scripts/extract_facts.py**
  Create the script:
  - Read config.yaml for API key and DB path
  - Query sessions that haven't been processed yet (tracking table or marker)
  - For each unprocessed session: fetch transcript, send to LLM, parse JSON response
  - Deduplicate against existing facts (same project+category+key = skip or update)
  - Insert new facts into the `facts` table
  - Mark session as processed
  - Progress reporting: "Processing session 5/20... extracted 3 new facts"

- [ ] **2.4 — Add extraction tracking**
  Decide tracking approach:
  - Option A: New column `facts_extracted` in `sys_sessions` (simple, no new table)
  - Option B: New table `fact_extraction_log` (more flexible, tracks per-fact source)
  - Pick one, implement it. Must be idempotent — re-running skips already-processed sessions.

- [ ] **2.5 — Test auto extraction**
  - Run on 3-5 recent sessions manually
  - Verify extracted facts are accurate and well-categorized
  - Verify dedup works (run again on same sessions, no duplicates)
  - Verify facts show up in `lookup_fact()` MCP queries
  - Test with a session that has no extractable facts (should handle gracefully)
  - Test with no API key configured (should fail with clear error message)

- [ ] **2.6 — Add slash command or hook integration (optional)**
  Decide: should extraction run automatically at session-end? Or manual-only?
  - Manual: user runs `/brain-extract` or `python3 scripts/extract_facts.py`
  - Automatic: session-end hook calls extract_facts after generating summary
  - Recommendation: start manual, add automatic later if it works well

- [ ] **2.7 — Audit and commit**
  Review all changes. Check for API key security (not logged, not exposed). Commit.

---

## FEATURE 3: EMAIL DIGESTS (Revised 2026-03-12, Session 36)

**Goal:** Premade email templates that show the brain reaching OUT to the user — weekly digests, daily standups, project deep dives. This is a competitive differentiator: no other AI memory tool does proactive outreach. Key selling point for open source launch.

**Strategic context (from BRAIN_BRAINSTORMING_IDEAS.md, session 9):**
- "Proactive outreach" is 1 of 6 things we have that nobody else does
- Email was positioned as a force multiplier and competitive differentiator
- Monday Morning Briefing (#1) and Dormant Project Alerts (#2) both APPROVED in session 9
- Mike's inception-to-date idea: "so someone can see all the work they did" — the forwardable email

**What already exists (built in session 9, updated through session 28):**
- `scripts/brain_digest.py` (580 lines) — weekly digest with 12 query functions
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

### Steps

- [ ] **3.1 — Add Daily Standup template (`--daily`)**
  - [ ] 3.1a — Design daily standup content: yesterday's sessions (topics, msg counts), decisions made, where things left off (last session notes excerpt), compact quick-scan format
  - [ ] 3.1b — Build `build_daily_html()` function in brain_digest.py
  - [ ] 3.1c — Add `--daily` flag to argparse
  - [ ] 3.1d — Test with `--daily --dry-run`, verify HTML renders clean
  - [ ] 3.1e — Test with `--daily` live send to Gmail

- [ ] **3.2 — Add Project Deep Dive template (`--project <prefix>`)**
  - [ ] 3.2a — Design project deep dive content: single project focus, all sessions for period, all decisions for that project, current project summary (from project_registry.summary), architecture snapshot, blockers and next steps
  - [ ] 3.2b — Build `build_project_html()` function in brain_digest.py
  - [ ] 3.2c — Add `--project` flag to argparse
  - [ ] 3.2d — Test with `--project mb --dry-run`, verify HTML
  - [ ] 3.2e — Test with `--project mb` live send

- [ ] **3.3 — Add cron entries for new templates**
  - [ ] 3.3a — Daily standup: `0 8 * * * python3 .../brain_digest.py --daily` (every morning 8am)
  - [ ] 3.3b — Weekly digest stays as-is (Monday 8am)
  - [ ] 3.3c — Document all cron options in the script's docstring

- [ ] **3.4 — Update config.yaml.example**
  - [ ] 3.4a — Verify email section exists with all fields documented
  - [ ] 3.4b — Add comments explaining Gmail app password setup
  - [ ] 3.4c — Add example cron lines as comments

- [ ] **3.5 — Update brain-setup.py**
  - [ ] 3.5a — Check if email config step exists in setup wizard
  - [ ] 3.5b — If not, add: "Do you want email digests? (y/n)" → SMTP details → test connection → save to config
  - [ ] 3.5c — Test setup flow with email enabled and disabled

- [ ] **3.6 — Write email use case ideas for docs**
  - [ ] 3.6a — Write use case list (10 ideas for open source users):
    1. Morning kickoff — daily standup at 8am, know exactly where you left off
    2. Weekly retrospective — see what you accomplished, spot productivity patterns
    3. Stakeholder update — forward the project deep dive to a manager or collaborator
    4. Dormant project alerts — catch projects you've neglected before they go stale
    5. Decision audit trail — weekly record of every architectural decision made
    6. Multi-project portfolio view — one email showing all projects at a glance
    7. Sprint boundary marker — send at end of sprint, archive for reference
    8. Onboarding context — forward to a new collaborator joining your project
    9. Accountability partner — auto-send to a friend/mentor to stay on track
    10. Personal changelog — monthly digest as a record of everything you built

- [ ] **3.7 — Update documentation**
  - [ ] 3.7a — README.md: add Email Digests section with overview + use cases
  - [ ] 3.7b — CLAUDE_BRAIN_HOW_TO.md: add email setup instructions (Gmail app password, cron, all 3 templates with examples)
  - [ ] 3.7c — Include example email output (text preview or screenshot description)

- [ ] **3.8 — Audit and commit**
  - [ ] 3.8a — Run code change checklist on brain_digest.py (grep all symbols, py_compile, test)
  - [ ] 3.8b — Verify no credentials in any committed file
  - [ ] 3.8c — Run brain_health.py — must be 9/9 PASS
  - [ ] 3.8d — Commit and push

---

## POST-BUILD

After all 3 features are built:

- [ ] **P.1 — Update CHANGELOG.md** with all three features
- [ ] **P.2 — Update POST_MVP_ROADMAP.md** — mark fuzzy search, auto-extraction, email as DONE
- [ ] **P.3 — Run full brain_health.py** — verify 9/9 PASS still holds
- [ ] **P.4 — Final README.md and HOW_TO review** — make sure docs match what's built
- [ ] **P.5 — Final commit and push to main**

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
| 113 | Transcript cleanup tool (`clean_transcripts.py`) fixes typos at the source | Recurring maintenance tool. Auto-detects typos via dictionary + ED=1 + frequency ratio. Modifies `transcripts.content` directly — FTS5 UPDATE trigger rebuilds index. 6-layer filtering prevents false positives. Mike's idea: fix the data, don't work around it. |
