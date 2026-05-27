# CHANGELOG

All notable changes to claude-brain.

---

## [0.3.1] - 2026-05-26 (PENDING PUSH TO MAIN)

### Fixed
- **Fuzzy correction silently corrupting searches for rare technical terms.** `scripts/fuzzy_search.py` was correcting any in-vocab term with doc < 100 if a close match had 20x+ frequency. This silently swapped technical terms like `PreCompact` (used heavily in brain conversations, ~50-90 docs) for unrelated common words like `prompt` (10,000+ docs). Result: searches for PreCompact, PostCompact, FastMCP, and other CamelCase/technical terms returned wrong results. Fix: added `_RARE_DOC_MAX = 30` constant — only correct in-vocab terms that appear in fewer than 30 docs AND meet the existing 20x ratio. Technical terms with 30+ legitimate uses are now protected. Caught by Codex bootstrap testing — Codex called `search_transcripts("PreCompact hook")` and got prompt-related results back. (Discovered during Codex integration verification, 2026-05-26.)

---

## [0.3.0] - 2026-04-13

### Added - /clear safety (the brain makes /clear a safe restart button)

For every other Claude Code user, `/clear` is destructive — it wipes context to free tokens and you lose continuity. With claude-brain, `/clear` now becomes a **safe restart**: the brain captures everything in real-time (already did), and on the first prompt after `/clear` it automatically restores context so Claude picks up where you left off.

- **session-end hook — `/clear` trigger detection.** Reads the `reason` field from the SessionEnd stdin JSON. On `reason == "clear"`, writes a `CLEAR_CHECKPOINT` marker to the ended session's notes instead of the generic fallback. Skips the auto-tag suggestion so Claude can write proper tags during post-/clear recovery.
- **user-prompt-submit hook — post-/clear detection + context recovery.** On each prompt, checks if a session in the same project ended < 5 minutes ago with a `CLEAR_CHECKPOINT` marker and a different session_id from the current one. When that pattern matches, injects recovery context automatically: the current project summary, the last 10 exchanges (user + assistant) from the ended session, and instructions to write proper notes for the ended session before responding to the user.
- **Works with existing upstream bug.** Anthropic's `SessionStart` hook does NOT fire on `/clear` (GitHub #34072, open). The UserPromptSubmit-based detection is a workaround that does not depend on the buggy SessionStart trigger, so it works today.

### Fixed
- **Stale script count.** README.md referenced an outdated script count from the launch era. Synced to the actual count (25 Python scripts).
- **brain_consistency.py false positives.** The script count check counted all `*.py` files on disk in `scripts/`, including any locally gitignored helpers, which inflated the count vs the public docs. Switched to counting git-tracked files only via `git ls-files`. The empty-notes check flagged active sessions that hadn't yet written end-of-session notes; added a 1-day freshness filter so only sessions that ended more than a day ago are checked, matching the existing untagged-session pattern.

---

## [0.2.1] - 2026-04-06

### Improved
- **user-prompt-submit hook** - fuzzy correction runs before FTS5 search (catches typos before they miss results), result content bumped from 200 to 400 characters, results increased from 3 to 5, recency weighting added (recent messages rank higher), hyphenated terms preserved as single keywords instead of being split.
- **stop hook** - auto-backup trigger checks backup age on every Claude response, runs `brain_sync.py` if the last backup is older than 12 hours. Prevents long-running sessions from going days without a backup.

### Fixed
- **FTS5 stale vocab cache** - MCP server vocabulary cache never refreshed, causing real words like "headless" to be autocorrected to "handles". Fix: 60-second cache TTL with live DB fallback before correcting. (Already on main in 0.2.0, listed here for completeness.)

---

## [0.2.0] - 2026-03-12

### Added - Feature 3: Email Digests (the brain reaches OUT to you)
- **3 email templates** via `scripts/brain_digest.py`:
  - **Daily standup** (`--daily`) - BLUF "Pick Up Here" per project, RAG health badges, blockers, in-progress, 7-day rolling average, quiet day handling. 150-250 words.
  - **Weekly digest** (default) - executive summary, week-over-week trend table, RAG portfolio with project context, top accomplishments, amber dormant alerts, forward nudge. 300-500 words.
  - **Project deep dive** (`--project mb`) - RAG header, executive summary, health metrics, in-progress, recent sessions, risks & blockers, next steps, decisions, architecture. 500-800 words.
- **Dark mode** (`--dark` flag or `email.dark_mode: true` in config) - full dark palette.
- **Email setup wizard** - Phase 7 in `brain-setup.py`: Gmail App Password, SMTP test, auto cron install.
- **`scripts/write_project_summary.py`** - update project summaries from CLI (end-session protocol).
- **10 email use cases** in README.md - Morning Kickoff, Stakeholder Update, Sprint Retro, etc.
- **Email design spec** - `email-digest-design-spec.md` (839 lines, BLUF methodology, HTML constraints).

### Added - Feature 1: Fuzzy Search (completed earlier, not in prior changelog)
- **`scripts/fuzzy_search.py`** - typo correction before FTS query using frequency-ratio approach.
- **`scripts/clean_transcripts.py`** - recurring maintenance tool, fixes typos at the source.
- Integrated into MCP server, brain_search.py, brain_query.py.

