# MIGRATION: Bash to Python Hook Conversion

**Created:** 2026-03-09
**Purpose:** Convert all .sh hooks and scripts to .py for cross-platform support (Linux + Mac + Windows)
**Status:** COMPLETE — all phases A-F done, merged to main, pushed to GitHub (2026-03-09)

---

## SAFETY

- **Git backup branch:** `main-backup-pre-migration` — full snapshot including config.yaml and settings.json copy
- **Work branch:** `migration/bash-to-python` — all changes happen here
- **Main branch:** UNTOUCHED until everything is tested, audited, and locked
- **Rollback:** `git checkout main` + restore settings.json = working brain in 10 seconds
- **Database:** Not touched in this migration. Dropbox backup covers it.
- **.sh files:** Stay in place until Phase F cleanup. Brain runs on .sh the entire time.

---

## PHASE A: PREPARATION

| # | Step | Status | Notes |
|---|------|--------|-------|
| A.1 | Commit any uncommitted changes to main | [x] | 958e7db — migration doc + competitive analysis script |
| A.2 | Create `main-backup-pre-migration` branch with config.yaml + settings.json copy | [x] | dc968d9 — config.yaml + settings.json.backup |
| A.3 | Return to main, create `migration/bash-to-python` branch | [x] | On branch, clean working tree |
| A.4 | This document committed to work branch | [x] | Phase A marked complete |

---

## PHASE B: CONVERT SCRIPTS (one at a time — write, test, compare, audit, lock)

Order matters. brain_sync must come before session-end (which calls it).

### B.1: stop.sh → stop.py (simplest — 37 lines, standalone)

| Step | Status | Notes |
|------|--------|-------|
| Write hooks/stop.py | [x] | 53 lines, clean Python |
| Manual test: `echo '{}' \| python3 hooks/stop.py` | [x] | Outputs `{}` |
| Compare output to: `echo '{}' \| bash hooks/stop.sh` | [x] | Both output `{}` — identical |
| Verify write_exchange.py was called (check DB or logs) | [x] | JSONL detection verified: finds same file + session ID as .sh |
| Audit: code review stop.py vs stop.sh logic | [x] | 8/8 lines mapped, path encoding verified identical |
| **LOCKED** | [x] | |

**Key translations:**
- `sed 's|^/|-|; s|/|-|g'` → Python string ops
- `ls -t *.jsonl | head -1` → `sorted(glob.glob(...), key=os.path.getmtime)[-1]`
- `cat > /dev/null` → `sys.stdin.read()`
- `basename "$JSONL_PATH" .jsonl` → `Path(jsonl_path).stem`

---

### B.2: brain_sync.sh → brain_sync.py (115 lines, standalone backup script)

| Step | Status | Notes |
|------|--------|-------|
| Write scripts/brain_sync.py | [x] | 103 lines, clean Python |
| Manual test: `python3 scripts/brain_sync.py` | [x] | Backup created, 172MB, integrity passed |
| Compare: backup file exists, size > 0, integrity passes | [x] | Same path, same size as .sh output |
| Compare log output format | [x] | Identical format. Python skips sqlite3 CLI fallback (better) |
| Audit: code review brain_sync.py vs brain_sync.sh logic | [x] | 12/12 lines mapped. shutil.copy2 = cp -p. os.path.getsize = stat. |
| **LOCKED** | [x] | |

**Key translations:**
- `cp -p` → `shutil.copy2()`
- `stat -c%s` / `stat -f%z` → `os.path.getsize()`
- `mkdir -p` → `os.makedirs(..., exist_ok=True)`
- `sqlite3 PRAGMA integrity_check` → `sqlite3.connect().execute()`
- `date -u` → `datetime.utcnow().strftime()`
- `set -euo pipefail` → try/except with sys.exit(1)
- log() function → Python logging or same file-append pattern

---

### B.3: session-end.sh → session-end.py (55 lines, calls brain_sync)

| Step | Status | Notes |
|------|--------|-------|
| Write hooks/session-end.py | [x] | 80 lines, calls brain_sync.py |
| Manual test: `echo '{}' \| python3 hooks/session-end.py` | [x] | Outputs `{}` |
| Compare output to: `echo '{}' \| bash hooks/session-end.sh` | [x] | Both output `{}` — identical |
| Verify generate_summary.py was called | [x] | Runs without error |
| Verify brain_sync.py was called (new backup exists) | [x] | Log confirms: 14:27:18 "Integrity check passed" |
| Audit: code review session-end.py vs session-end.sh logic | [x] | 9/9 lines mapped. Project detection verified: both return `mb` |
| **LOCKED** | [x] | |

