# CLAUDE-BRAIN - TEST SPECIFICATIONS

**Created:** 2026-03-03
**Last Updated:** 2026-03-03
**Purpose:** Define all test cases BEFORE code is written. Build to pass.
**Related:** PROJECT_TRACKER.md (step mapping), SCRIPT_CONTRACTS.md (interfaces)

---

## CONVENTIONS

- **Test IDs** use format: `T-{component}-{number}` (e.g., T-INGEST-01)
- **Fixture files** live in `verification/fixtures/`
- **Audit reports** written to `verification/AUDIT_REPORT_{date}_{phase}_{component}.txt`
- **Pass criteria:** Every test must pass. Zero tolerance for skipped tests.
- **Test runner:** Each component gets a `verification/test_{component}.py` script
- **DB state notation:** `→ table(count)` means "assert N rows in table after"

---

## FIXTURE FILES NEEDED

These must be created before any script testing begins.

| Fixture | Description |
|---------|-------------|
| `fixtures/valid_session.jsonl` | 10-line session: 1 system, 3 user, 3 assistant, 2 progress, 1 file-history-snapshot. Real UUIDs, timestamps, session ID. |
| `fixtures/valid_session_with_tools.jsonl` | Session with assistant tool_use content blocks and user tool_result content blocks. |
| `fixtures/subagent_session.jsonl` | Subagent JSONL (has `agentId` field). 5 lines. |
| `fixtures/tool_result_sample.txt` | Plain text tool result file (matches toolu_*.txt format). |
| `fixtures/malformed.jsonl` | 5 lines: 1 valid, 1 truncated JSON, 1 empty line, 1 missing uuid, 1 missing type. |
| `fixtures/duplicate_uuids.jsonl` | 4 lines: 2 valid messages with unique UUIDs, then 2 messages reusing those same UUIDs. |
| `fixtures/claude_ai_export.json` | Minimal claude.ai export: uuid, name, chat_messages (5 messages: 3 human, 2 assistant). Matches real format: sender, text, content, uuid, created_at, parent_message_uuid. |
| `fixtures/empty.jsonl` | Empty file (0 bytes). |
| `fixtures/config_minimal.yaml` | Bare minimum valid config for testing. |
| `fixtures/config_missing_keys.yaml` | Config missing required sections (no `storage`). |

---

## 1. INGEST_JSONL.PY

Core ingestion engine. Parses JSONL, maps projects, deduplicates, writes to DB.

### Happy Path

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-INGEST-01 | Ingest a valid session | `fixtures/valid_session.jsonl`, project mapping → "gen" | → sys_sessions(1), transcripts(7 - user+assistant+system, NOT progress or file-history-snapshot), sys_ingest_log(1) |
| T-INGEST-02 | Extract session metadata | Same fixture | sys_sessions row: session_id matches JSONL, project="gen", started_at = earliest timestamp, model from assistant message, source="jsonl_ingest" |
| T-INGEST-03 | Store raw JSON | Same fixture | Every transcripts row has non-null raw_json. raw_json parses back to valid JSON matching original line. |
| T-INGEST-04 | Ingest session with tool_use/tool_result | `fixtures/valid_session_with_tools.jsonl` | Tool use and tool result blocks stored. Content field captures text content. |
| T-INGEST-05 | Ingest subagent JSONL | `fixtures/subagent_session.jsonl` | → transcripts rows have is_subagent=1. Session ID from JSONL. Ingest log: file_type="subagent". |
| T-INGEST-06 | Ingest tool result txt file | `fixtures/tool_result_sample.txt` in a session folder | → tool_results(1). tool_use_id = filename minus .txt. content = file contents. |
| T-INGEST-07 | Project mapping - Windows folder name | Folder name "C--Users-micha-OneDrive-Documents-Projects-Johnny-Goods-claude-code" | project = "jg" |
| T-INGEST-08 | Project mapping - Fedora cwd path | cwd = "/home/user/claude-brain/johnny-goods-assistant/..." | project = "jga" (NOT "jg" - longer match wins) |
| T-INGEST-09 | Project mapping - no match | cwd = "/tmp/randomfolder" | project = "oth" (default) |
| T-INGEST-10 | Message count | Valid session with 3 user + 3 assistant + 1 system = 7 storable messages | sys_sessions.message_count = 7 |