### Added - Infrastructure
- **Rule #2 GO check hook** - `user-prompt-submit.py` detects "thoughts?" without GO, injects STOP reminder.
- **Rule #1 expanded** - brain search + Exa web search before all work.
- **End-session verified checklist** - table with solid lines, every row must show DONE.
- **`CLAUDE.md.example`** - generic version for new users (brain-first rule included).
- **Token monitor** - `cc-updated.sh` with desktop notifications at 25/50/70/80/90% thresholds.
- **Office skills** - docx, xlsx, pdf, pptx skills installed from tfriedel/claude-office-skills.
- **Exa MCP** - web search registered for Claude Code.

### Changed - Phase 8: Architecture Merge (CLOSED)
- `sys_session_summaries` table eliminated. Single source: `sys_sessions.notes`.
- `project_registry` gained 4 columns: `summary`, `summary_updated_at`, `status`, `health`.
- All 113 session notes rewritten by Opus. All 7 project summaries regenerated.
- Tag: `post-architecture-merge` (15/15 tests pass).

### Changed - HTML Email Foundation
- All email styles inline (Gmail web strips `<style>` blocks).
- Safe HTML skeleton: DOCTYPE, xmlns, MSO conditional comments, color-scheme meta.
- Preheader text for inbox preview. #1a1a1a text (not #000000) for dark mode safety.

### Fixed
- **All 9 bugs closed** - B1-B7 FIXED, B8-B9 WONTFIX (upstream CC bug #5506).
- **Project summary staleness** - end-session protocol now requires summary update with verified checklist.

---

## [0.1.1] - 2026-03-10

### Fixed
- **SessionEnd hook timeout (Bug 1)** - Root cause: `generate_summary.py` made 30s OpenRouter API call, exceeding hook timeout. Fix: deleted `generate_summary.py` entirely. `session-end.py` now only runs `brain_sync.py` (detached).
- **MCP server unclean shutdown (Bug 2)** - Root cause: `sys.exit(0)` in signal handler raises `SystemExit` through asyncio event loop. Fix: changed to `os._exit(0)` for clean OS-level exit.
- **UTC timestamps** - All 4 scripts with logging now use `time.gmtime` converter so "Z" suffix is accurate (was using local time).

### Removed
- **`scripts/generate_summary.py`** - Deleted. Claude writes session notes directly. No LLM summary generation. No OpenRouter dependency.
- **`summary_llm` config section** - Removed from `config.yaml`, `config.yaml.example`, and `brain-setup.py` setup wizard.
- **`repair_missing_summaries()`** - Removed from `startup_check.py` (called deleted generate_summary.py).
- **generate_summary call in `import_claude_ai.py`** - Removed dead subprocess call block.

### Changed
- `hooks/session-end.py` - Complete rewrite. Only runs `brain_sync.py` (detached via `Popen`).
- `mcp/server.py` - Signal handler uses `os._exit(0)` instead of `sys.exit(0)`.
- Documentation updated: ARCHITECTURE.md, FOLDER_SCHEMA.md, SCRIPT_CONTRACTS.md, TEST_SPECIFICATIONS.md, POST_MVP_ROADMAP.md, PROJECT_TRACKER.md, CHANGELOG.md.
- Added CODE CHANGE CHECKLIST to CLAUDE.md and MEMORY.md.

---

## [0.1.0] - 2026-03-09

### Added
- **Bash-to-Python migration complete** - all hooks and scripts are now pure Python. No bash dependencies. Cross-platform ready (Linux, macOS; Windows via WSL).
- **Batch embedding backfill** - `scripts/batch_embed.py` backfills semantic search vectors for all existing transcripts.
- **requirements.txt** - standard Python dependency file for pip install.
- **Email digest framework** - architecture supports scheduled email summaries (daily recaps, weekly progress, dormant project alerts).

### Changed
- All 4 hooks rewritten from bash to Python (`hooks/*.py`).
- All support scripts rewritten from bash to Python (`scripts/brain_sync.py`, `scripts/startup_check.py`).
- Documentation rewritten for public release (README.md, CLAUDE_BRAIN_HOW_TO.md).
- Project prefix standard set to 2-3 characters (was 2-4).
- Brain health check now achieves 9/9 PASS (embedding coverage at 100%).

### Removed
- All `.sh` shell scripts (replaced by `.py` equivalents).
- Internal/personal references from public-facing documentation.

---

## [0.0.1] - 2026-02-01

### Added
- Initial implementation - SQLite database, 4 lifecycle hooks (bash), MCP server with 11 tools.
- 11 slash commands (`/brain-question`, `/brain-search`, `/brain-history`, `/brain-recap`, `/brain-decide`, `/brain-health`, `/brain-status`, `/brain-import`, `/brain-questionnaire`, `/brain-setup`, `/brain-export`).
- Dual search: FTS5 keyword search + semantic search (sentence-transformers + numpy).
- Session quality scoring and tagging.
- Claude.ai conversation import via Chrome extension export.
- Interactive setup wizard (`brain-setup.py`).
- Multi-machine support via Dropbox/cloud sync.
- ~~LLM-powered session summaries via direct API call (OpenRouter/Anthropic).~~ (Removed in 0.1.1 - generate_summary.py deleted, Claude writes notes directly.)
