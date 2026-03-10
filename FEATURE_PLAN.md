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
Phase 8 eliminates sys_session_summaries and generate_summary.py. Feature 2 will use direct Anthropic API calls (not OpenRouter/Haiku). See ARCHITECTURE_MERGE_PLAN.md.

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
**Prerequisite:** Phase 8 (Architecture Merge) must be complete. generate_summary.py and OpenRouter infra will be deleted in Phase 8. Feature 2 will use a new, clean LLM call approach (direct Anthropic API or similar).

### Steps

- [ ] **2.1 — Design LLM call approach (post-Phase 8)**
  Phase 8 removes generate_summary.py and all OpenRouter config. Design the new LLM call mechanism for fact extraction. Options: direct Anthropic API, or Claude Code subprocess. Read the `facts` table schema.

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

## FEATURE 3: EMAIL DIGESTS

**Goal:** Scheduled email summaries of brain activity — daily recaps, weekly progress, dormant project alerts, pattern detection.

### Steps

- [ ] **3.1 — Read existing query infrastructure**
  Read MCP server queries (get_recent_sessions, get_recent_summaries, get_status) to understand what data we can pull. Read config.yaml.example for current config structure.

- [ ] **3.2 — Design email config schema**
  Add to config.yaml.example:
  ```yaml
  email:
    enabled: false
    smtp_host: "smtp.gmail.com"
    smtp_port: 587
    sender: "your-email@gmail.com"
    recipient: "your-email@gmail.com"
    password: ""  # App password for Gmail, or SMTP password
    daily_digest: true
    weekly_digest: true
    dormant_alert_days: 14
  ```

- [ ] **3.3 — Build email query functions**
  Functions that query the brain for email content:
  - `get_daily_recap(db_path, date)` — sessions, projects, decisions, quality for one day
  - `get_weekly_progress(db_path, start_date)` — aggregate stats for the week
  - `get_dormant_projects(db_path, threshold_days)` — projects with no activity
  - `get_pattern_report(db_path, start_date)` — quality trends, frustrated sessions, rework

- [ ] **3.4 — Build HTML email templates**
  Clean, readable HTML email templates for each digest type.
  - Must work in Gmail, Outlook, Apple Mail (inline CSS, no fancy layout)
  - Header with brain logo/name
  - Sections with headers, tables, bullet points
  - Footer with "Generated by claude-brain" and unsubscribe note

- [ ] **3.5 — Build scripts/email_digest.py**
  Main script:
  - Read config.yaml for email settings and DB path
  - Accept arguments: `--daily`, `--weekly`, `--dormant`, `--pattern`, `--all`
  - Query brain, format email, send via SMTP
  - Logging: log what was sent and when
  - Error handling: clear message if SMTP fails (wrong password, network, etc.)

- [ ] **3.6 — Test email delivery**
  - Send a test daily digest to a real email address
  - Verify HTML renders correctly in Gmail
  - Test with no sessions in time range (should send "quiet day" message, not error)
  - Test with SMTP misconfigured (should fail with clear error)
  - Test each digest type independently

- [ ] **3.7 — Document cron setup**
  Write clear instructions for scheduling:
  - Daily: `0 8 * * * python3 /path/to/scripts/email_digest.py --daily`
  - Weekly: `0 8 * * 1 python3 /path/to/scripts/email_digest.py --weekly`
  - Include in README and HOW_TO
  - Optional: script can self-install cron entries (`--install-cron`)

- [ ] **3.8 — Update config.yaml.example**
  Add email section with comments explaining each field.

- [ ] **3.9 — Update brain-setup.py (optional)**
  Add email configuration step to the setup wizard:
  - "Do you want email digests? (y/n)"
  - If yes: ask for SMTP details, test connection, save to config
  - If no: skip, can enable later

- [ ] **3.10 — Update documentation**
  Add email digest section to README.md and CLAUDE_BRAIN_HOW_TO.md.
  - Setup instructions
  - Example email screenshots or text previews
  - 5 high-impact prompt examples for email content

- [ ] **3.11 — Audit and commit**
  Review all changes. Verify no credentials in committed files. Commit.

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