### Deduplication

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-INGEST-20 | Skip duplicate UUIDs | `fixtures/duplicate_uuids.jsonl` | → transcripts(2) not 4. Only first occurrence stored. No error raised. |
| T-INGEST-21 | Re-ingest same file | Run ingest on `valid_session.jsonl` twice | Second run: 0 new records. sys_ingest_log still shows 1 row. No duplicates in transcripts. |
| T-INGEST-22 | Ingest log prevents re-import | After ingesting a file, check sys_ingest_log | Row exists with correct file_path, file_size, records_imported, ingested_at. |

### Error Handling

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-INGEST-30 | Malformed JSONL lines | `fixtures/malformed.jsonl` | Valid lines ingested. Invalid lines logged and skipped. Script does NOT crash. Returns count of skipped lines. |
| T-INGEST-31 | Empty file | `fixtures/empty.jsonl` | No rows inserted. Ingest log records 0 records_imported. No error. |
| T-INGEST-32 | File not found | Path to nonexistent file | Script returns error code. Logs error. Does not crash. |
| T-INGEST-33 | Database locked | Simulate locked DB (concurrent connection with write lock) | Script retries or returns clear error. Does not corrupt data. |
| T-INGEST-34 | Missing uuid field | JSONL line with no uuid | Line skipped. Logged as warning. Other lines still processed. |

### Data Integrity

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-INGEST-40 | FTS5 sync after ingest | Ingest valid session, then search FTS5 for a word from content | FTS5 returns matching row. Triggers kept index in sync. |
| T-INGEST-41 | Timestamps preserved | Ingest valid session | transcripts.timestamp matches JSONL timestamp exactly (ISO 8601). |
| T-INGEST-42 | Parent UUID chain | Messages with parentUuid values | transcripts.parent_uuid matches JSONL parentUuid. |
| T-INGEST-43 | Content extraction - text blocks | Assistant message with content: [{type: "text", text: "hello"}] | transcripts.content = "hello" |
| T-INGEST-44 | Content extraction - thinking blocks | Assistant message with thinking + text blocks | transcripts.content captures text blocks. Thinking blocks handled (stored or excluded - decision needed). |
| T-INGEST-45 | System message subtypes | System messages with subtype "compact_boundary" | transcripts.subtype = "compact_boundary" |

---

## 2. STARTUP_CHECK.PY

Session start orchestrator. Scans for new JSONL, calls ingest, verifies folders, backs up DB.

### Happy Path

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-STARTUP-01 | Scan finds new files | Place fixture JSONL in a source_path directory | Script detects it, calls ingest, file now in sys_ingest_log. |
| T-STARTUP-02 | Scan skips ingested files | File already in sys_ingest_log | File not re-processed. Log says "0 new files". |
| T-STARTUP-03 | Scans both source paths | Files in Fedora path AND Windows archive path | Both scanned. New files from both ingested. |
| T-STARTUP-04 | Subagent/tool-result discovery | Session folder with subagents/ and tool-results/ subdirs | All subagent JSONL and tool-result TXT files discovered and ingested. |
| T-STARTUP-05 | Database backup triggered | Run startup check | Backup file created in db-backup/. File size > 0. |
| T-STARTUP-06 | Folder verification | All required folders exist | Script confirms. Returns success. |
| T-STARTUP-07 | Summary output | Normal run | Prints: files scanned, new files ingested, records added, backup status. |

