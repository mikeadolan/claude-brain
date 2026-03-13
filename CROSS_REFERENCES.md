# CROSS-REFERENCES -- Impact Map for Code Changes

**Created:** 2026-03-13
**Last Updated:** 2026-03-13
**Purpose:** Before changing ANY component, look it up here to see every file affected.
**Validation:** Run `python3 scripts/impact_check.py "term1" "term2"` to verify at runtime.

---

## HOW TO USE THIS DOCUMENT

1. **Before a change:** Find the component below. Note every file listed.
2. **Run impact_check.py** with the relevant search terms to get the current, live list.
3. **Make the change** across ALL listed files.
4. **Run impact_check.py again** with the OLD terms to confirm zero stale references.
5. **py_compile** all modified .py files.

---

## MCP SERVER (mcp/server.py)

Search terms: `"brain-server" "mcp/server" "FastMCP" "mcpServers"`

| Category | Files |
|----------|-------|
| Code | mcp/server.py, scripts/brain-setup.py (registration), scripts/brain_health.py (health check), scripts/startup_check.py (folder check), scripts/fuzzy_search.py (comment) |
| Config | requirements.txt, ~/.claude.json (project entries) |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md (Section 4), ARCHITECTURE.md, CHANGELOG.md, FEATURE_PLAN.md, FOLDER_SCHEMA.md, NEXT_SESSION_START_PROMPT.txt, PROJECT_TRACKER.md |
| Routing | CLAUDE.md, CLAUDE.md.example, general/CLAUDE.md, job-search/CLAUDE.md, johnny-goods/CLAUDE.md, johnny-goods-assistant/CLAUDE.md, leg-therapy/CLAUDE.md, other/CLAUDE.md |
| Tests | verification/SCRIPT_CONTRACTS.md, verification/TEST_SPECIFICATIONS.md |
| External | ~/.claude.json (mcpServers entries per project) |

---

## HOOKS (hooks/)

Search terms: `"session-start" "session-end" "user-prompt-submit" "stop.py"`

| Category | Files |
|----------|-------|
| Code | hooks/session-start.py, hooks/user-prompt-submit.py, hooks/stop.py, hooks/session-end.py, scripts/write_exchange.py (called by stop), scripts/brain_sync.py (called by session-end) |
| Config | ~/.claude/settings.json (hook registration) |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md, ARCHITECTURE.md, SESSION_PROTOCOLS.md, NEXT_SESSION_START_PROMPT.txt, FOLDER_SCHEMA.md, MIGRATION_BASH_TO_PYTHON.md, PROJECT_TRACKER.md |
| Tests | verification/SCRIPT_CONTRACTS.md, verification/TEST_SPECIFICATIONS.md |

---

## SESSION NOTES (sys_sessions.notes)

Search terms: `"write_session_notes" "sys_sessions" ".notes"`

| Category | Files |
|----------|-------|
| Code | scripts/write_session_notes.py, scripts/brain_digest.py, scripts/brain_query.py, scripts/brain_search.py, mcp/server.py (get_recent_summaries, search_transcripts), hooks/session-start.py (gap detection) |
| Config | CLAUDE.md (end-session protocol), CLAUDE.md.example |
| Docs | SESSION_PROTOCOLS.md, ARCHITECTURE_MERGE_PLAN.md, PROJECT_TRACKER.md |

---

## PROJECT SUMMARIES (project_registry.summary)

Search terms: `"write_project_summary" "project_registry" "project_summary"`

| Category | Files |
|----------|-------|
| Code | scripts/write_project_summary.py, mcp/server.py (get_project_state), hooks/session-start.py (injects summary), scripts/brain_digest.py (project deep dive) |
| Config | CLAUDE.md (end-session protocol) |
| Docs | SESSION_PROTOCOLS.md, ARCHITECTURE_MERGE_PLAN.md |

---

## EMAIL DIGESTS (scripts/brain_digest.py)

Search terms: `"brain_digest" "brain-digest" "digest"`

| Category | Files |
|----------|-------|
| Code | scripts/brain_digest.py |
| Config | config.yaml.example (email section, dark_mode) |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md (Section 8.5), CHANGELOG.md, FEATURE_PLAN.md, FOLDER_SCHEMA.md, ARCHITECTURE_MERGE_PLAN.md, DEPENDENCIES.md |

---

## SEARCH (FTS5 + Semantic + Fuzzy)

Search terms: `"brain_query" "brain_search" "fuzzy_search" "search_transcripts" "search_semantic" "transcripts_fts"`

