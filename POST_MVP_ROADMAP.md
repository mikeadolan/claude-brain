# POST-MVP ROADMAP — claude-brain

Everything deferred, pushed, or identified as "after v0.1" across all sessions,
decisions, and documentation. Compiled from the brain database, MVP plan,
tracker, HOW_TO, and DEPENDENCIES.md.

---

## 1. REMAINING MVP STEPS

| Step | Description | Status | Blocker |
|------|------------|--------|---------|
| 7.8 | Beta tester onboarding — friend clones, runs setup, tests on Mac | Not started | Waiting on friend's GitHub username |
| 7.9 | Document known limitations and post-MVP roadmap | **Done** | — |
| 6.7 | Laptop switch test (second Fedora laptop via Dropbox) | Deferred | Second laptop not set up |

---

## 2. DEFERRED SLASH COMMANDS (Decisions 54, 94)

Do NOT build in v0.1. Added to PROJECT_TRACKER.md.

| Command | Description | Status |
|---------|------------|--------|
| `/brain-forget` | Delete specific records from database | Deferred — too dangerous for v0.1. Needs confirmation dialogs and undo capability. |
| `/brain-tag` | Tag management for conversations | Deferred — Decision 54, not needed for core functionality. |
| `/brain-sync` | Manual sync trigger | Deferred — hooks handle sync automatically. Terminal command `brain_sync.sh` already exists. |
| ~~`/brain-doctor`~~ | ~~Full health check~~ | **DONE** — Renamed to `/brain-health` (Decision 100). 9-point diagnostic. scripts/brain_health.py. |

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

## 4. KNOWN LIMITATIONS

### Platform & Runtime

| Limitation | Detail | Post-MVP Fix |
|-----------|--------|-------------|
| **Python 3.13+ only** | Tested on 3.13 and 3.14. Python 3.12 and below are untested — may work but not guaranteed. sentence-transformers and numpy both require recent versions. | Expand testing to 3.10+ and document minimum. |
| **Single-user design** | No multi-user support. One person, one database. No authentication, no user accounts, no permissions. | Not planned — this is a personal memory tool. |
| **Fedora + macOS only** | Tested on Fedora 43. macOS support via brain-setup.py (untested until beta). Windows not supported. | Decision 52: multi-OS is post-MVP. |

### Search & Performance

| Limitation | Detail | Post-MVP Fix |
|-----------|--------|-------------|
| **Semantic search cold-start ~4-5s** | First query loads the all-MiniLM-L6-v2 model into memory (~80MB). Subsequent queries are fast (<100ms). | Accept as tradeoff. Model stays loaded for session duration. |
| **FTS5 search only (no fuzzy match)** | Keyword search uses SQLite FTS5 — exact token matching with OR logic. Typos like "sesion" won't match "session". No did-you-mean. | Post-MVP: add fuzzy matching layer or Levenshtein distance fallback. |
| **No cross-machine real-time sync** | DB is local. Dropbox syncs project files but not the database. | Move DB to Dropbox, or build a sync script. |

### Data Capture

| Limitation | Detail | Post-MVP Fix |
|-----------|--------|-------------|
| **No auto-capture from claude.ai** | Claude.ai has no hook system. Manual export via Chrome extension + `/brain-import`. | Blocked on claude.ai adding hook/API support. |
| **Summaries require normal exit** | session-end hook only fires on clean exit (`/exit` or terminal close). If Claude Code crashes, summary is lost (but exchanges are saved by stop hook). | Accept as tradeoff — exchanges capture the important data. |
| **No automatic fact extraction** | brain_facts populated manually from questionnaire. | Auto-extract facts from conversations. |

### Feature Gaps

| Limitation | Detail | Post-MVP Fix |
|-----------|--------|-------------|
| **No web UI** | CLI-only via Claude Code. | Post-MVP consideration. |
| **No lessons learned extractor** | No tool to aggregate patterns across sessions. | Build tool that finds "mistake"/"redo"/"should have" patterns. |
| **No session narrative generation** | LLM summaries are structured (topic, counts, decisions). No story-like narrative of what happened. | Post-MVP: richer narrative summaries. |

---

## 5. OPEN SOURCE PACKAGING

Already on GitHub (PRIVATE, Decision 96). Some packaging items remain:

| Item | Purpose | Status |
|------|---------|--------|
| `requirements.txt` | `pip install -r requirements.txt` for users | Not created |
| `requirements-semantic.txt` | Optional semantic search deps | Not created |
| `setup.py` or `pyproject.toml` | Package metadata for distribution | Not created |
| ~~README.md~~ | ~~GitHub landing page~~ | **DONE** (Step 7.5) |
| ~~LICENSE~~ | ~~MIT license~~ | **DONE** (Step 7.7) |
| ~~.gitignore~~ | ~~Exclude DB, local files, logs~~ | **DONE** (Step 0.6, expanded in 7.6) |
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
| ~~LLM-powered summaries~~ | ~~Replace pure-Python summary generator~~ | **DONE** — Direct API call to OpenRouter/Anthropic (Decision 99), bypasses claude -p hang. Pure Python fallback if no key. |
| ~~MEMORY.md trimming~~ | ~~Move stable info to DB to save context tokens~~ | **DONE** — Stable info moved to DB + ARCHITECTURE.md + SESSION_PROTOCOLS.md. session-history.md retired (Decision 102). |
| Session narratives | Richer session summaries that read like a story of what happened | LLM summaries are a step toward this. Post-MVP. |
| Token optimization | Hook output and context injection could be further optimized | Post-MVP. |

---

## 8. DECISION LOG (deferred-related decisions, for reference)

- **Decision 52:** Scope = Fedora + Dropbox only
- **Decision 53:** Multi-OS + provider-agnostic + open-source polish = post-MVP
- **Decision 54:** brain-tags + brain-doctor = post-MVP
- **Decision 55:** brain-setup wizard deferred (REVERSED — built in Step 7.4)
- **Decision 56:** Y/F/R verification deferred
- **Decision 81:** LLM summaries blocked (claude -p hangs). **RESOLVED** by Decision 99 (direct API call).
- **Decision 85:** Phase 7 rewritten, brain-setup moved IN to MVP (un-deferring Decision 55)
- **Decision 89:** ChromaDB replaced with SQLite+numpy (**RESOLVED** the Python 3.14 blocker)
- **Decision 96:** Repo starts PRIVATE for beta testing
- **Decision 99:** LLM summaries via direct API call to OpenRouter/Anthropic. Pure Python fallback.
- **Decision 100:** /brain-doctor renamed to /brain-health. **DONE.**
- **Decision 102:** session-history.md retired. Brain DB replaces it.

---

## PRIORITY SUGGESTION

If Mike wants to tackle these post-MVP, here's a rough grouping:

**Quick wins (hours):**
- `requirements.txt` + `requirements-semantic.txt` — simple file creation
- Token optimization — reduce hook output size

**Medium effort (1-2 sessions):**
- `/brain-forget` — needs careful UX (confirmation + undo)
- `/brain-tag` — tag management
- Automatic fact extraction from conversations
- Cross-machine DB sync (move DB to Dropbox or build sync script)
- Fuzzy search fallback (typo-tolerant matching)

**Larger projects (multi-session):**
- Lessons learned extractor (pattern mining across sessions)
- Session narratives (story-like summaries beyond structured LLM output)
- Multi-OS support (Windows paths, package managers)
- Public release + packaging