### Error Handling

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-STARTUP-10 | Source path does not exist | Config points to nonexistent path | Script logs warning. Continues with other paths. Does not crash. |
| T-STARTUP-11 | Missing folder | One required folder deleted | Script logs warning. Optionally recreates it. Does not crash. |
| T-STARTUP-12 | Database unreachable | Wrong DB path in config | Script exits with clear error. Does not create a new DB at wrong path. |

---

## 3. WRITE_EXCHANGE.PY

Captures live exchanges during active sessions. Called by stop hook after every Claude response.

### Happy Path

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-WRITE-01 | Write user+assistant pair | User message JSON + assistant message JSON | → transcripts(2). Correct session_id, project, type, content, timestamp. |
| T-WRITE-02 | Session auto-created | Exchange for a session_id not yet in sys_sessions | → sys_sessions(1) created with session_id, project, started_at. |
| T-WRITE-03 | Session updated | Exchange for existing session | sys_sessions.message_count incremented. ended_at updated. |
| T-WRITE-04 | Embedding generated | Semantic search enabled in config | ChromaDB collection has new entry. Embedding vector has correct dimensions (384 for MiniLM-L6-v2). |
| T-WRITE-05 | Embedding skipped | Semantic search disabled in config | No ChromaDB write. No error. |
| T-WRITE-06 | Dedup on uuid | Exchange with uuid already in transcripts | Skipped. No duplicate. No error. |

### Error Handling

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-WRITE-10 | ChromaDB unavailable | Semantic search enabled but ChromaDB path invalid | Exchange still written to SQLite. Error logged for ChromaDB. Non-blocking. |
| T-WRITE-11 | Empty content | Message with empty string content | Row written with empty content. Not skipped. |

---

## 4. [DELETED] GENERATE_SUMMARY.PY

**Status:** DELETED in session 22. Claude writes notes directly via end-session protocol.
No OpenRouter API. No Python fallback. sys_session_summaries table dropped (session 25).
All session context now lives in `sys_sessions.notes`.

---

## 5. IMPORT_CLAUDE_AI.PY

Imports claude.ai JSON conversation exports.

### Happy Path

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-IMPORT-01 | Import valid export | `fixtures/claude_ai_export.json` | → transcripts(5). source_file = original path. Each row has uuid from export. |
| T-IMPORT-02 | Session created | Same | → sys_sessions(1). source="claude_ai_import". |
| T-IMPORT-03 | Message mapping | Human messages → type="user", role="user". Assistant messages → type="assistant", role="assistant". | Content matches export text field. |
| T-IMPORT-04 | File moved on success | After import | File moved from imports/ to imports/completed/. |

### Error Handling

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-IMPORT-10 | Invalid JSON file | Corrupt JSON | Script reports error. File not moved. No partial data. |
| T-IMPORT-11 | Missing required fields | JSON with no chat_messages | Script reports error. Does not crash. |
| T-IMPORT-12 | Duplicate import | Same file imported twice | Second import: dedup by uuid. No duplicate rows. |

---

## 6. BRAIN_SYNC.PY

Rotating backup of SQLite database.

### Happy Path

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-SYNC-01 | First backup | No existing backups in db-backup/ | 1 backup file created. File size matches source DB size (±1%). |
| T-SYNC-02 | Rotation - 2 copies | 2 existing backups | Oldest deleted. Current renamed. New copy created. Total = 2 files. |
| T-SYNC-03 | Verify after copy | backup.verify_after_copy=true in config | Script checks file size > 0 and SQLite integrity_check passes. |
| T-SYNC-04 | Log output | Normal run | Prints: timestamp, file size, backup path. |

### Error Handling

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-SYNC-10 | Source DB missing | DB file does not exist | Script exits with clear error. Does not create empty backup. |
| T-SYNC-11 | Backup dir missing | db-backup/ deleted | Script creates directory, then backs up. |

---

## 7. STATUS.PY

Database stats and health check.

