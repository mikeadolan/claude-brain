# POST-MVP ROADMAP — claude-brain

Everything deferred, pushed, or identified as "after v0.1" across all sessions,
decisions, and documentation. Compiled from the brain database, MVP plan,
tracker, HOW_TO, and DEPENDENCIES.md.

---

## 1. REMAINING MVP STEPS (not yet done)

| Step | Description | Status | Blocker |
|------|------------|--------|---------|
| 7.8 | Beta tester onboarding — friend clones, runs setup, tests on Mac | Not started | Waiting on friend's GitHub username |
| 7.9 | Document known limitations and post-MVP roadmap | Not started | None |
| 6.7 | Laptop switch test (second Fedora laptop via Dropbox) | Deferred | Second laptop not set up |

---

## 2. DEFERRED SLASH COMMANDS (Decisions 54, 94)

Do NOT build in v0.1. Added to PROJECT_TRACKER.md.

| Command | Description | Why Deferred |
|---------|------------|-------------|
| `/brain-forget` | Delete specific records from database | Too dangerous for v0.1. Needs confirmation dialogs and undo capability. |
| `/brain-tag` | Tag management for conversations | Decision 54 — not needed for core functionality. |
| `/brain-sync` | Manual sync trigger | Hooks handle sync automatically. Terminal command `brain_sync.sh` already exists. |
| `/brain-doctor` | Full health check (deps, folders, DB, MCP, aliases) | Diagnostic tool — nice to have, not critical. |

---

## 3. DEFERRED FEATURES — FROM LOCKED DECISIONS

| Decision | What Was Deferred | Rationale |
|----------|------------------|-----------|
| 52 | Multi-OS support (macOS, Windows) | MVP is Fedora-only. Polish comes later. |
| 53 | Provider-agnostic storage (iCloud, OneDrive, etc.) | MVP is Dropbox-only. |
| 53 | Open-source packaging polish | MVP works; packaging is cosmetic. |
| 54 | brain-tags management | Not needed for core functionality. |
| 54 | brain-doctor health check | Not needed for core functionality. |
| 56 | Y/F/R verification of questionnaire answers | Mike answered directly; formal verification not needed. |
| ~~81~~ | ~~LLM-generated session summaries (Claude Haiku)~~ | **RESOLVED** — Direct API call to OpenRouter/Anthropic bypasses `claude -p` hang entirely. Config.yaml stores API key. Pure Python fallback for users without a key. |

---

## 4. KNOWN LIMITATIONS (from HOW_TO Section 12)

| Limitation | Current State | Post-MVP Fix |
|-----------|--------------|-------------|
| No auto-capture from claude.ai | Manual export via Chrome extension + `/brain-import` | Blocked on claude.ai adding hook/API support |
| No cross-machine real-time sync | DB is local; Dropbox syncs project files but not the DB | Move DB to Dropbox, or build a sync script |
| Summaries require normal exit | session-end hook only fires on clean exit (`/exit` or terminal close) | If Claude Code crashes mid-session, summary is lost (exchanges are saved by stop hook) |
| No web UI | CLI-only via Claude Code | Post-MVP consideration |
| No automatic fact extraction | brain_facts manually populated from questionnaire | Auto-extract facts from conversations |
| No lessons learned extractor | No tool to aggregate patterns | Build tool that finds "mistake"/"redo"/"should have" patterns across sessions |

---

## 5. OPEN SOURCE PACKAGING (from DEPENDENCIES.md)

Already on GitHub (PRIVATE). These packaging items remain:

| Item | Purpose | Status |
|------|---------|--------|
| `requirements.txt` | `pip install -r requirements.txt` for users | Not created |
| `requirements-semantic.txt` | Optional semantic search deps | Not created |
| `setup.py` or `pyproject.toml` | Package metadata for distribution | Not created |
| Repo visibility: PUBLIC | Switch from PRIVATE to PUBLIC | Blocked on beta testing (Decision 96) |

---

## 6. OPEN ITEMS

| # | Item | Status |
|---|------|--------|
| O.4 | OpenRouter — verify works in Claude Code on Fedora | Open (Mike's homework) |

---

## 7. ARCHITECTURAL IMPROVEMENTS (identified in conversations)

| Item | Description | Source |
|------|------------|--------|
| ~~Progressive retrieval layers (L1/L2/L3)~~ | ~~Formalize the retrieval hierarchy~~ | **DONE** — L1 structured tables, L2 FTS5, L3 semantic. Already built, just was unlabeled. |
| ~~Forked subagent for memory recall~~ | ~~Dedicated subagent for memory ops~~ | **DONE** — Solved by Decision 94 (local script replaces subagent). |
| ~~LLM-powered summaries~~ | ~~Replace pure-Python summary generator~~ | **DONE** — Direct API call to OpenRouter/Anthropic, bypasses claude -p hang. Pure Python fallback if no key. |
| ~~MEMORY.md trimming~~ | ~~Move stable info to DB to save context tokens~~ | **IN PROGRESS** — Data moved to DB + ARCHITECTURE.md + SESSION_PROTOCOLS.md. Trim pending. |
| Session narratives | Richer session summaries that read like a story of what happened | Referenced in MEMORY.md. LLM summaries are a step toward this. |
| Token optimization | Hook output and context injection could be further optimized | Discussed in session (3/8) |

---

## 8. DECISION LOG (deferred-related decisions, for reference)

- **Decision 52:** Scope = Fedora + Dropbox only
- **Decision 53:** Multi-OS + provider-agnostic + open-source polish = post-MVP
- **Decision 54:** brain-tags + brain-doctor = post-MVP
- **Decision 55:** brain-setup wizard deferred (REVERSED — built in Step 7.4)
- **Decision 56:** Y/F/R verification deferred
- **Decision 81:** LLM summaries blocked (claude -p hangs). Pure Python fallback.
- **Decision 85:** Phase 7 rewritten, brain-setup moved IN to MVP (un-deferring Decision 55)
- **Decision 89:** ChromaDB replaced with SQLite+numpy (RESOLVED the Python 3.14 blocker)
- **Decision 96:** Repo starts PRIVATE for beta testing

---

## PRIORITY SUGGESTION

If Mike wants to tackle these post-MVP, here's a rough grouping:

**Quick wins (hours):**
- `/brain-doctor` — health check, high value, low risk
- `requirements.txt` + `requirements-semantic.txt` — simple file creation
- MEMORY.md trimming — move stable info to DB, save context tokens

**Medium effort (1-2 sessions):**
- `/brain-forget` — needs careful UX (confirmation + undo)
- `/brain-tag` — tag management
- Automatic fact extraction from conversations
- Cross-machine DB sync

**Larger projects (multi-session):**
- Lessons learned extractor (pattern mining across sessions)
- LLM-powered summaries (blocked on Claude Code supporting nested sessions)
- Multi-OS support (macOS, Windows paths, package managers)
- Public release + packaging