**Key translations:**
- Same path encoding as stop.sh (sed → Python)
- Same JSONL detection as stop.sh (ls -t → glob+sorted)
- Inline Python for project detection → direct Python function
- `bash "$ROOT/scripts/brain_sync.sh"` → `subprocess.run([sys.executable, brain_sync_path])`

---

### B.4: session-start.sh → session-start.py (111 lines, mostly inline Python already)

| Step | Status | Notes |
|------|--------|-------|
| Write hooks/session-start.py | [x] | 113 lines, inline Python extracted to proper script |
| Manual test: `echo '{}' \| python3 hooks/session-start.py` | [x] | Valid JSON with session notes + summaries |
| Compare output to: `echo '{}' \| bash hooks/session-start.sh` | [x] | Byte-for-byte identical (diff returned nothing) |
| Verify startup_check.py was called | [x] | Runs via subprocess without error |
| Audit: code review session-start.py vs session-start.sh logic | [x] | Inline heredoc → native Python. All DB queries identical. |
| **LOCKED** | [x] | |

**Key translations:**
- Bash wrapper is thin — the inline Python heredoc becomes the actual script
- `python3 "$ROOT/scripts/startup_check.py"` → `subprocess.run()`
- Fallback JSON logic (bash `if -z`) → Python try/except already handles it

---

### B.5: user-prompt-submit.sh → user-prompt-submit.py (168 lines, most complex)

| Step | Status | Notes |
|------|--------|-------|
| Write hooks/user-prompt-submit.py | [x] | 148 lines, same logic as inline heredoc |
| Manual test with sample prompt: `echo '{"prompts":[{"content":"test search query for chapter"}]}' \| python3 hooks/user-prompt-submit.py` | [x] | Returns relevant memories JSON |
| Compare output to same input via .sh | [x] | Byte-for-byte identical (diff returned nothing) |
| Test with short prompt (<15 chars): `echo '{"prompts":[{"content":"hi"}]}' \| python3 hooks/user-prompt-submit.py` | [x] | Returns `{}` — both versions match |
| Audit: code review user-prompt-submit.py vs user-prompt-submit.sh logic | [x] | Same STOP_WORDS, FTS5, project bias, dedup. Empty input also tested. |
| **LOCKED** | [x] | |

**Key translations:**
- Bash wrapper is thin — the inline Python heredoc becomes the actual script
- `INPUT=$(cat)` → `sys.stdin.read()`
- Fallback JSON logic → Python try/except already handles it

---

## PHASE C: UPDATE CODE REFERENCES

Only after ALL Phase B steps are LOCKED.

| # | File | What to change | Status |
|---|------|---------------|--------|
| C.1 | `scripts/brain_health.py` (lines 433-436) | `.sh` → `.py` in hook filename validation | [x] |
| C.2 | `scripts/brain-setup.py` (line 32 + line 741 + line 905) | `HOOK_SCRIPTS` list `.sh` → `.py` + config template + `bash` → `python3` in hook command builder | [x] |
| C.3 | `scripts/startup_check.py` (line 11) | Comment: `session-start.sh` → `session-start.py` | [x] |
| C.4 | `scripts/write_exchange.py` (line 6) | Comment: `stop.sh` → `stop.py` | [x] |
| C.5 | `scripts/write_session_notes.py` (line 6) | Comment: `session-start.sh` → `session-start.py` | [x] |
| C.6 | `scripts/generate_summary.py` (line 10) | Comment: `session-end.sh` → `session-end.py` | [x] |
| C.7 | `config.yaml.example` (line 242) | `brain_sync.sh` → `brain_sync.py` | [x] |
| C.8 | Test: run `brain_health.py` — hook check validates .py names | [x] | Hooks FAIL expected: settings.json still has .sh (Phase D fixes this). All other checks pass. |
| C.9 | Audit: grep entire repo for `.sh` refs AND `bash` as interpreter | [x] | 1 extra fix: startup_check.py:171 stale comment. Old .sh files + competitive analysis doc = safe (expected). |
| **LOCKED** | | | [x] |

---

## PHASE D: SWITCH HOOKS (all at once, test via session boundary)

