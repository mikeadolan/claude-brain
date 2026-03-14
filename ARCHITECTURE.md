# CLAUDE-BRAIN ARCHITECTURE

Quick reference for how scripts, hooks, MCP, and the database connect.
Source of truth for the dependency chain. See CLAUDE_BRAIN_MVP_PLAN.txt for full specs.

---

## DATABASE (11 tables)

| Table | Purpose |
|-------|---------|
| sys_sessions | One row per session (session_id PK, project, source, quality_score, tags, notes) |
| sys_ingest_log | Tracks imported files, prevents re-import (file_path PK) |
| project_registry | Maps folders to prefixes (8 projects). Columns: folder_name PK, prefix UNIQUE, label, summary, status, health |
| transcripts | Every message, every session (uuid UNIQUE, FTS5 on content, source field for platform tracking) |
| transcripts_fts | FTS5 virtual table on transcripts.content |
| transcript_embeddings | Semantic search vectors (transcript_id PK, embedding BLOB, 384-dim) |
| tool_results | Tool call outputs from .txt files (tool_use_id, content) |
| brain_facts | Everything about Mike, cross-project (category, key, value) |
| brain_preferences | How Mike works (category, preference) |
| decisions | Locked decisions per project (decision_number, description, rationale) |
| facts | Project-specific facts (project, category, key, value) |

---

## 8 PROJECTS

| Prefix | Project | Description |
|--------|---------|-------------|
| jg | johnny-goods | Memoir execution |
| jga | johnny-goods-assistant | Memoir planning |
| gen | general | General conversations |
| mb | mike-brain | Brain development |
| js | job-search | Job search |
| lt | leg-therapy | Leg therapy |
| mp | music-project | Music auto play site |
| oth | other | Uncategorized, default fallback |

---

## 4 DATA SOURCES

| Source | How | Tag on transcripts |
|--------|-----|-------------------|
| Claude Code | Automatic (hooks) | `claude_code` |
| Claude.ai | Manual JSON export + /brain-import | `claude_ai` |
| ChatGPT | Full data export + import_chatgpt.py | `chatgpt` |
| Gemini | Google Takeout HTML + import_gemini.py | `gemini` |

---

## SCRIPT/HOOK DEPENDENCY CHAIN

```
config.yaml
 ├─ ingest_jsonl.py ← startup_check.py ← session-start.py (hook)
 ├─ write_exchange.py ← stop.py (hook)
 ├─ brain_sync.py ← session-end.py (hook, detached) + startup_check.py
 ├─ import_claude_ai.py (standalone, /brain-import)
 ├─ import_chatgpt.py (standalone, scan → xlsx → import)
 ├─ import_gemini.py (standalone, scan → xlsx → import)
 ├─ status.py ← MCP get_status() + /brain-status
 ├─ copy_chat_file.py (standalone, called by Claude via CLAUDE.md)
 ├─ brain_query.py ← /brain-question
 ├─ brain_search.py ← /brain-search
 ├─ brain_history.py ← /brain-history
 ├─ brain_recap.py ← /brain-recap
 ├─ brain_decide.py ← /brain-decide
 ├─ brain_export.py ← /brain-export
 ├─ brain_health.py ← /brain-health
 ├─ brain_digest.py ← cron (email digests)
 ├─ brain_tag_review.py ← /brain-tag-review
 ├─ brain_topics.py ← /brain-topics
 ├─ fuzzy_search.py (shared module for typo correction)
 ├─ batch_embed.py (standalone, backfill embeddings)
 ├─ clean_transcripts.py (standalone, transcript typo cleanup)
 ├─ write_session_notes.py ← end-session protocol
 ├─ write_project_summary.py ← end-session protocol
 ├─ impact_check.py (standalone, pre-change analysis)
 ├─ add-project.py (standalone, add new project)
 ├─ build_competitive_analysis_docx.py (standalone, DOCX report)
 ├─ brain-setup.py (standalone, first-run installer)
 └─ mcp/server.py (standalone, 11 read-only tools)
 user-prompt-submit.py (hook) reads DB directly (FTS5 + GO check + frustration detector)
```

---

## KEY PATHS

| What | Path |
|------|------|
| ROOT | ~/Dropbox/claude-brain (or wherever you cloned the repo) |
| DB | ~/claude-brain-local/claude-brain.db (local disk, not synced) |
| Config | {ROOT}/config.yaml |
| Scripts | {ROOT}/scripts/ (28 scripts) |
| Hooks | {ROOT}/hooks/ (4 hooks) |
| MCP | {ROOT}/mcp/server.py (11 tools) |
| Slash commands | ~/.claude/commands/ (13 commands) |
| Skills | ~/.claude/skills/ (10 JG skills + 4 office skills) |
| Tests | {ROOT}/verification/ |

---

## SEMANTIC SEARCH

- SQLite+numpy (Decision 89, replaced ChromaDB)
- sentence-transformers generates 384-dim embeddings; numpy does cosine similarity
- write_exchange.py embeds on every new message
- batch_embed.py backfills for imported data
- MCP search_semantic() queries embeddings
- Hook is FTS5-only (model load too slow); semantic available via MCP on demand

---

## ENVIRONMENT

- Fedora 43, Python 3.14.3, pip 25.1.1
- SQLite 3.50.2 (library), sqlite3 CLI not installed
- Claude Code 2.1.75, Opus 4.6, 1M context (Anthropic Max)
- git 2.53.0, gh CLI 2.87.0 (authenticated via PAT)
- PyYAML 6.0.2, mcp 1.26.0
- Dropbox syncing between laptops
- GitHub: mikeadolan/claude-brain (PRIVATE)
- Native status line: context %, 5hr rate limit %, weekly rate limit %

---

## WHERE TO FIND WHAT (routing table)

| Question | Go Here |
|----------|---------|
| What step are we on? | PROJECT_TRACKER.md |
| Master project plan | CLAUDE_BRAIN_MVP_PLAN.txt |
| Build-phase decisions 77+ | PROJECT_TRACKER.md → BUILD-PHASE DECISIONS |
| Script interfaces, args, DB writes | verification/SCRIPT_CONTRACTS.md |
| Where files live on disk | FOLDER_SCHEMA.md |
| Config values (paths, mappings) | config.yaml |
| Marketing and launch plan | LAUNCH_PLAN.md |
| Johnny Goods workflow | johnny-goods/CLAUDE.md + STEP_NUMBERS.txt |
