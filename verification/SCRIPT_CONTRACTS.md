# CLAUDE-BRAIN — SCRIPT CONTRACTS

**Created:** 2026-03-03
**Last Updated:** 2026-03-03
**Purpose:** Define the exact interface for every script, hook, and server.
**Related:** PROJECT_TRACKER.md (build steps), TEST_SPECIFICATIONS.md (test cases)

---

## CONVENTIONS (All Scripts)

### Config Loading
- Every script loads config from: `{ROOT}/config.yaml`
- ROOT is determined by: script's own location → parent directory
  - e.g., `scripts/ingest_jsonl.py` → ROOT = `..`
- Config parsed with PyYAML. Missing keys → script exits with error.

### Database Connection
- Path: read from `config.yaml` → `storage.local_db_path`
- Always use `sqlite3.connect()` with `isolation_level=None` for autocommit
  OR explicit `BEGIN`/`COMMIT` transactions for batch operations.
- WAL mode enabled: `PRAGMA journal_mode=WAL;` on connect.
- Busy timeout: `PRAGMA busy_timeout=5000;` (5 seconds) on connect.

### Timestamps
- All timestamps are ISO 8601 with UTC timezone: `2026-03-03T04:56:08Z`
- Use `datetime.datetime.now(datetime.timezone.utc).isoformat()` for `created_at`
- Preserve original timestamps from JSONL/exports as-is (do not re-format)

### Logging
- Every script logs to: `{ROOT}/logs/{hostname}/{script_name}.log`
- Hostname auto-detected via `socket.gethostname()`
- Format: `{ISO timestamp} [{LEVEL}] {message}`
- Levels: INFO for normal operations, WARNING for skipped items, ERROR for failures
- Also print summary to stdout for human visibility

### Exit Codes
- `0` = success
- `1` = error (logged, recoverable)
- `2` = fatal error (config missing, DB unreachable, unrecoverable)

### Dependencies
- Python 3.14.3, stdlib only + PyYAML + sqlite3
- ChromaDB: **BLOCKED** — incompatible with Python 3.14 (pydantic v1 crash)
  - All semantic search code must be gated behind `try/except ImportError`
  - Scripts must work fully without ChromaDB installed
  - See BLOCKER section at end of this document

---

## 1. ingest_jsonl.py

**Location:** `scripts/ingest_jsonl.py`
**Triggered by:** `startup_check.py` (called as Python module, not subprocess)
**Phase:** 2.1

### Interface

```
Usage:  python3 ingest_jsonl.py <file_path> [--project <prefix>] [--type <file_type>]

Args:
  file_path       Path to JSONL file, or tool-result .txt file
  --project       Project prefix override (default: auto-detect from path/cwd)
  --type          File type: "jsonl" | "subagent" | "tool_result" (default: auto-detect)

Returns:
  Exit code 0 on success, 1 on partial failure, 2 on fatal error

Stdout:
  Summary line: "Ingested {N} records from {file_path} ({M} skipped)"
```

### Auto-Detection Rules

**File type detection:**
- `.jsonl` extension + no `agentId` in first line → type = "jsonl"
- `.jsonl` extension + `agentId` in first line → type = "subagent"
- `.txt` extension + in a `tool-results/` directory → type = "tool_result"

**Project detection (in priority order):**
1. `--project` argument (if given)
2. `jsonl_project_mapping` in config — match folder name from file path (Windows archive)
3. `jsonl_project_mapping` in config — match `cwd` field from first JSONL line (Fedora sessions)
4. Default: `"oth"`

**Mapping match order matters:** For Fedora cwd matching, longer/more-specific paths match first. `johnny-goods-assistant` must match before `johnny-goods`.

### Database Writes

**For JSONL files (type = "jsonl" or "subagent"):**

| Table | Action |
|-------|--------|
| `sys_sessions` | INSERT OR IGNORE. One row per session_id. Fields: session_id (from JSONL), project (detected), started_at (earliest timestamp), model (from first assistant message), source ("jsonl_ingest"), claude_version (from version field), cwd (from cwd field). |
| `transcripts` | INSERT OR IGNORE (dedup on uuid). One row per user/assistant/system message. Skip progress and file-history-snapshot types. Fields mapped from JSONL (see field mapping below). |
| `sys_ingest_log` | INSERT. One row per file. Fields: file_path, file_size, file_type, records_imported, ingested_at. |

**For tool-result files (type = "tool_result"):**

