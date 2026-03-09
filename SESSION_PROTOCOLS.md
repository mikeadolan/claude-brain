# SESSION PROTOCOLS — claude-brain

Human-readable backup of session start and end protocols.
Primary source: brain database (brain_preferences table).

---

## SESSION START PROTOCOL

Do this EVERY session:

1. Read PROJECT_TRACKER.md FIRST — know where we are before doing anything
2. Read CLAUDE_BRAIN_MVP_PLAN.txt (root) — the MASTER PROJECT PLAN with full architecture
3. Check BUILD-PHASE DECISIONS section in tracker for recent decisions
4. Check OPEN ITEMS in tracker for unresolved blockers
5. Confirm current step with Mike before starting work
6. Never re-ask locked decisions — they're in the tracker and MVP plan
7. Never start coding without Mike's GO
8. Read LAST SESSION notes — know what happened last time
9. If resuming after a provider switch or long gap: use /brain-recap or /brain-history for multi-session context
10. When Mike says "start session" or opens with a task, follow this protocol then confirm ready with a brief status line: "MEMORY.md loaded. Last session: [one-line summary]. Tracker read. Current step: [phase/step]. Ready." — do not recite the full protocol, just this confirmation.

---

## END-SESSION PROTOCOL

When Mike says "end session" (or similar: "wrap up", "done for today", "close it out"), do ALL of these:

1. Write session notes to the brain database via write_session_notes.py:
   - Date, provider (Max or OpenRouter), approximate duration
   - What was done — detailed and thorough, as many bullets as needed
   - Decisions made (with numbers from tracker if applicable)
   - Files created (every new file)
   - Files modified (every changed file)
   - Current state (exact phase/step)
   - Blockers or issues discovered
   - Exact next step
2. Update PROJECT_TRACKER.md if any steps changed status
3. Update FOLDER_SCHEMA.md if any folders or files were created
4. Update DEPENDENCIES.md if any packages or tools changed
5. New decisions go in PROJECT_TRACKER.md → BUILD-PHASE DECISIONS section
6. Confirm to Mike: "Session logged. Governance updated."

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
