# ARCHITECTURE MERGE PLAN — Notes/Summaries Unification + Project Summaries

**Created:** 2026-03-10 (Session 20)
**Status:** AGREED, NOT STARTED
**Prerequisite for:** Feature 2, Feature 3, and all pre-public work
**This document survives compaction. If context is lost, read this first.**

---

## WHAT WAS DECIDED (Session 20 Agreements)

1. **sys_session_summaries table is ELIMINATED.** One source of truth: `sys_sessions.notes`.
2. **generate_summary.py is DELETED.** No OpenRouter API. No Python fallback. Opus writes all notes.
3. **Gap detection is SILENT.** session-start.py detects missing notes, injects info into Claude's context (additionalContext). User sees nothing. Claude fills gaps automatically.
4. **Project summaries are NEW.** Living document per project on `project_registry`. Updated by Claude every end-session. Rich structure based on PM best practice + AI memory patterns.
5. **Session notes format is STANDARDIZED.** Topic on line 1, ## section headers, parseable by all consumers.
6. **All OpenRouter summary infrastructure is removed.** API key, config section, error handling — gone.

---

## SESSION NOTES FORMAT (standardized)

```
Topic: [One-line description of what the session was about]
Date: YYYY-MM-DD | Project: [prefix] | Provider: [model info]
Duration: ~Xm | Messages: N

## What Was Done
- Bullet points of accomplishments

## Decisions
- Decision #N: description (if any made)

## Files Modified
- path/to/file.py

## Current State
Where things stand at end of session.

## Blockers
What's blocking progress (or "None").

## Next Step
What to do next session.
```

---

## PROJECT SUMMARY FORMAT (new, living document per project)

```
Status: Active | Health: Green
Started: YYYY-MM-DD | Last session: YYYY-MM-DD
Sessions: N | Messages: N

## Summary
Two-sentence executive summary of the project and where it stands today.

## Accomplishments
- Major milestones achieved (cumulative, not per-session)

## In Progress
- What's actively being worked on right now

## Decisions
- Decision #N: description (only important/active ones)

## Architecture
- Key files, tools, structure (flexes by project type)

## Risks & Blockers
- What could go wrong or is stuck ("None" if clean)

## Next Steps
- Ordered priority list of what comes next

## Recent Sessions
- YYYY-MM-DD: [one-line description]
- YYYY-MM-DD: [one-line description]
- YYYY-MM-DD: [one-line description]
```

---

## SCHEMA CHANGES

```sql
-- New columns on project_registry
ALTER TABLE project_registry ADD COLUMN summary TEXT;
ALTER TABLE project_registry ADD COLUMN summary_updated_at TEXT;
ALTER TABLE project_registry ADD COLUMN status TEXT DEFAULT 'active';
ALTER TABLE project_registry ADD COLUMN health TEXT DEFAULT 'green';

-- After all code is updated and tested:
DROP TABLE sys_session_summaries;
```

---

## EXECUTION STEPS (in order)

### STEP 0: Safety Net (MUST DO FIRST)
- [ ] 0.1 — `git add` the 4 dirty files from session 19 (hooks/session-end.py, hooks/session-start.py, hooks/stop.py, scripts/write_session_notes.py)
- [ ] 0.2 — Commit: "Session 19 fixes: auto-detect session ID, remove DEVNULL from hooks"
- [ ] 0.3 — Tag: `git tag pre-architecture-merge`
- [ ] 0.4 — Copy `config.yaml` to `~/claude-brain-local/config.yaml.backup`
- [ ] 0.5 — Copy `~/.claude/settings.json` to `~/claude-brain-local/settings.json.backup`
- [ ] 0.6 — Create branch: `git checkout -b merge-notes-summaries`
- [ ] 0.7 — Verify: `git log --oneline -3` shows clean history, tag exists

### STEP 1: Schema Migration
- [ ] 1.1 — Add 4 columns to project_registry (summary, summary_updated_at, status, health)
- [ ] 1.2 — Verify all 125 sessions have notes (should already be true from session 19 backfill)
- [ ] 1.3 — Verify no sessions have notes=empty but summary=populated (if any, copy summary to notes)