### Happy Path

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-STATUS-01 | All stats returned | DB with data | Output includes: total sessions, total messages, DB file size, messages per project, last session per project, last backup info. |
| T-STATUS-02 | Semantic search status | Semantic search enabled, embeddings exist | Output includes embedding count and collection name. |
| T-STATUS-03 | Semantic search disabled | Config has semantic_search.enabled=false | Output says "Semantic search: disabled". No error. |
| T-STATUS-04 | Empty database | Fresh DB with 0 data rows | All counts = 0. No errors. |

---

## 8. COPY_CHAT_FILE.PY

File versioning to chat-files/ per project.

### Happy Path

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-COPY-01 | Copy a file | Filepath, project, session_id | File copied to {project}/chat-files/{date}_{time}_{session_short}/. Original unchanged. |
| T-COPY-02 | Subfolder naming | Session ID "a25d2fc5-9c03-4c24-ab5f-fab1e0d33d6b" | Subfolder uses first 8 chars: a25d2fc5. Date and time match current. |
| T-COPY-03 | Multiple files same session | Two files copied with same session_id | Both land in same subfolder. |

### Error Handling

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-COPY-10 | Source file missing | Path to nonexistent file | Script exits with error. Logs message. |
| T-COPY-11 | Invalid project | Project not in project_registry | Script exits with error. Does not create orphan folders. |

---

## 9. HOOKS

### session-start.py (Hook 1)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-HOOK-START-01 | Runs startup_check.py | Hook fires | startup_check.py executes. Exit code 0. |
| T-HOOK-START-02 | Loads recent summaries | DB has session summaries | Output JSON: {"additionalContext": "## Recent Session Context\n..."} containing recent summaries. |
| T-HOOK-START-03 | Empty summaries | No summaries in DB | Output JSON: {"additionalContext": ""} or minimal context. Valid JSON. |
| T-HOOK-START-04 | Valid JSON output | Any state | stdout is parseable JSON. No extra output mixed in. |

### user-prompt-submit.py (Hook 2)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-HOOK-PROMPT-01 | Receives prompt via stdin | stdin: {"user_prompt":"test query"} | Script extracts "test query". |
| T-HOOK-PROMPT-02 | Semantic search results | Relevant data in DB | Output JSON: {"hookSpecificOutput":{"hookEventName":"UserPromptSubmit","additionalContext":"## Relevant Memories\n..."}} with top 3 results. |
| T-HOOK-PROMPT-03 | No results | Empty DB / no matches | Output JSON with empty or minimal additionalContext. Valid JSON. |
| T-HOOK-PROMPT-04 | Semantic search disabled | Config: enabled=false | Hook returns {} or minimal JSON. No error. |

### stop.py (Hook 3)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-HOOK-STOP-01 | Calls write_exchange.py | Hook fires after response | write_exchange.py runs. New rows in transcripts. |
| T-HOOK-STOP-02 | Non-blocking | Hook runs | Returns quickly. Does not block next user prompt. |
| T-HOOK-STOP-03 | Valid JSON output | Any state | stdout: {} (empty JSON object). |

### session-end.py (Hook 4)

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-HOOK-END-01 | Runs backup | Hook fires on session end | brain_sync.py runs (detached). New backup in db-backup/. |
| T-HOOK-END-02 | Returns instantly | Hook fires | Hook returns {} without blocking. brain_sync.py detached. |
| T-HOOK-END-03 | Fallback notes written | Session has no notes when hook fires | sys_sessions.notes updated with AUTO-GENERATED FALLBACK placeholder. |
| T-HOOK-END-04 | No-op when notes exist | Session already has notes from Claude | sys_sessions.notes unchanged. Hook does not overwrite. |
| T-HOOK-END-05 | Valid JSON output | Any state | stdout: {} (empty JSON object). |

---

## 10. MCP SERVER (server.py)