| Table | Action |
|-------|--------|
| `tool_results` | INSERT. Fields: session_id (from parent folder name), project (detected), tool_use_id (filename minus .txt), content (file contents), source_file (full path). |
| `sys_ingest_log` | INSERT. One row. file_type = "tool_result". |

### Field Mapping: JSONL → transcripts

| transcripts column | JSONL source |
|--------------------|-------------|
| session_id | `.sessionId` |
| project | Auto-detected (see rules above) |
| uuid | `.uuid` |
| parent_uuid | `.parentUuid` |
| type | `.type` ("user", "assistant", "system") |
| subtype | `.subtype` (system messages only, else NULL) |
| role | `.message.role` |
| content | `.message.content` — see Content Extraction below |
| model | `.message.model` (assistant only, else NULL) |
| timestamp | `.timestamp` |
| token_input | `.message.usage.input_tokens` (if present, else NULL) |
| token_output | `.message.usage.output_tokens` (if present, else NULL) |
| stop_reason | `.message.stop_reason` (if present, else NULL) |
| is_subagent | 1 if file_type = "subagent", else 0 |
| source_file | Full path to the source file |
| raw_json | The complete original JSON line (unmodified) |
| created_at | Current UTC timestamp |

### Content Extraction Rules

The `message.content` field varies by message type:

| Scenario | content value in JSONL | Stored in transcripts.content |
|----------|----------------------|-------------------------------|
| Simple string | `"content": "hello"` | `"hello"` |
| Text blocks | `"content": [{"type": "text", "text": "hello"}, ...]` | Concatenate all text block `.text` values, joined by `\n` |
| Tool use blocks | `"content": [{"type": "tool_use", ...}]` | Skip tool_use blocks in content. Store only text blocks. |
| Tool result blocks | `"content": [{"type": "tool_result", ...}]` | Skip tool_result blocks in content. Store only text blocks. |
| Thinking blocks | `"content": [{"type": "thinking", ...}]` | Skip thinking/redacted_thinking. Store only text blocks. |
| No text blocks | `"content": [{"type": "tool_use", ...}]` only | content = "" (empty string, NOT null) |
| System (no message) | System messages may have no `.message` field | content = "" |

### Deduplication

- Primary dedup: `uuid` column (UNIQUE constraint in DB)
- File-level dedup: check `sys_ingest_log` for `file_path` before processing
- If file already in ingest log: skip entirely, return 0

### Error Handling

| Error | Behavior |
|-------|----------|
| Malformed JSON line | Log warning with line number. Skip line. Continue. |
| Missing uuid | Log warning. Skip line. Continue. |
| Duplicate uuid (DB constraint) | INSERT OR IGNORE. Silent skip. |
| File not found | Return exit code 1. Log error. |
| DB connection failure | Return exit code 2. Log error. |
| Missing config key | Return exit code 2. Log error. |

---

## 2. startup_check.py

**Location:** `scripts/startup_check.py`
**Triggered by:** `hooks/session-start.sh`
**Phase:** 2.3

### Interface

```
Usage:  python3 startup_check.py

Args:   None (reads everything from config.yaml)

Returns:
  Exit code 0 on success, 1 on warnings, 2 on fatal error

Stdout:
  Multi-line summary:
    "=== Claude Brain Startup Check ==="
    "Source paths scanned: 2"
    "New files found: {N}"
    "Records ingested: {M}"
    "Errors: {E}"
    "Backup: OK ({size})"
    "==================================="
```

### Behavior

1. Load config.yaml
2. Verify required folders exist (ROOT, scripts/, hooks/, mcp/, logs/, db-backup/, verification/)
   - Missing folder → log WARNING, create it, continue
3. Scan each path in `config.jsonl.source_paths`:
   - Find all `.jsonl` files (recursive)
   - Find all `tool-results/*.txt` files (recursive)
   - Check each against `sys_ingest_log`
   - New files → call `ingest_jsonl.ingest()` (Python import, not subprocess)
4. Run database backup (call `brain_sync.sh` or inline backup logic)
5. Print summary to stdout
6. Log to `logs/{hostname}/startup_check.log`

### Scan Logic

```
For each source_path in config.jsonl.source_paths:
  IF path does not exist → log WARNING, skip
  Walk directory tree:
    For each .jsonl file:
      IF file_path NOT in sys_ingest_log → ingest
      Detect subagent: file is in a subagents/ subdirectory
    For each .txt file in tool-results/ subdirectory:
      IF file_path NOT in sys_ingest_log → ingest as tool_result
```