| Category | Files |
|----------|-------|
| Code | scripts/brain_query.py, scripts/brain_search.py, scripts/fuzzy_search.py, scripts/clean_transcripts.py, scripts/batch_embed.py, mcp/server.py, hooks/user-prompt-submit.py |
| Config | commands/brain-question.md, commands/brain-search.md |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md, FEATURE_PLAN.md, CHANGELOG.md, FOLDER_SCHEMA.md, PROJECT_TRACKER.md |
| Tests | verification/SCRIPT_CONTRACTS.md, verification/TEST_SPECIFICATIONS.md |

---

## HEALTH CHECK (scripts/brain_health.py)

Search terms: `"brain_health" "brain-health"`

| Category | Files |
|----------|-------|
| Code | scripts/brain_health.py, scripts/brain-setup.py (calls health at end) |
| Config | commands/brain-health.md |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md, CHANGELOG.md, FEATURE_PLAN.md, PROJECT_TRACKER.md, NEXT_SESSION_START_PROMPT.txt, MIGRATION_BASH_TO_PYTHON.md, POST_MVP_ROADMAP.md |

---

## SETUP INSTALLER (scripts/brain-setup.py)

Search terms: `"brain-setup" "brain_setup"`

| Category | Files |
|----------|-------|
| Code | scripts/brain-setup.py |
| Config | commands/brain-setup.md |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md, PROJECT_TRACKER.md, FOLDER_SCHEMA.md, CHANGELOG.md |

---

## INGESTION (scripts/ingest_jsonl.py, write_exchange.py)

Search terms: `"ingest_jsonl" "write_exchange"`

| Category | Files |
|----------|-------|
| Code | scripts/ingest_jsonl.py, scripts/write_exchange.py, scripts/startup_check.py (imports ingest_jsonl), hooks/stop.py (calls write_exchange) |
| Docs | PROJECT_TRACKER.md, FOLDER_SCHEMA.md, ARCHITECTURE.md, CLAUDE_BRAIN_MVP_PLAN.txt |
| Tests | verification/SCRIPT_CONTRACTS.md, verification/TEST_SPECIFICATIONS.md |

---

## CONFIG (config.yaml)

Search terms: `"config.yaml" "config_yaml" "load_config"`

| Category | Files |
|----------|-------|
| Code | Nearly all scripts load config.yaml -- brain_digest.py, brain_health.py, brain_query.py, brain_search.py, brain-setup.py, ingest_jsonl.py, write_exchange.py, startup_check.py, mcp/server.py, hooks/* |
| Config | config.yaml.example, CLAUDE.md.example |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md, ARCHITECTURE.md, DEPENDENCIES.md |
| Tests | verification/SCRIPT_CONTRACTS.md |
| Note | **config.yaml is gitignored. config.yaml.example is in repo.** Any config key change must update BOTH. |

---

## DATABASE TABLES

Search terms: `"sys_sessions" "transcripts" "project_registry" "transcript_embeddings" "brain_facts" "brain_preferences" "decisions"`

| Category | Files |
|----------|-------|
| Code | Nearly all scripts query the DB. Key files: mcp/server.py (all tables), scripts/brain-setup.py (DDL), scripts/brain_health.py (integrity checks), scripts/write_exchange.py, scripts/ingest_jsonl.py |
| Docs | ARCHITECTURE.md (schema), DATABASE_INFO.txt |
| Tests | verification/TEST_SPECIFICATIONS.md, verification/AUDIT_REPORT_2026-03-03_phase1_database.txt |
| Note | **Schema changes require updating: brain-setup.py DDL, ARCHITECTURE.md schema section, and running ALTER TABLE on live DB.** |

---

## SLASH COMMANDS (commands/)

Search terms: `"brain-status" "brain-search" "brain-question" "brain-decide" "brain-recap" "brain-history" "brain-export" "brain-import" "brain-setup" "brain-questionnaire" "brain-health"`

| Category | Files |
|----------|-------|
| Code | commands/*.md (11 command files), scripts/* (each command calls a script) |
| Docs | README.md, CLAUDE_BRAIN_HOW_TO.md (Section 3) |
| Note | **Adding/removing a command requires updating README (count + table) and HOW_TO (section 3).** |

---

## ROUTING (CLAUDE.md files)

Search terms: `"CLAUDE.md" "TOOL ROUTING" "brain MCP" "search_transcripts" "lookup_decision"`

| Category | Files |
|----------|-------|
| Files | CLAUDE.md (root), CLAUDE.md.example, general/CLAUDE.md, job-search/CLAUDE.md, johnny-goods/CLAUDE.md, johnny-goods-assistant/CLAUDE.md, leg-therapy/CLAUDE.md, other/CLAUDE.md |
| Note | **All project CLAUDE.md files share the same brain routing template. Change one, change all.** |

---

## UPDATE LOG

| Date | What Changed |
|------|-------------|
| 2026-03-13 | Initial creation. All major components audited via impact_check.py. |
