# SESSION PROTOCOLS - claude-brain

Human-readable backup of session start and end protocols.
Primary source: brain database (brain_preferences table).

---

## SESSION START PROTOCOL

Do this EVERY session. Output the checklist table BEFORE doing anything else.

1. Search the brain (search_transcripts + get_recent_summaries).
2. Read PROJECT_TRACKER.md - know where we are.
3. Review session-start hook output - it injects a verification checklist, last session notes, and flagged unfinished items automatically. Do NOT skip these.
4. If picking up unfinished work: VERIFY the premise independently before acting. Reproduce the problem. Identify which component is actually failing. Never trust prior notes blindly.
5. **PRESENT unfinished items and NEXT_SESSION.md notes to the user prominently.** They need to SEE and react to them -- not just a checkmark.
6. Never re-ask locked decisions. Never start coding without Mike's GO.
7. Output this verified checklist (EVERY item must show DONE):

```
┌─────────────────────────────────────┬──────────┐
│ Start-Session Checklist             │ Status   │
├─────────────────────────────────────┼──────────┤
│ Brain searched                      │ ✓ DONE   │
├─────────────────────────────────────┼──────────┤
│ PROJECT_TRACKER.md read             │ ✓ DONE   │
├─────────────────────────────────────┼──────────┤
│ Session-start hook output reviewed  │ ✓ DONE   │
├─────────────────────────────────────┼──────────┤
│ Unfinished items SHOWN to user      │ ✓ DONE   │
├─────────────────────────────────────┼──────────┤
│ Next-session notes SHOWN to user    │ ✓ DONE   │
└─────────────────────────────────────┴──────────┘
```

8. Confirm ready: "MEMORY.md loaded. Brain searched. Last session: [summary]. Tracker read. Current step: [step]. Ready."

If ANY row shows ✗ MISSING, STOP and fix it before proceeding.

### Hook-Enforced Behaviors (automated, non-negotiable)

**session-start.py** injects into every session:
- Verification checklist (verify premises, use brain tools, don't trust notes blindly)
- Full last session notes
- Flagged unfinished/unverified items from last session (anything marked NOT DONE, unverified, etc.)
- Recent session topics grouped by project

**user-prompt-submit.py** runs on every message:
- Searches brain for relevant memories based on prompt keywords
- **Frustration circuit breaker:** If Mike's message indicates frustration (anger keywords, caps, repeated punctuation), the hook automatically searches the brain for the current topic and injects a STOP directive + brain context. This forces a reassessment instead of continuing down a wrong path.

---

## END-SESSION PROTOCOL

When Mike says "end session" (or similar: "wrap up", "done for today", "close it out"), do ALL of these:

1. Write session notes to DB:
   `python3 scripts/write_session_notes.py --notes "<text>"`
   Include: date, provider, what was done, decisions, files modified, current state, next step.
2. Update project summary in DB:
   `python3 scripts/write_project_summary.py --prefix <prefix> --summary "<text>"`
   Rewrite the FULL summary reflecting current state - not a patch, a complete rewrite.
3. Update MEMORY.md LAST SESSION section as backup.
4. Update governance files: PROJECT_TRACKER.md, FEATURE_PLAN.md, NEXT_SESSION_START_PROMPT.txt.
5. Git commit + push all changes.
6. Output verified checklist table. EVERY row must show ✓ DONE:

```
┌─────────────────────────────┬──────────┐
│ End-Session Checklist       │ Status   │
├─────────────────────────────┼──────────┤
│ Session notes written to DB │ ✓ DONE   │
├─────────────────────────────┼──────────┤
│ Project summary updated     │ ✓ DONE   │
├─────────────────────────────┼──────────┤
│ MEMORY.md updated           │ ✓ DONE   │
├─────────────────────────────┼──────────┤
│ Governance files updated    │ ✓ DONE   │
├─────────────────────────────┼──────────┤
│ Git committed + pushed      │ ✓ DONE   │
└─────────────────────────────┴──────────┘
```

If ANY row shows ✗ MISSING, STOP and fix it before closing.

**Why this matters:** Project summaries power the daily and weekly email digests.
If the summary isn't updated, tomorrow's emails show stale data. This was missed
in sessions 29-35 (project summary only updated when explicitly asked, not at
end-of-session). The checklist table makes it impossible to skip.

---

## MIKE'S WORKING STYLE (process rules)

- Architect, not coder. Wants polished work. Never assume.
- Step-by-step execution with checkpoints. Present and wait for GO.
- Brutal honesty. No fluff. Quality over speed.
- Every step gets an independent audit before marking done.
- Break big steps into 4 checkpoints: create → build → test → audit report.
- Update PROJECT_TRACKER.md after every step. It's the single source of truth.
- Update FOLDER_SCHEMA.md at end of each phase or when folders change.
- Update DEPENDENCIES.md when any package/tool changes.
- New decisions go in PROJECT_TRACKER.md → BUILD-PHASE DECISIONS section.
- Before presenting any multi-step plan to Mike: do an end-to-end walkthrough from his perspective. Simulate step by step. Find gaps, fix them, THEN present.