### Database Writes

Delegates to `ingest_jsonl.py`. No direct DB writes except reading `sys_ingest_log`.

---

## 3. write_exchange.py

**Location:** `scripts/write_exchange.py`
**Triggered by:** `hooks/stop.sh`
**Phase:** 2.4

### Interface

```
Usage:  python3 write_exchange.py --session-id <id> --jsonl-path <path>

Args:
  --session-id     Current session UUID
  --jsonl-path     Path to the current session's JSONL file

Returns:
  Exit code 0 on success

Stdout:
  "Wrote {N} new messages for session {session_id}"
```

### Behavior

1. Read the JSONL file
2. Find messages not yet in `transcripts` (by uuid)
3. Insert new user/assistant/system messages into `transcripts`
4. Update or create `sys_sessions` row (message_count, ended_at)
5. If `semantic_search.enabled` and ChromaDB importable:
   - Generate embedding for new text content
   - Store in ChromaDB collection
6. If ChromaDB fails → log warning, continue (non-blocking)

### Database Writes

| Table | Action |
|-------|--------|
| `transcripts` | INSERT OR IGNORE for each new message |
| `sys_sessions` | INSERT OR UPDATE (upsert). Update message_count, ended_at. |

### ChromaDB Write (conditional)

| Store | Action |
|-------|--------|
| ChromaDB collection (`transcripts`) | `collection.add(ids=[uuid], documents=[content], metadatas=[{session_id, project, timestamp}])` |

---

## 4. generate_summary.py

**Location:** `scripts/generate_summary.py`
**Triggered by:** `hooks/session-end.sh`
**Phase:** 2.5

### Interface

```
Usage:  python3 generate_summary.py --session-id <id>

Args:
  --session-id     Session UUID to summarize

Returns:
  Exit code 0 on success, 1 on failure

Stdout:
  "Summary generated for session {session_id} ({N} lines)"
```

### Behavior

1. Query `transcripts` for all rows with session_id, ordered by timestamp
2. If 0 rows → log warning, exit 0 (no summary needed)
3. Build transcript text from content fields
4. Call Claude Haiku for summarization:
   ```
   claude -p --model haiku "Summarize this session in under 50 lines: {transcript}"
   ```
   (subprocess call to `claude` CLI)
5. Validate output ≤ 50 lines. Truncate if exceeded.
6. Write to `sys_session_summaries`

### Database Writes

| Table | Action |
|-------|--------|
| `sys_session_summaries` | INSERT. Fields: session_id, project (from sys_sessions), summary, created_at. |

### Error Handling

| Error | Behavior |
|-------|----------|
| No transcripts for session | Log warning. Exit 0. No summary row. |
| Claude Haiku call fails | Log error. Exit 1. No partial data. |
| Summary > 50 lines | Truncate to 50 lines. Log warning. Still write. |
| Duplicate session_id | Update existing summary (INSERT OR REPLACE). |

---

## 5. import_claude_ai.py

**Location:** `scripts/import_claude_ai.py`
**Triggered by:** User runs manually
**Phase:** 3.1

### Interface

```
Usage:  python3 import_claude_ai.py <json_file> --project <prefix>

Args:
  json_file        Path to claude.ai JSON export
  --project        Project prefix to assign

Returns:
  Exit code 0 on success

Stdout:
  "Imported {N} messages from '{conversation_name}' → project {prefix}"
```

### Behavior

1. Parse JSON file (top-level object, not JSONL)
2. Extract metadata: uuid, name, created_at, model
3. Create `sys_sessions` row:
   - session_id = export uuid
   - source = "claude_ai_import"
   - project = from --project arg
   - started_at = export created_at
4. For each item in `chat_messages`:
   - Map sender "human" → type="user", role="user"
   - Map sender "assistant" → type="assistant", role="assistant"
   - content = `.text` field
   - uuid = `.uuid` from export
   - timestamp = `.created_at`
   - parent_uuid = `.parent_message_uuid`
5. INSERT OR IGNORE into `transcripts` (dedup on uuid)
6. Record in `sys_ingest_log` (file_type = "claude_ai_import")
7. Move file to `imports/completed/`

### Database Writes

| Table | Action |
|-------|--------|
| `sys_sessions` | INSERT. source="claude_ai_import". |
| `transcripts` | INSERT OR IGNORE per message. |
| `sys_ingest_log` | INSERT. file_type="claude_ai_import". |

### Claude.ai Export Field Mapping

