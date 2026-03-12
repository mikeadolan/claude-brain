# CLAUDE-BRAIN ARCHITECTURE

Quick reference for how scripts, hooks, MCP, and the database connect.
Source of truth for the dependency chain. See CLAUDE_BRAIN_MVP_PLAN.txt for full specs.

---

## DATABASE (10 tables)

| Table | Purpose |
|-------|---------|
| sys_sessions | One row per Claude Code session (session_id PK, project, started_at, model, source, quality_score, quality_tags) |
| sys_ingest_log | Tracks imported files, prevents re-import (file_path PK) |
| project_registry | Maps folders to prefixes (7 projects seeded). Columns: folder_name PK, prefix UNIQUE, label, registered_at, summary, summary_updated_at, status DEFAULT 'active', health DEFAULT 'green' |
| transcripts | Every message, every session (uuid UNIQUE, FTS5 on content, 18 columns) |
| transcripts_fts | FTS5 virtual table on transcripts.content |
| tool_results | Tool call outputs from .txt files (tool_use_id, content) |
| brain_facts | Everything about Mike, cross-project (category, key, value) |
| brain_preferences | How Mike works (category, preference) |
| decisions | Locked decisions per project (decision_number, description, rationale) |
| facts | Project-specific facts (project, category, key, value) |
| transcript_embeddings | Semantic search vectors (transcript_id PK, embedding BLOB, model, created_at) |

---

## 7 PROJECTS

| Prefix | Project | Description |
|--------|---------|-------------|
| jg | johnny-goods | Memoir execution (OpenRouter 1M) |
| jga | johnny-goods-assistant | Memoir planning (Claude Max) |
| gen | general | General conversations |
| mb | mike-brain | Brain development |
| js | job-search | Job search |
| lt | leg-therapy | Leg therapy |
| oth | other | Uncategorized, default fallback |

---

## SCRIPT/HOOK DEPENDENCY CHAIN

```
config.yaml
 ├─ ingest_jsonl.py ← startup_check.py ← session-start.py (hook)
 ├─ write_exchange.py ← stop.py (hook)
 ├─ brain_sync.py ← session-end.py (hook, detached) + startup_check.py
 ├─ import_claude_ai.py (standalone, user runs manually)
 ├─ status.py ← MCP get_status() + user manual
 ├─ copy_chat_file.py (standalone, called by Claude via CLAUDE.md)
 ├─ brain_search.py ← /brain-search slash command
 ├─ brain_history.py ← /brain-history slash command
 ├─ brain_recap.py ← /brain-recap slash command
 ├─ brain_decide.py ← /brain-decide slash command
 ├─ brain_export.py ← /brain-export slash command
 └─ mcp/server.py (standalone, 10 read-only functions)
 user-prompt-submit.py (hook) reads DB directly (FTS5 only, semantic via MCP)
```

---

## KEY PATHS

| What | Path |
|------|------|
| ROOT | ~/Dropbox/claude-brain (or wherever you cloned the repo) |
| DB | ~/claude-brain-local/claude-brain.db (local disk, not synced) |
| Config | {ROOT}/config.yaml |
| Scripts | {ROOT}/scripts/ (15 scripts) |
| Hooks | {ROOT}/hooks/ (4 hooks) |
| MCP | {ROOT}/mcp/server.py (11 tools) |
| Tests | {ROOT}/verification/ |
| Fixtures | {ROOT}/verification/fixtures/ |

---

## SEMANTIC SEARCH

- ChromaDB fully replaced with SQLite+numpy (Decision 89)
- sentence-transformers generates 384-dim embeddings; numpy does cosine similarity
- write_exchange.py embeds on every new message
- MCP search_semantic() queries embeddings
- Hook is FTS5-only (model load too slow); semantic available via MCP on demand

---

## ENVIRONMENT

- Fedora 43, Python 3.14.3, pip 25.1.1
- SQLite 3.50.2 (library), sqlite3 CLI not installed
- Claude Code 2.1.63
- git 2.53.0, gh CLI 2.87.0 (authenticated via PAT)
- PyYAML 6.0.2, mcp 1.26.0
- Dropbox syncing between laptops
- GitHub: mikeadolan/claude-brain (PRIVATE)

---

## WHERE TO FIND WHAT (routing table)

| Question | Go Here |
|----------|---------|
| What step are we on? | PROJECT_TRACKER.md |
| Master project plan (architecture, schema, all specs) | CLAUDE_BRAIN_MVP_PLAN.txt |
| Locked decisions 52-76 (planning phase) | CLAUDE_BRAIN_MVP_PLAN.txt Section 11 |
| Build-phase decisions 77+ | PROJECT_TRACKER.md → BUILD-PHASE DECISIONS |
| Script interfaces, args, DB writes, exit codes | verification/SCRIPT_CONTRACTS.md |
| Test cases (what to test, expected results) | verification/TEST_SPECIFICATIONS.md |
| JSONL field mapping and content extraction rules | verification/SCRIPT_CONTRACTS.md Section 1 |
| JSONL format examples (real data structure) | memory/jsonl-format.md |
| Where files live on disk | FOLDER_SCHEMA.md |
| What's installed, what's needed, blockers | DEPENDENCIES.md |
| What never goes to GitHub | .gitignore |
| Config values (paths, mappings, features) | config.yaml |
| DB connection info | DATABASE_INFO.txt |
| Audit reports | verification/AUDIT_REPORT_*.txt |