### STEP 2: Delete generate_summary.py
- [ ] 2.1 — `git rm scripts/generate_summary.py`
- [ ] 2.2 — Remove `summary_llm` section from `config.yaml`
- [ ] 2.3 — Remove `summary_llm` section from `config.yaml.example`

### STEP 3: Update session-end.py
- [ ] 3.1 — Remove the call to generate_summary.py (lines 59-66)
- [ ] 3.2 — Keep the backup call (brain_sync.py)
- [ ] 3.3 — Test: `echo '{}' | python3 hooks/session-end.py` returns `{}`

### STEP 4: Update session-start.py
- [ ] 4.1 — Remove query to sys_session_summaries (lines 70-107)
- [ ] 4.2 — Add gap detection: query sys_sessions for recent sessions where notes IS NULL or notes = ''
- [ ] 4.3 — Inject gap info into additionalContext (for Claude's eyes, invisible to user)
- [ ] 4.4 — Inject current project summary from project_registry.summary
- [ ] 4.5 — Keep "Last Session Notes" injection (already reads from sys_sessions.notes)
- [ ] 4.6 — Test: `echo '{}' | python3 hooks/session-start.py` returns valid JSON

### STEP 5: Update consumer scripts (7 files)
- [ ] 5.1 — `brain_history.py`: Change subquery from sys_session_summaries to sys_sessions.notes
- [ ] 5.2 — `brain_recap.py`: Same change
- [ ] 5.3 — `brain_export.py`: Same change in export_recap_week()
- [ ] 5.4 — `brain_digest.py`: Change get_session_summaries() to query sys_sessions for notes; change get_brain_totals() to count notes instead of summaries; update build_email_html()
- [ ] 5.5 — `mcp/server.py`: Change get_recent_summaries() to read from sys_sessions.notes (rename tool or keep name)
- [ ] 5.6 — `brain_health.py`: Change summary coverage check to notes coverage check
- [ ] 5.7 — `startup_check.py`: Remove repair_missing_summaries(). Add notes gap count to startup output.

### STEP 6: Update brain-setup.py
- [ ] 6.1 — Remove sys_session_summaries CREATE TABLE from schema DDL
- [ ] 6.2 — Add new project_registry columns (summary, summary_updated_at, status, health) to DDL
- [ ] 6.3 — Verify setup still works for new installations (no summaries table expected)

### STEP 7: Drop the table
- [ ] 7.1 — Run ALL tests from the testing checklist below FIRST
- [ ] 7.2 — Only after all tests pass: DROP TABLE sys_session_summaries
- [ ] 7.3 — Run ALL tests AGAIN after the drop
- [ ] 7.4 — Run brain_health.py — must be 9/9 PASS

### STEP 8: Populate project summaries
- [ ] 8.1 — Write project summary for each active project (mb, jg, gen, js)
- [ ] 8.2 — Set status and health for each project
- [ ] 8.3 — Verify session-start.py injects project summary into additionalContext

### STEP 9: Update documentation (6 files)
- [ ] 9.1 — ARCHITECTURE.md: Remove sys_session_summaries from table list, update count (12->11 tables, then +4 columns), update dependency chain
- [ ] 9.2 — README.md: Update architecture section, remove references to summaries table
- [ ] 9.3 — CLAUDE_BRAIN_HOW_TO.md: Update any summaries references
- [ ] 9.4 — FEATURE_PLAN.md: Update Feature 2 and 3 to reflect removed OpenRouter dependency
- [ ] 9.5 — verification/TEST_SPECIFICATIONS.md: Update test cases
- [ ] 9.6 — verification/SCRIPT_CONTRACTS.md: Update contracts for changed scripts

### STEP 10: Update end-session protocol
- [ ] 10.1 — Update CLAUDE.md end-session protocol to include project summary update
- [ ] 10.2 — Update MEMORY.md end-session protocol
- [ ] 10.3 — Update SESSION_PROTOCOLS.md if it exists
- [ ] 10.4 — Write new write_project_summary.py script (or add function to write_session_notes.py)

### STEP 11: Final commit and merge
- [ ] 11.1 — Run full test suite one final time
- [ ] 11.2 — Commit on branch: "Architecture merge: eliminate sys_session_summaries, add project summaries"
- [ ] 11.3 — Merge to main: `git checkout main && git merge merge-notes-summaries`
- [ ] 11.4 — Tag: `git tag post-architecture-merge`
- [ ] 11.5 — Push to GitHub

---

## TESTING CHECKLIST (run at Step 7.1, 7.3, and 11.1)

| # | Test | Command | Pass Criteria |
|---|------|---------|---------------|
| T1 | session-start.py | `echo '{}' \| python3 hooks/session-start.py` | Valid JSON. Notes in context. No summaries query. Project summary present. |
| T2 | session-end.py | `echo '{}' \| python3 hooks/session-end.py` | Returns `{}`. No generate_summary call. Backup runs. |
| T3 | stop.py | `echo '{}' \| python3 hooks/stop.py` | Returns `{}`. No changes (was not affected). |
| T4 | brain_history.py | `python3 scripts/brain_history.py --count 5` | Shows topics from notes. No crash. |
| T5 | brain_recap.py | `python3 scripts/brain_recap.py --week` | Shows topics from notes. No crash. |
| T6 | brain_export --recap | `python3 scripts/brain_export.py --recap-week` | Exports file. Topics from notes. |
| T7 | brain_digest.py | `python3 scripts/brain_digest.py --dry-run` | Generates HTML. Session highlights from notes. No crash. |
| T8 | brain_health.py | `python3 scripts/brain_health.py` | 9/9 PASS. Notes coverage replaces summary coverage. |
| T9 | startup_check.py | `python3 scripts/startup_check.py` | Completes. No repair calls. Reports gap count. |
| T10 | brain-setup.py (inspect) | Read the DDL section | No sys_session_summaries CREATE. New project_registry columns present. |
| T11 | MCP server | Import test or MCP call | get_recent_summaries/notes returns data from sys_sessions.notes. |
| T12 | DB integrity | Python: `conn.execute("PRAGMA integrity_check")` | Returns "ok". |
| T13 | Notes coverage | Python: `SELECT COUNT(*) FROM sys_sessions WHERE notes IS NULL OR notes = ''` | Should be 1 (current session only). |
| T14 | No summaries refs | `grep -r "sys_session_summaries" scripts/ hooks/ mcp/` | Zero matches after Step 7.2. |
| T15 | Project summaries | Python: `SELECT prefix, LENGTH(summary) FROM project_registry WHERE summary IS NOT NULL` | Active projects have summaries. |

---

## FILES AFFECTED (complete list)

**DELETED:**
- scripts/generate_summary.py

**MODIFIED (code):**
- hooks/session-end.py
- hooks/session-start.py
- scripts/brain_history.py
- scripts/brain_recap.py
- scripts/brain_export.py
- scripts/brain_digest.py
- scripts/brain_health.py
- scripts/startup_check.py
- scripts/brain-setup.py
- mcp/server.py
- config.yaml
- config.yaml.example (if exists)

**MODIFIED (docs):**
- ARCHITECTURE.md
- README.md
- CLAUDE_BRAIN_HOW_TO.md
- FEATURE_PLAN.md
- verification/TEST_SPECIFICATIONS.md
- verification/SCRIPT_CONTRACTS.md
- CLAUDE.md (end-session protocol)
- memory/MEMORY.md

**NEW (possibly):**
- scripts/write_project_summary.py (or integrated into write_session_notes.py)

**DB CHANGES:**
- ALTER TABLE project_registry: +4 columns
- DROP TABLE sys_session_summaries

---

## UPDATED END-SESSION PROTOCOL (after merge)

1. Write session notes -> `sys_sessions.notes` (standardized format, Topic on line 1)
2. Update project summary -> `project_registry.summary` (rewrite, not append)
3. Update MEMORY.md LAST SESSION as backup
4. Update governance files (tracker, schema, dependencies) as needed
5. Confirm: "Session logged. Project summary updated. Governance updated."