| transcripts column | Export source |
|--------------------|-------------|
| session_id | Top-level `.uuid` |
| uuid | `chat_messages[].uuid` |
| parent_uuid | `chat_messages[].parent_message_uuid` |
| type | "human" → "user", "assistant" → "assistant" |
| role | Same mapping as type |
| content | `chat_messages[].text` |
| timestamp | `chat_messages[].created_at` |
| source_file | Path to the JSON file |
| raw_json | `json.dumps()` of the individual chat_message object |
| model | Top-level `.model` (if present) |
| is_subagent | 0 |
| All others | NULL |

---

## 6. brain_sync.sh

**Location:** `scripts/brain_sync.sh`
**Triggered by:** `hooks/session-end.sh` and `startup_check.py`
**Phase:** 3.2

### Interface

```
Usage:  bash brain_sync.sh

Args:   None (reads config.yaml for paths)

Returns:
  Exit code 0 on success, 1 on failure

Stdout:
  "Backup complete: {dest_path} ({size} bytes) at {timestamp}"
```

### Behavior

1. Read DB path from config (or hardcode — it's a bash script)
   - Source: `{local_db_path from config.yaml}`
   - Dest: `{ROOT}/db-backup/`
2. Rotation (max 2 copies):
   - If `claude-brain.db.bak2` exists → delete it
   - If `claude-brain.db.bak1` exists → rename to `.bak2`
   - Copy source → `claude-brain.db.bak1`
3. Verify:
   - Check file size > 0
   - Run `sqlite3 {backup} "PRAGMA integrity_check;"` → must return "ok"
4. Print confirmation
5. Log to `{ROOT}/logs/{hostname}/brain_sync.log`

### File Operations

| Operation | Path |
|-----------|------|
| Read | `{local_db_path from config.yaml}` |
| Delete (if exists) | `{ROOT}/db-backup/claude-brain.db.bak2` |
| Rename (if exists) | `.bak1` → `.bak2` |
| Copy | Source → `{ROOT}/db-backup/claude-brain.db.bak1` |

---

## 7. status.py

**Location:** `scripts/status.py`
**Triggered by:** User manually or MCP `get_status()`
**Phase:** 3.3

### Interface

```
Usage:  python3 status.py [--json]

Args:
  --json           Output as JSON (for MCP) instead of human-readable

Returns:
  Exit code 0 always (informational only)

Stdout (human-readable):
  === Claude Brain Status ===
  Database: {path} ({size} KB)
  Sessions: {N} total
  Messages: {M} total
  By project:
    jg:  {n} sessions, {m} messages, last: {date}
    gen: {n} sessions, {m} messages, last: {date}
    ...
  Last backup: {date} ({size} KB)
  Last ingest: {date} ({files} files)
  Semantic search: {enabled|disabled} ({count} embeddings)
  ===========================

Stdout (--json):
  {"sessions": N, "messages": M, "db_size_kb": S, "projects": {...}, ...}
```

### Database Reads

| Query | Source |
|-------|--------|
| Total sessions | `SELECT COUNT(*) FROM sys_sessions` |
| Total messages | `SELECT COUNT(*) FROM transcripts` |
| Per-project stats | `SELECT project, COUNT(*) FROM sys_sessions GROUP BY project` |
| Last session per project | `SELECT project, MAX(started_at) FROM sys_sessions GROUP BY project` |
| Message count per project | `SELECT project, COUNT(*) FROM transcripts GROUP BY project` |
| Last backup | Most recent file in `db-backup/` by mtime |
| Last ingest | `SELECT MAX(ingested_at) FROM sys_ingest_log` |
| Embedding count | ChromaDB `collection.count()` (if available) |

---

## 8. copy_chat_file.py

**Location:** `scripts/copy_chat_file.py`
**Triggered by:** CLAUDE.md instruction (explicit call by Claude)
**Phase:** 3.4

### Interface

```
Usage:  python3 copy_chat_file.py <filepath> --project <prefix> --session <session_id>

Args:
  filepath         Path to the file to copy
  --project        Project prefix (jg, gen, etc.)
  --session        Current session UUID

Returns:
  Exit code 0 on success, 1 on error

Stdout:
  "Copied {filename} → {dest_path}"
```

### Behavior

1. Validate source file exists
2. Validate project prefix exists in `project_registry`
3. Build destination path:
   ```
   {ROOT}/{project_folder}/chat-files/{YYYY-MM-DD}_{HHMMSS}_{session_id[:8]}/
   ```
4. Create destination directory if needed
5. Copy file (preserve original, do not move)
6. Print confirmation

### File Operations

| Operation | Detail |
|-----------|--------|
| Read | Source file (validate exists) |
| Mkdir | Destination subfolder (if needed) |
| Copy | Source → destination (shutil.copy2 to preserve metadata) |

---

## 9. HOOK CONTRACTS

All hooks are bash scripts. They read JSON from stdin and write JSON to stdout.
Claude Code manages the hook lifecycle — scripts just respond.

### Common Hook Pattern

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INPUT=$(cat)  # Read stdin JSON

# ... do work ...

# Output JSON to stdout (ONLY valid JSON, no other output)
echo '{"additionalContext": "..."}'
```

### Rule: stdout is SACRED

Hooks communicate with Claude Code via stdout JSON. Any stray `echo`, `print`,
or error message on stdout will corrupt the response. All script output that is
not the final JSON must go to stderr or log files.

---

### Hook 1: session-start.sh

**Location:** `hooks/session-start.sh`
**Fires:** Once when Claude Code session starts
**Phase:** 4.1

| Property | Value |
|----------|-------|
| Stdin | `{}` (empty JSON) |
| Stdout | `{"additionalContext": "..."}` |
| Calls | `scripts/startup_check.py` (stderr/log only), then queries `sys_session_summaries` |
| Blocking | Yes — Claude waits for this to finish |

**Stdout content:** Recent session summaries (last 5 per project, configurable),
formatted as markdown text in `additionalContext`.

```json
{
  "additionalContext": "## Recent Session Context\n\n### jg (Johnny Goods)\n- 2026-03-02: Worked on Step 19...\n\n### gen (General)\n- 2026-03-01: Discussed laptop setup..."
}
```

---

### Hook 2: user-prompt-submit.sh

**Location:** `hooks/user-prompt-submit.sh`
**Fires:** Before every user message is sent to Claude
**Phase:** 4.2

| Property | Value |
|----------|-------|
| Stdin | `{"prompts":[{"content":"user's message text"}]}` |
| Stdout | `{"additionalContext": "..."}` |
| Calls | Semantic search (if enabled) against prompt text |
| Blocking | Yes — runs before message reaches Claude |

**Stdout content:** Top 3 relevant memories from semantic search (or FTS5 fallback).

```json
{
  "additionalContext": "## Relevant Memories\n\n1. [2026-02-28, jg] Discussed Fat Tony's character...\n2. [2026-02-25, gen] Set up Fedora laptop..."
}
```

If semantic search is disabled/broken: return `{}` or FTS5 results.

---

### Hook 3: stop.sh

**Location:** `hooks/stop.sh`
**Fires:** After every Claude response completes
**Phase:** 4.3

| Property | Value |
|----------|-------|
| Stdin | `{}` (session metadata) |
| Stdout | `{}` |
| Calls | `scripts/write_exchange.py` |
| Blocking | No — should run fast, but does not block next prompt |

**Key requirement:** Must determine current session ID and JSONL path from
environment or Claude Code metadata. Pass to write_exchange.py.

---

### Hook 4: session-end.sh

**Location:** `hooks/session-end.sh`
**Fires:** When session ends (/exit or terminal close)
**Phase:** 4.4

| Property | Value |
|----------|-------|
| Stdin | `{}` (session metadata) |
| Stdout | `{}` |
| Calls | `scripts/generate_summary.py`, then `scripts/brain_sync.sh` |
| Blocking | N/A — session is ending |

**Note:** May not fire on terminal close. Data integrity guaranteed by
stop.sh having captured all exchanges already.

---

## 10. MCP SERVER CONTRACT

**Location:** `mcp/server.py`
**Registered:** `claude mcp add brain-server python3 mcp/server.py`
**Phase:** 5.1

### Server Setup

- Uses `mcp` Python SDK
- Read-only: all data access, no writes
- Connects to SQLite DB from config
- 10 tool functions registered

### Function Signatures

| Function | Args | Returns |
|----------|------|---------|
| `get_profile()` | none | All brain_facts + brain_preferences rows |
| `get_project_state(project)` | project: str | Recent decisions + key facts for project |
| `search_transcripts(query, project?, limit?, recency_bias?)` | query: str, project: str\|None, limit: int=20, recency_bias: bool=False | FTS5 search results with content preview |
| `get_session(session_id)` | session_id: str | All transcript rows for session, ordered by timestamp |
| `get_recent_sessions(project?, count?)` | project: str\|None, count: int=10 | List of recent sessions with metadata |
| `lookup_decision(project, topic)` | project: str, topic: str | Matching decisions by keyword search |
| `lookup_fact(project, category?, key?, recency_bias?)` | project: str, category: str\|None, key: str\|None, recency_bias: bool=True | Matching facts |
| `get_recent_summaries(project?, count?)` | project: str\|None, count: int=5 | Last N session summaries |
| `search_semantic(query, project?, limit?)` | query: str, project: str\|None, limit: int=10 | ChromaDB vector search results |
| `get_status()` | none | DB stats (same as status.py --json) |

### Recency Bias Rules

| Function | Default | Rationale |
|----------|---------|-----------|
| search_transcripts | OFF | User explicitly searching, relevance matters more |
| lookup_decision | Always OFF | Decisions are locked. Age is irrelevant. |
| lookup_fact | ON | Preferences and status change over time |
| search_semantic | OFF | Meaning-based search, relevance matters more |

### Recency Bias Implementation

When ON: multiply FTS5 rank by a time decay factor.
```sql
ORDER BY rank * (1.0 / (1.0 + julianday('now') - julianday(timestamp)))
```
Newer rows get a boost. Very old rows deprioritized but not excluded.

---

## DEPENDENCY GRAPH

```
config.yaml
    │
    ├── ingest_jsonl.py ←── startup_check.py ←── session-start.sh (hook)
    │
    ├── write_exchange.py ←── stop.sh (hook)
    │
    ├── generate_summary.py ←── session-end.sh (hook)
    │
    ├── brain_sync.sh ←── session-end.sh (hook)
    │                 ←── startup_check.py
    │
    ├── import_claude_ai.py (standalone)
    │
    ├── status.py ←── MCP get_status()
    │
    ├── copy_chat_file.py (standalone, called by Claude via CLAUDE.md)
    │
    └── mcp/server.py (standalone, registered with Claude Code)

    user-prompt-submit.sh (hook) ── reads DB + ChromaDB directly
```

---

## BLOCKER: CHROMADB + PYTHON 3.14

**Status:** ChromaDB crashes on import with Python 3.14 (pydantic v1 incompatibility)

**Error:**
```
pydantic.v1.errors.ConfigError: unable to infer type for attribute "chroma_server_nofile"
```

**Impact:** Semantic search (Decision 75) cannot work until resolved.

**Options:**
1. Wait for ChromaDB to release Python 3.14-compatible version
2. Install Python 3.12/3.13 alongside 3.14 and use it for brain scripts
3. Replace ChromaDB with a lighter vector search (e.g., `numpy` + cosine similarity on raw embeddings stored in SQLite)
4. Defer semantic search to post-MVP

**Decision needed from Mike before Phase 2.4 (write_exchange.py).**

All scripts are designed so semantic search is optional. Everything works
without it. The gating pattern is:

```python
try:
    import chromadb
    SEMANTIC_AVAILABLE = True
except (ImportError, Exception):
    SEMANTIC_AVAILABLE = False
```

---

## CROSS-REFERENCE: CONTRACT → TEST → TRACKER

| Script | Contract Section | Test IDs | Tracker Step |
|--------|-----------------|----------|--------------|
| ingest_jsonl.py | 1 | T-INGEST-* (18 tests) | 2.1 |
| startup_check.py | 2 | T-STARTUP-* (10 tests) | 2.3 |
| write_exchange.py | 3 | T-WRITE-* (8 tests) | 2.4 |
| generate_summary.py | 4 | T-SUMMARY-* (6 tests) | 2.5 |
| import_claude_ai.py | 5 | T-IMPORT-* (7 tests) | 3.1 |
| brain_sync.sh | 6 | T-SYNC-* (6 tests) | 3.2 |
| status.py | 7 | T-STATUS-* (4 tests) | 3.3 |
| copy_chat_file.py | 8 | T-COPY-* (5 tests) | 3.4 |
| session-start.sh | 9 (Hook 1) | T-HOOK-START-* (4 tests) | 4.1 |
| user-prompt-submit.sh | 9 (Hook 2) | T-HOOK-PROMPT-* (4 tests) | 4.2 |
| stop.sh | 9 (Hook 3) | T-HOOK-STOP-* (3 tests) | 4.3 |
| session-end.sh | 9 (Hook 4) | T-HOOK-END-* (3 tests) | 4.4 |
| mcp/server.py | 10 | T-MCP-* (18 tests) | 5.1 |
