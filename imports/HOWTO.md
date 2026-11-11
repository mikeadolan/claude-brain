# Importing conversations into claude-brain

Claude Code sessions are captured automatically by the hooks - nothing to do.
The other sources need one command each. Everything below is safe to re-run:
already-imported conversations are skipped.

| Source | What you need | Where to read more |
|---|---|---|
| Claude.ai | JSON export per conversation (Chrome extension) | [Section 7.1](../CLAUDE_BRAIN_HOW_TO.md) |
| ChatGPT | Full account export from OpenAI | [Section 7.2](../CLAUDE_BRAIN_HOW_TO.md) |
| Gemini | Google Takeout, My Activity → Gemini Apps | [Section 7.3](../CLAUDE_BRAIN_HOW_TO.md) |
| GitHub Copilot Chat | Nothing - read from local disk | [Section 7.4](../CLAUDE_BRAIN_HOW_TO.md) |

---

## Quick start: GitHub Copilot Chat

Copilot writes its history to `%APPDATA%\Code\User\...` and `~/.copilot/session-state`.
No export, no extension, no upload.

**1. Scan** (read-only, writes a review file):

```bash
python3 scripts/import_copilot.py --scan
```

Output ends with the path of `imports/copilot_import_map.csv`. You get a summary like:

```
Sessions with content : 120
Turns                 : 1641
New                   : 120
Trimmed in JSONL      : 28
Orphaned workspace    : 14
```

**2. Review the CSV** - one row per conversation:

| Column | What to do with it |
|---|---|
| `project` | Change it if the suggested prefix is wrong. This is the only column you need to edit |
| `title` | Read-only, so you recognise the conversation |
| `workspace_exists` | `no` = folder renamed/moved/deleted. The chat is still imported |
| `truncated` | Copilot dropped older messages; that part is gone and cannot be recovered |
| `status` | `IMPORTED` means it is already in the brain |

**3. Dry run, then import:**

```bash
python3 scripts/import_copilot.py --import --map imports/copilot_import_map.csv --dry-run
python3 scripts/import_copilot.py --import --map imports/copilot_import_map.csv
```

Re-running is safe: messages are keyed so nothing is duplicated. Your project and tag
choices are **not** overwritten - if you change the `project` column later, apply it with
`--update-metadata`:

```bash
python3 scripts/import_copilot.py --import --map imports/copilot_import_map.csv --update-metadata
```

**4. Check the result:**

```bash
python3 scripts/import_copilot.py --report --output imports/copilot_imported.md
python3 scripts/brain_search.py "something you remember from a Copilot chat"
```

### What gets imported

- User messages and assistant answers (tool calls and thinking blocks are skipped)
- Inline references, rendered as `[name]`
- Timestamps, model, workspace path, session id
- Source tag `copilot_chat` (VS Code) or `copilot_agent` (agent host)

### What does not

- Chats that never had a message. Most files on a long-lived machine are empty shells
- Tool output and file diffs
- History Copilot itself dropped from its JSONL. Sessions where the session store holds more
  turns use the store instead; the rest is recorded in `sys_sessions.notes` as
  `history truncated by Copilot`

### Registering imported prefixes

Where a prefix belongs depends on whether the workspace still exists on disk:

| Situation | Where it goes | How |
|---|---|---|
| Folder exists (anywhere, including another drive or a UNC share) | `projects:` with a `path` | `python3 scripts/add-project.py --path "<folder>"` |
| Folder is gone, or is a bare drive root | `import_projects:` | add the entry by hand |

Only `projects:` entries get a CLAUDE.md, a registry row and a brain-server MCP
registration. `import_projects:` entries are labels for history that no longer has a
directory -- the transcripts stay queryable, but nothing is created for them.

```yaml
projects:
  - folder_name: "tradingview-indicators"
    prefix: "tradingview-indicators"
    label: "Tradingview Indicators"
    path: "C:\\GIT\\Tradingview_indicators"

import_projects:
  - folder_name: "xscraper"
    prefix: "xscraper"
    label: "XScraper"
```

Add the same prefix to `jsonl_project_mapping:` so future transcripts route to it
automatically. For a project nested inside another one, add the more specific path
fragment as well -- the longest matching key wins.

---

## Claude.ai

1. Install the **AI Chat Exporter** Chrome extension
2. Open a conversation on claude.ai, click the extension icon, export as **JSON**
3. Save the `.json` into `imports/`
4. In Claude Code, run `/brain-import`, or from a terminal:

```bash
python3 scripts/import_claude_ai.py "imports/My conversation.json" --project oth
```

The file is moved to `imports/completed/` afterwards.

## ChatGPT

```bash
python3 scripts/import_chatgpt.py --scan imports/chatgpt-export/
# edit imports/chatgpt_import_map.xlsx (project + tags)
python3 scripts/import_chatgpt.py --import imports/chatgpt-export/ --map imports/chatgpt_import_map.xlsx
```

## Gemini

```bash
python3 scripts/import_gemini.py --scan imports/gemini-export/
# edit imports/gemini_import_map.xlsx
python3 scripts/import_gemini.py --import imports/gemini-export/ --map imports/gemini_import_map.xlsx
```

Takeout tip: select **My Activity → Gemini Apps**. Choosing just "Gemini" yields an empty file.

---

## Verifying an import

```bash
python3 scripts/brain_search.py "a phrase from the conversation"   # is it searchable?
python3 scripts/status.py                                          # counts per project
```

If semantic search is enabled, run `python3 scripts/batch_embed.py` so the new rows are
included in the embedding index as well.