| # | Step | Status | Notes |
|---|------|--------|-------|
| D.1 | Update `~/.claude/settings.json` — all 4 hooks from `.sh` to `.py` | [x] | All 4: bash→python3, .sh→.py |
| D.2 | End session — `session-end.py` fires (live test) | [x] | Notes + summary + backup present for session 566dfb2c |
| D.3 | Start new session — `session-start.py` fires (live test) | [x] | "SessionStart:startup hook success" confirmed |
| D.4 | Type a prompt — `user-prompt-submit.py` fires (live test) | [x] | "UserPromptSubmit hook success" confirmed |
| D.5 | Get a response — `stop.py` fires (live test) | [x] | Session a376ea56 created with 53 transcripts |
| D.6 | All 4 hooks verified live | [x] | |
| D.7 | Re-run `brain_health.py` — hooks check must now PASS (9/9) | [x] | 8/9 PASS, hooks 4/4 PASS. 1 WARN = embeddings 52% (pre-existing) |
| **LOCKED** | | | [x] |

**If any hook fails:** Change that one line in settings.json back to `.sh`. Fix the `.py` bug. Re-test. Try again.

---

## PHASE E: UPDATE DOCUMENTATION

Only after Phase D is LOCKED (all hooks live and verified).

| # | File | Status |
|---|------|--------|
| E.1 | `README.md` | [x] |
| E.2 | `CLAUDE_BRAIN_HOW_TO.md` | [x] |
| E.3 | `ARCHITECTURE.md` | [x] |
| E.4 | `FOLDER_SCHEMA.md` | [x] |
| E.5 | `POST_MVP_ROADMAP.md` | [x] |
| E.6 | `verification/TEST_SPECIFICATIONS.md` | [x] |
| E.7 | `verification/SCRIPT_CONTRACTS.md` | [x] |
| E.8 | `NEXT_SESSION_START_PROMPT.txt` | [x] |
| E.9 | `BRAIN_BRAINSTORMING_IDEAS.md` | [x] |
| E.10 | Audit: grep entire repo for `.sh` — clean. Remaining refs in: migration doc (expected), PROJECT_TRACKER (historical), MVP_PLAN (versioned/frozen), config.yaml fixed | [x] |
| **LOCKED** | | [x] |

---

## PHASE F: CLEANUP AND MERGE

| # | Step | Status | Notes |
|---|------|--------|-------|
| F.1 | Delete `hooks/session-start.sh` | [x] | Deleted |
| F.2 | Delete `hooks/user-prompt-submit.sh` | [x] | Deleted |
| F.3 | Delete `hooks/stop.sh` | [x] | Deleted |
| F.4 | Delete `hooks/session-end.sh` | [x] | Deleted |
| F.5 | Delete `scripts/brain_sync.sh` | [x] | Deleted |
| F.6 | Full lifecycle test (start → prompt → response → end) | [x] | 4/4 hooks verified live. stop.py: 30 transcripts in DB. session-end.py: exit 0. brain_health: 8/9→9/9 PASS |
| F.7 | Commit all changes on migration branch | [x] | 68de212 — 19 files changed, 109 insertions, 591 deletions |
| F.8 | Merge `migration/bash-to-python` → `main` | [x] | 31efb0a — clean merge, zero conflicts |
| F.9 | Push to GitHub | [x] | e9bf822..31efb0a main → main |
| F.10 | Verify `main-backup-pre-migration` branch exists on GitHub as rollback | [x] | Pushed to origin. All .sh files + config.yaml + settings.json.backup preserved |
| **DONE** | | | [x] |

---

## SESSION BOUNDARY NOTES

If the session ends at any point, the next session:
1. Reads this document
2. Finds the first unchecked `[ ]` box
3. Picks up from there
4. No context lost

---

## DECISION LOG

| # | Decision | Date |
|---|----------|------|
| 103 | Bash-to-Python migration uses git branches for full backup. main-backup-pre-migration includes gitignored files. Work on migration/bash-to-python branch. One file at a time: write, test, compare, audit, lock. | 2026-03-09 |
| 104 | Migration Phase F complete: 5 .sh files deleted, lifecycle tested (4/4 hooks live, brain_health 9/9), committed (68de212), merged to main (31efb0a), pushed to GitHub. Backup branch on GitHub with full .sh rollback. Embeddings backfilled to 100% (batch_embed.py, 2555 records, 9.4s). | 2026-03-09 |