### get_profile()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-PROFILE-01 | Returns all facts + prefs | brain_facts and brain_preferences populated | Returns all rows from both tables. |
| T-MCP-PROFILE-02 | Empty profile | No data in brain tables | Returns empty result. No error. |

### search_transcripts()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-SEARCH-01 | FTS5 search | query="ASUS laptop", transcripts has matching row | Returns matching rows with content preview. |
| T-MCP-SEARCH-02 | Project filter | query="test", project="jg" | Only returns jg rows. |
| T-MCP-SEARCH-03 | Limit | limit=5, 20 matches exist | Returns exactly 5. |
| T-MCP-SEARCH-04 | Relevance ranking | Two results with different relevance | Higher-relevance result ranks first (recency_bias removed from MCP schema). |
| T-MCP-SEARCH-05 | Fixed limit | 30 matches exist in DB | Returns exactly 20 (hardcoded limit, not overridable via MCP). |
| T-MCP-SEARCH-06 | No results | query="xyzzynonexistent" | Returns empty list. No error. |

### search_semantic()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-SEMANTIC-01 | Meaning-based search | query="illegal gambling", DB has "ran numbers on Pleasant Ave" | Returns the matching row. |
| T-MCP-SEMANTIC-02 | Project filter | query="test", project="jg" | Only returns jg results. |
| T-MCP-SEMANTIC-03 | Disabled | semantic_search.enabled=false | Returns message: "Semantic search is not enabled." |

### get_session()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-SESSION-01 | Full transcript | Valid session_id | Returns all transcript rows for that session, ordered by timestamp. |
| T-MCP-SESSION-02 | Invalid session | Nonexistent session_id | Returns empty result or "Session not found." |

### get_recent_sessions()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-RECENT-01 | List recent | count=5, 10 sessions exist | Returns 5 most recent sessions. |
| T-MCP-RECENT-02 | Project filter | project="jg" | Only jg sessions returned. |

### lookup_decision()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-DECISION-01 | Find by keyword | project="jg", topic="Teamsters" | Returns matching decisions. |
| T-MCP-DECISION-02 | No recency bias | Any query | Recency bias always OFF for decisions. |

### lookup_fact()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-FACT-01 | By project + category | project="jg", category="character" | Returns matching facts. |
| T-MCP-FACT-02 | By key | key="Fat Tony" | Returns that specific fact. |

### get_recent_summaries()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-SUMMARIES-01 | Return last N | count=5, 10 summaries exist | Returns 5 most recent. |
| T-MCP-SUMMARIES-02 | Project filter | project="jg" | Only jg summaries. |

### get_status()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-STATUS-01 | Returns stats | DB with data | Total sessions, messages, DB size, last backup. |

### get_project_state()

| ID | Test | Input | Expected |
|----|------|-------|----------|
| T-MCP-PROJECT-01 | Returns decisions + facts | project="jg" | Returns recent decisions and key facts for jg. |
| T-MCP-PROJECT-02 | Unknown project | project="zzz" | Returns empty result. No error. |

---

## 11. INTEGRATION TESTS

End-to-end tests that verify components work together.

| ID | Test | Scenario | Expected |
|----|------|----------|----------|
| T-INT-01 | Full ingest pipeline | Place JSONL in source path → run startup_check.py | sys_ingest_log, sys_sessions, transcripts all populated. Backup created. |
| T-INT-02 | Hook → script chain | session-start hook fires → startup_check runs → ingest runs | Data in DB. Context returned as JSON. |
| T-INT-03 | Write + search | write_exchange.py writes data → search_transcripts() finds it → search_semantic() finds it | Both FTS5 and ChromaDB return the written data. |
| T-INT-04 | Session lifecycle | Start → 3 exchanges → end | sys_sessions(1), transcripts(6), backup created. |
| T-INT-05 | Crash recovery | Simulate terminal close (no session-end hook) → next session start | startup_check reconciles from JSONL. No data lost. |
| T-INT-06 | Cross-project search | Data from jg and gen in DB | search_transcripts without project filter returns both. With project filter returns only one. |
| T-INT-07 | MCP → DB round-trip | Populate brain_facts → get_profile() via MCP | Profile data matches what was inserted. |

---

## 12. OBSERVED JSONL FORMAT REFERENCE

Documented from real files to ensure test fixtures are accurate.

### Message Types and Fields

| Type | Fields (always present) | Fields (sometimes present) |
|------|------------------------|---------------------------|
| **user** | type, uuid, parentUuid, sessionId, timestamp, message, cwd, version, userType, isSidechain, gitBranch | permissionMode, thinkingMetadata, todos, toolUseResult, slug, sourceToolAssistantUUID |
| **assistant** | type, uuid, parentUuid, sessionId, timestamp, message, cwd, version, userType, isSidechain, gitBranch | |
| **system** | type, uuid, parentUuid, sessionId, timestamp, cwd, version, userType, isSidechain, gitBranch, subtype, slug | durationMs, isMeta |
| **progress** | type, uuid, parentUuid, sessionId, timestamp, cwd, version, userType, isSidechain, gitBranch, data, slug | parentToolUseID, toolUseID |
| **file-history-snapshot** | type, messageId, snapshot, isSnapshotUpdate | |

### System Subtypes Observed

`compact_boundary`, `microcompact_boundary`, `turn_duration`

### Message Content Block Types (within message.content)

`text`, `tool_use`, `tool_result`, `thinking`, `redacted_thinking`

### Subagent JSONL Differences

Same structure as main JSONL but includes `agentId` field on every line.

### Claude.ai Export Format (JSON, not JSONL)

```
{
  "uuid": "...",
  "name": "conversation title",
  "summary": "...",
  "created_at": "ISO 8601",
  "updated_at": "ISO 8601",
  "chat_messages": [
    {
      "uuid": "...",
      "sender": "human" | "assistant",
      "text": "message text",
      "content": [...],
      "created_at": "ISO 8601",
      "parent_message_uuid": "...",
      "index": 0,
      "attachments": [],
      "files": [],
      "files_v2": [],
      "truncated": false
    }
  ]
}
```

---

## TEST EXECUTION ORDER

Tests should be run in this order (dependency chain):

1. **Fixtures created** (prerequisite for everything)
2. **ingest_jsonl.py tests** (T-INGEST-*) - core engine, no other script depends on it being wrong
3. **startup_check.py tests** (T-STARTUP-*) - depends on ingest working
4. **write_exchange.py tests** (T-WRITE-*) - independent of ingest
5. **brain_sync.py tests** (T-SYNC-*) - independent
6. **status.py tests** (T-STATUS-*) - reads DB populated by above
7. **copy_chat_file.py tests** (T-COPY-*) - independent
8. **import_claude_ai.py tests** (T-IMPORT-*) - independent
10. **Hook tests** (T-HOOK-*) - depends on scripts working
11. **MCP tests** (T-MCP-*) - depends on data existing
12. **Integration tests** (T-INT-*) - depends on everything

---

## TOTAL TEST COUNT

| Component | Happy | Dedup/Edge | Error | Total |
|-----------|-------|------------|-------|-------|
| ingest_jsonl.py | 10 | 3 | 5 | 18 |
| startup_check.py | 7 | - | 3 | 10 |
| write_exchange.py | 6 | - | 2 | 8 |
| import_claude_ai.py | 4 | - | 3 | 7 |
| brain_sync.py | 4 | - | 2 | 6 |
| status.py | 4 | - | - | 4 |
| copy_chat_file.py | 3 | - | 2 | 5 |
| Hooks (4 hooks) | 11 | - | - | 11 |
| MCP Server (10 functions) | 18 | - | - | 18 |
| Integration | 7 | - | - | 7 |
| **TOTAL** | **77** | **3** | **20** | **100** |
