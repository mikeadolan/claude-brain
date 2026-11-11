#!/usr/bin/env python3
"""import_copilot.py - Import GitHub Copilot Chat history into claude-brain.

Copilot data sources:

1. VS Code chat sessions: one JSONL file per session under
   %APPDATA%\\<variant>\\User\\workspaceStorage\\<hash>\\chatSessions\\ and
   %APPDATA%\\<variant>\\User\\globalStorage\\emptyWindowChatSessions\\ (no folder)
2. The Copilot session store: a SQLite database under globalStorage that holds
   the full turn history of agent-mode sessions:
   %APPDATA%\\<variant>\\User\\globalStorage\\github.copilot-chat\\session-store.db
3. The agent host: ~/.copilot/session-state/<id>/events.jsonl plus workspace.yaml

The JSONL file is a replay log, not a transcript:
   kind 0 = header (customTitle, creationDate, sessionId, requests[])
   kind 1 = patch of a single field at path k
   kind 2 = full replacement of the value at path k

Assistant text lives in response parts without a "kind" field, concatenated in
order; inline references are rendered as [label]. Long sessions are trimmed in
the JSONL, so the store often holds more turns for the same session; every
source is read and the richest one wins per session.

Workflow:
    python3 import_copilot.py --scan
    python3 import_copilot.py --import --map imports/copilot_import_map.csv --dry-run
    python3 import_copilot.py --import --map imports/copilot_import_map.csv
"""

import argparse
import csv
import json
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

USE_COLOR = sys.stdout.isatty()


def green(text):
    return f"\033[32m{text}\033[0m" if USE_COLOR else text


def yellow(text):
    return f"\033[33m{text}\033[0m" if USE_COLOR else text


def red(text):
    return f"\033[31m{text}\033[0m" if USE_COLOR else text


def dim(text):
    return f"\033[2m{text}\033[0m" if USE_COLOR else text


# ---------------------------------------------------------------------------
# Paths / config
# ---------------------------------------------------------------------------

ROOT_DIR = Path(__file__).resolve().parent.parent

DEFAULT_PROJECT = "oth"
VSCODE_VARIANTS = ["Code", "Code - Insiders", "VSCodium", "Cursor"]
STORE_RELATIVE = Path("User") / "globalStorage" / "github.copilot-chat" / "session-store.db"


def load_config():
    """Return (config, db_path). db_path may be None when unavailable."""
    config_path = ROOT_DIR / "config.yaml"
    config = {}
    db_path = None
    if config_path.exists():
        import yaml

        with open(config_path, encoding="utf-8") as f:
            config = yaml.safe_load(f) or {}
        storage = config.get("storage", {})
        if storage.get("mode", "local") == "synced":
            db_path = storage.get("local_db_path")
        else:
            db_path = os.path.join(storage.get("root_path", ""), "claude-brain.db")
    return config, db_path


def default_data_roots():
    """Return [dict] describing every Copilot data location on this machine."""
    roots = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        for variant in VSCODE_VARIANTS:
            user_dir = Path(appdata) / variant / "User"
            storage = user_dir / "workspaceStorage"
            store = Path(appdata) / variant / STORE_RELATIVE
            empty_window = user_dir / "globalStorage" / "emptyWindowChatSessions"
            if storage.is_dir() or store.is_file() or empty_window.is_dir():
                roots.append(
                    {
                        "variant": variant,
                        "storage": storage if storage.is_dir() else None,
                        "store": store if store.is_file() else None,
                        "empty_window": empty_window if empty_window.is_dir() else None,
                    }
                )
    return roots


def agent_state_dir():
    """Return the agent-host session directory (~/.copilot/session-state)."""
    return Path(os.path.expanduser("~")) / ".copilot" / "session-state"


# ---------------------------------------------------------------------------
# JSONL replay
# ---------------------------------------------------------------------------


def _set_at(state, path, value):
    """Apply one replay record: set `value` at the nested `path`."""
    node = state
    for key in path[:-1]:
        if isinstance(key, int):
            if not isinstance(node, list) or key >= len(node):
                return False
            node = node[key]
        else:
            if not isinstance(node, dict):
                return False
            node = node.setdefault(key, {})
    last = path[-1]
    if isinstance(node, list):
        if not isinstance(last, int):
            return False
        while len(node) <= last:
            node.append({})
        node[last] = value
    elif isinstance(node, dict):
        node[last] = value
    else:
        return False
    return True


def replay_jsonl(path):
    """Return the final header state of a Copilot chat JSONL replay log."""
    state = None
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue  # truncated write from a crash mid-flush
            kind = record.get("kind")
            if kind == 0:
                state = record.get("v") or {}
                continue
            path_keys = record.get("k")
            if not isinstance(path_keys, list) or not path_keys or state is None:
                continue
            _set_at(state, path_keys, record.get("v"))
    return state or None


def _inline_ref_text(ref):
    """Render an inline reference as [label]: symbols by name, files by basename."""
    if not isinstance(ref, dict):
        return ""
    label = ref.get("name")
    if not label:
        for key in ("fsPath", "path", "external"):
            value = ref.get(key)
            if isinstance(value, str) and value:
                label = value.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
                break
    if not label:
        return ""
    return f"[{label}]"


def _part_text(part):
    """Extract the visible text of a response part, or '' when it has none."""
    if isinstance(part, str):
        return part
    if not isinstance(part, dict):
        return ""
    kind = part.get("kind")
    if kind == "inlineReference":
        return _inline_ref_text(part.get("inlineReference"))
    if kind is not None:
        return ""
    value = part.get("value")
    if isinstance(value, dict):
        value = value.get("value")
    return value if isinstance(value, str) else ""


def _user_text(message):
    if isinstance(message, str):
        return message
    if not isinstance(message, dict):
        return ""
    text = message.get("text")
    if isinstance(text, str) and text:
        return text
    parts = message.get("parts") or []
    return "".join(
        p.get("text", "") for p in parts if isinstance(p, dict) and isinstance(p.get("text"), str)
    )


def _ms_to_iso(value):
    """Convert epoch milliseconds to an ISO-8601 UTC string."""
    if not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (OverflowError, OSError, ValueError):
        return None


def extract_turns(header):
    """Return [{timestamp, user, assistant, model}] for one session header."""
    turns = []
    for request in header.get("requests") or []:
        if not isinstance(request, dict) or request.get("hiddenFromTranscript"):
            continue
        user = _user_text(request.get("message"))
        assistant = "".join(_part_text(p) for p in request.get("response") or [])
        if not user.strip() and not assistant.strip():
            continue
        turns.append(
            {
                "timestamp": _ms_to_iso(request.get("timestamp")),
                "user": user,
                "assistant": assistant,
                "model": request.get("modelId"),
            }
        )
    return turns


def _clean_title(text, limit=80):
    """Collapse a title to a single readable line."""
    if not isinstance(text, str):
        return ""
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    return cleaned[:limit]


def _title_from_header(header, turns):
    title = _clean_title(header.get("customTitle"))
    if not title:
        for turn in turns:
            title = _clean_title((turn["user"] or "").strip().splitlines()[0] if turn["user"].strip() else "")
            if title:
                break
    return title or "(untitled)"


def read_workspace_folder(workspace_json):
    """Return the folder of a workspace.json, or None for multi-root workspaces."""
    try:
        with open(workspace_json, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    uri = data.get("folder")
    if not uri:
        return None
    if uri.startswith("file:///"):
        from urllib.parse import unquote

        path = unquote(uri[len("file:///") :])
        return path.replace("/", "\\")
    return None


def parse_jsonl_session(path):
    """Return a session dict for one chatSessions/*.jsonl file, or None."""
    header = replay_jsonl(path)
    if header is None:
        return None
    turns = extract_turns(header)
    session_id = header.get("sessionId") or path.stem
    created = _ms_to_iso(header.get("creationDate"))
    timestamps = [t["timestamp"] for t in turns if t["timestamp"]]
    return {
        "session_id": session_id,
        "title": _title_from_header(header, turns),
        "created_at": created or (timestamps[0] if timestamps else None),
        "updated_at": timestamps[-1] if timestamps else created,
        "turns": turns,
        "jsonl_path": str(path),
        "jsonl_turns": len(turns),
        "store_turns": 0,
        "store_cwd": None,
        "store_summary": None,
        "sources": {"jsonl"},
    }


def _iso_z(value):
    """Pass through an ISO timestamp, or None when it is not usable."""
    return value if isinstance(value, str) and value.strip() else None


def read_empty_window_sessions(empty_window_dir):
    """Return sessions for chats opened without a folder (empty window)."""
    sessions = []
    if not empty_window_dir or not Path(empty_window_dir).is_dir():
        return sessions
    for path in sorted(Path(empty_window_dir).glob("*.jsonl")):
        session = parse_jsonl_session(path)
        if session is None or not session["turns"]:
            continue
        session["workspace_hash"] = None
        session["workspace_folder"] = None
        sessions.append(session)
    return sessions


def read_agent_sessions(base_dir):
    """Return sessions from the agent host: <base>/<id>/events.jsonl.

    Assistant messages stream in as several events per reply, so consecutive
    non-empty assistant.message events between two user.message events are
    joined into one reply.
    """
    sessions = []
    if not base_dir or not Path(base_dir).is_dir():
        return sessions
    import yaml

    for events_path in sorted(Path(base_dir).glob("*/events.jsonl")):
        meta = {}
        workspace_yaml = events_path.parent / "workspace.yaml"
        if workspace_yaml.is_file():
            try:
                with open(workspace_yaml, encoding="utf-8") as f:
                    meta = yaml.safe_load(f) or {}
            except (OSError, yaml.YAMLError):
                meta = {}

        turns = []
        model = None
        current = None
        with open(events_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                kind = event.get("type")
                data = event.get("data") or {}
                if kind == "session.start":
                    model = data.get("selectedModel") or model
                elif kind == "user.message":
                    current = {
                        "timestamp": _iso_z(event.get("timestamp")),
                        "user": data.get("content") or "",
                        "parts": [],
                        "model": model,
                    }
                    turns.append(current)
                elif kind == "assistant.message" and current is not None:
                    text = data.get("content")
                    if isinstance(text, str) and text.strip():
                        current["parts"].append(text)

        for turn in turns:
            turn["assistant"] = "\n\n".join(turn.pop("parts"))
        turns = [t for t in turns if t["user"].strip() or t["assistant"].strip()]
        if not turns:
            continue

        session_id = meta.get("id") or events_path.parent.name
        timestamps = [t["timestamp"] for t in turns if t["timestamp"]]
        sessions.append(
            {
                "session_id": session_id,
                "title": _clean_title(meta.get("name")) or _title_from_header({}, turns),
                "created_at": _iso_z(meta.get("created_at")) or (timestamps[0] if timestamps else None),
                "updated_at": _iso_z(meta.get("updated_at")) or (timestamps[-1] if timestamps else None),
                "turns": turns,
                "jsonl_path": None,
                "jsonl_turns": 0,
                "store_turns": 0,
                "store_cwd": meta.get("cwd"),
                "store_summary": None,
                "workspace_hash": None,
                "workspace_folder": None,
                "origin": "agent",
                "sources": {"agent"},
            }
        )
    return sessions


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def find_jsonl_sessions(storage_root):
    """Return every chatSessions/*.jsonl under a workspaceStorage directory."""
    if not storage_root:
        return []
    storage_root = Path(storage_root)
    if not storage_root.is_dir():
        return []
    return sorted(storage_root.glob("*/chatSessions/*.jsonl"))


def _workspace_for(path):
    """Return (workspace_hash, workspace_folder) for a chatSessions file."""
    workspace_hash = path.parent.parent.name
    workspace_json = path.parent.parent / "workspace.json"
    folder = read_workspace_folder(workspace_json) if workspace_json.is_file() else None
    return workspace_hash, folder


def read_store_sessions(store_path):
    """Return {session_id: session dict} from the Copilot session store."""
    sessions = {}
    if not store_path or not Path(store_path).is_file():
        return sessions
    try:
        conn = sqlite3.connect(f"file:{Path(store_path).as_posix()}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except sqlite3.Error:
        return sessions
    try:
        meta = {}
        for row in conn.execute(
            "SELECT id, cwd, summary, created_at, updated_at FROM sessions"
        ):
            meta[row["id"]] = dict(row)
        turns_by_session = {}
        for row in conn.execute(
            "SELECT session_id, turn_index, user_message, assistant_response, timestamp"
            " FROM turns ORDER BY session_id, turn_index"
        ):
            turns_by_session.setdefault(row["session_id"], []).append(
                {
                    "timestamp": row["timestamp"],
                    "user": row["user_message"] or "",
                    "assistant": row["assistant_response"] or "",
                    "model": None,
                }
            )
    except sqlite3.Error:
        return sessions
    finally:
        conn.close()

    for session_id, turns in turns_by_session.items():
        info = meta.get(session_id, {})
        sessions[session_id] = {
            "session_id": session_id,
            "title": _clean_title(info.get("summary")) or "(untitled)",
            "created_at": info.get("created_at"),
            "updated_at": info.get("updated_at"),
            "turns": turns,
            "jsonl_path": None,
            "jsonl_turns": 0,
            "store_turns": len(turns),
            "store_cwd": info.get("cwd"),
            "store_summary": info.get("summary"),
            "sources": {"store"},
        }
    return sessions


def _turns_chars(turns):
    return sum(len(t["user"]) + len(t["assistant"]) for t in turns)


def collect_sessions(storage_root, store_path, source="auto", empty_window_dir=None, agent_dir=None):
    """Discover and merge sessions from every source, richest copy per id."""
    merged = {}

    def offer(candidate):
        current = merged.get(candidate["session_id"])
        if current is None:
            merged[candidate["session_id"]] = candidate
            return
        winner, loser = (
            (candidate, current)
            if (len(candidate["turns"]), _turns_chars(candidate["turns"]))
            > (len(current["turns"]), _turns_chars(current["turns"]))
            else (current, candidate)
        )
        winner["sources"] = current["sources"] | candidate["sources"]
        winner["jsonl_turns"] = max(current.get("jsonl_turns", 0), candidate.get("jsonl_turns", 0))
        winner["store_turns"] = max(current.get("store_turns", 0), candidate.get("store_turns", 0))
        winner["jsonl_path"] = current.get("jsonl_path") or candidate.get("jsonl_path")
        winner["store_cwd"] = current.get("store_cwd") or candidate.get("store_cwd")
        winner["store_summary"] = current.get("store_summary") or candidate.get("store_summary")
        winner["origin"] = current.get("origin") or candidate.get("origin")
        if not winner["title"].strip() or winner["title"] == "(untitled)":
            winner["title"] = loser["title"]
        winner["workspace_hash"] = (
            winner.get("workspace_hash") or loser.get("workspace_hash")
        )
        winner["workspace_folder"] = (
            winner.get("workspace_folder") or loser.get("workspace_folder")
        )
        merged[candidate["session_id"]] = winner

    if source in ("auto", "store"):
        for session in read_store_sessions(store_path).values():
            session["origin"] = "store"
            offer(session)

    if source in ("auto", "jsonl"):
        # Richest duplicate first, so the single-pass merge keeps the best copy
        candidates = []
        for path in find_jsonl_sessions(storage_root):
            session = parse_jsonl_session(path)
            if session is None or not session["turns"]:
                continue
            session["workspace_hash"], session["workspace_folder"] = _workspace_for(path)
            session["origin"] = "jsonl"
            candidates.append(session)
        candidates.sort(key=lambda s: (len(s["turns"]), _turns_chars(s["turns"])), reverse=True)
        for session in candidates:
            offer(session)
        for session in read_empty_window_sessions(empty_window_dir):
            session["origin"] = "empty_window"
            offer(session)

    if source == "auto":
        for session in read_agent_sessions(agent_dir):
            offer(session)

    for session in merged.values():
        folder = session.get("workspace_folder") or session.get("store_cwd")
        session["workspace"] = folder
        session["workspace_exists"] = bool(folder) and os.path.isdir(folder)
        session["trimmed"] = session.get("store_turns", 0) > session.get("jsonl_turns", 0) > 0
        session["truncated"] = _looks_truncated(session)
        session.setdefault("sources", set())
    return merged


def _looks_truncated(session):
    """True when the first kept message is well after the session started.

    Copilot trims older requests out of the JSONL replay log, so a large gap
    between creationDate and the first surviving message means history was
    dropped and cannot be recovered from these files.
    """
    created = _iso_z(session.get("created_at"))
    timestamps = [t["timestamp"] for t in session["turns"] if t.get("timestamp")]
    if not created or not timestamps:
        return False
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        first_dt = datetime.fromisoformat(min(timestamps).replace("Z", "+00:00"))
    except ValueError:
        return False
    return (first_dt - created_dt).total_seconds() > 3600


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _project_prefixes(config):
    """Configured projects, including import-only ones (they have no folder)."""
    entries = list(config.get("projects") or []) + list(config.get("import_projects") or [])
    return [p for p in entries if isinstance(p, dict)]


DRIVE_PREFIXES = {"s:": "s-drive", "x:": "x-drive", "o:": "o-drive", "z:": "z-drive", "c:": "c-drive"}


def sanitize_project_name(workspace):
    """Derive a readable project prefix from a workspace folder path."""
    if not workspace:
        return DEFAULT_PROJECT
    normalised = workspace.replace("/", "\\").rstrip("\\")
    name = normalised.rsplit("\\", 1)[-1].strip()
    if not name:
        return DEFAULT_PROJECT
    if name.lower() in DRIVE_PREFIXES:
        return DRIVE_PREFIXES[name.lower()]
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    slug = re.sub(r"-main$", "", slug)
    # Cap keeps display sane without mangling long folder names
    # (was 18, which truncated e.g. tradingview-indicators -> tradingview-indica)
    return slug[:36].strip("-") or DEFAULT_PROJECT


def suggest_project(workspace, projects):
    """Suggest a project prefix: a configured project if one matches, else the folder."""
    if not workspace:
        return DEFAULT_PROJECT
    normalised = workspace.replace("/", "\\").lower().rstrip("\\")
    base = normalised.rsplit("\\", 1)[-1]
    for project in projects:
        folder_name = (project.get("folder_name") or "").lower()
        prefix = project.get("prefix") or DEFAULT_PROJECT
        if folder_name and (base == folder_name or f"\\{folder_name}" in normalised):
            return prefix
    return sanitize_project_name(workspace)


def imported_session_ids(db_path):
    """Return session ids already present in the brain, or an empty set."""
    if not db_path or not os.path.isfile(db_path):
        return set()
    try:
        conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return set()
    try:
        return {
            row[0]
            for row in conn.execute("SELECT session_id FROM sys_sessions WHERE source LIKE 'copilot%'")
        }
    except sqlite3.Error:
        return set()
    finally:
        conn.close()


def build_scan_rows(sessions, config, db_path):
    """Turn merged sessions into report rows."""
    projects = _project_prefixes(config)
    existing = imported_session_ids(db_path)
    rows = []
    for session in sessions.values():
        workspace = session.get("workspace")
        workspace_name = workspace.replace("/", "\\").rstrip("\\").rsplit("\\", 1)[-1] if workspace else ""
        tags = []
        if workspace and not session["workspace_exists"]:
            tags.append("orphaned")
        rows.append(
            {
                "session_id": session["session_id"],
                "date": (session.get("created_at") or "")[:10] or "unknown",
                "turns": len(session["turns"]),
                "project": suggest_project(workspace, projects),
                "suggested_folder": _clean_title(workspace_name, 60),
                "tags": ", ".join(tags),
                "status": "IMPORTED" if f"copilot_{session['session_id']}" in existing else "NEW",
                "trimmed": "yes" if session.get("trimmed") else "",
                "truncated": "yes" if session.get("truncated") else "",
                "sources": "+".join(sorted(session.get("sources") or [])),
                "workspace_name": workspace_name,
                "workspace": workspace or "",
                "workspace_exists": "yes" if session["workspace_exists"] else ("no" if workspace else ""),
                "title": session["title"],
            }
        )
    rows.sort(key=lambda r: (r["date"], r["title"]), reverse=True)
    return rows


def print_scan_report(rows, sessions, source_label):
    total_turns = sum(r["turns"] for r in rows)
    new_rows = [r for r in rows if r["status"] == "NEW"]
    trimmed = [r for r in rows if r["trimmed"]]
    orphaned = [r for r in rows if "orphaned" in r["tags"]]

    print(f"\nCopilot Chat scan ({source_label})")
    print("=" * 60)
    print(f"  Sessions with content : {len(rows)}")
    print(f"  Turns                 : {total_turns}")
    print(f"  New                   : {len(new_rows)}")
    print(f"  Already imported      : {len(rows) - len(new_rows)}")
    print(f"  Trimmed in JSONL      : {len(trimmed)}")
    print(f"  Orphaned workspace    : {len(orphaned)}")

    by_source = {}
    for row in rows:
        by_source[row["sources"]] = by_source.get(row["sources"], 0) + 1
    if by_source:
        print("\n  By source:")
        for label, count in sorted(by_source.items(), key=lambda kv: -kv[1]):
            print(f"    {label:<14} {count:>4} sessions")

    if rows:
        print("\n  Newest 10:")
        for row in new_rows[:10] or rows[:10]:
            flag = "!" if "orphaned" in row["tags"] else " "
            where = row.get("workspace_name") or "?"
            print(
                f"    {flag} {row['date']}  {row['turns']:>4} turns  "
                f"{where[:18]:<18} {row['title'][:46]}"
            )
    if trimmed:
        print(
            yellow(
                f"\n  Note: {len(trimmed)} session(s) are trimmed in the JSONL;"
                " the store holds more turns."
            )
        )


def write_csv(rows, output_path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else [
        "session_id", "date", "turns", "project", "suggested_folder", "tags", "status",
        "trimmed", "truncated", "sources", "workspace_name", "workspace",
        "workspace_exists", "title",
    ]
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _turn_uuid(session_key, index, role):
    """Deterministic uuid so re-imports are idempotent."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"claude-brain:copilot:{session_key}:{index}:{role}"))


def _session_rows(session):
    """Return the transcript rows for one session, in conversation order."""
    session_key = f"copilot_{session['session_id']}"
    rows = []
    for index, turn in enumerate(session["turns"]):
        timestamp = turn.get("timestamp")
        user_uuid = _turn_uuid(session_key, index, "user")
        if turn["user"].strip():
            rows.append(
                {
                    "uuid": user_uuid,
                    "parent_uuid": None,
                    "type": "user",
                    "role": "user",
                    "content": turn["user"],
                    "timestamp": timestamp,
                }
            )
        if turn["assistant"].strip():
            rows.append(
                {
                    "uuid": _turn_uuid(session_key, index, "assistant"),
                    "parent_uuid": user_uuid,
                    "type": "assistant",
                    "role": "assistant",
                    "content": turn["assistant"],
                    "timestamp": timestamp,
                }
            )
    return rows


def resolve_sources(args):
    """Return (storage_root, store_path, empty_window_dir, agent_dir, label)."""
    if args.root:
        return (
            Path(args.root),
            Path(args.store) if args.store else None,
            Path(args.empty_window) if args.empty_window else None,
            Path(args.agent_dir) if args.agent_dir else agent_state_dir(),
            str(args.root),
        )
    roots = default_data_roots()
    if args.store:
        return None, Path(args.store), None, None, str(args.store)
    if not roots:
        return None, None, None, None, ""
    primary = roots[0]
    return (
        primary["storage"],
        primary["store"],
        primary["empty_window"],
        Path(args.agent_dir) if args.agent_dir else agent_state_dir(),
        f"{primary['variant']} ({len(roots)} variant(s) found)",
    )


def cmd_import(args):
    """Import scanned sessions into the brain, guided by a mapping CSV."""
    if not args.map:
        print(red("--map <csv_file> is required for import mode"))
        print("Run --scan first to generate it.")
        return 1

    map_path = Path(args.map)
    if not map_path.exists():
        print(red(f"Mapping file not found: {map_path}"))
        return 1

    config, db_path = load_config()
    if not db_path or not os.path.isfile(db_path):
        print(red(f"Database not found: {db_path}"))
        return 1

    mapping = {}
    with open(map_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("session_id"):
                mapping[row["session_id"]] = {
                    "project": (row.get("project") or DEFAULT_PROJECT).strip() or DEFAULT_PROJECT,
                    "tags": (row.get("tags") or "").strip(),
                }
    print(f"\nMapping file: {map_path.name} ({len(mapping)} sessions)")

    storage_root, store_path, empty_window_dir, agent_dir, label = resolve_sources(args)
    sessions = collect_sessions(
        storage_root, store_path, source=args.source,
        empty_window_dir=empty_window_dir, agent_dir=agent_dir,
    )
    print(f"Copilot data: {label or 'session store'}")

    conn = sqlite3.connect(db_path)
    try:
        existing_uuids = {
            row[0] for row in conn.execute(
                "SELECT uuid FROM transcripts WHERE session_id LIKE 'copilot_%'"
            )
        }
        existing_sessions = {
            row[0] for row in conn.execute(
                "SELECT session_id FROM sys_sessions WHERE session_id LIKE 'copilot_%'"
            )
        }

        selected = [(sid, sessions[sid]) for sid in mapping if sid in sessions]
        missing = [sid for sid in mapping if sid not in sessions]
        total_new = total_dup = 0
        plan = []
        for sid, session in selected:
            rows = _session_rows(session)
            new_rows = [r for r in rows if r["uuid"] not in existing_uuids]
            total_new += len(new_rows)
            total_dup += len(rows) - len(new_rows)
            plan.append((sid, session, rows, new_rows))

        print(f"\n  Sessions in mapping : {len(mapping)}")
        print(f"  Found on disk       : {len(selected)}")
        if missing:
            print(f"  Not found on disk   : {len(missing)}")
        print(f"  Transcript rows     : {total_new + total_dup}")
        print(f"    new               : {total_new}")
        print(f"    already present   : {total_dup}")

        if args.dry_run:
            print(f"\n{yellow('DRY RUN')} -- nothing written")
            for sid, session, rows, new_rows in sorted(
                plan, key=lambda p: len(p[3]), reverse=True
            )[:10]:
                print(
                    f"    {session['title'][:50]:<50} "
                    f"{len(new_rows):>4} new rows  [{mapping[sid]['project']}]"
                )
            return 0

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # A re-import must never undo a project or tags the user chose in the CSV,
        # unless --update-metadata says so explicitly.
        update_cols = (
            "started_at=excluded.started_at, ended_at=excluded.ended_at, cwd=excluded.cwd,"
            " model=excluded.model, message_count=excluded.message_count, notes=excluded.notes"
        )
        if getattr(args, "update_metadata", False):
            update_cols += ", project=excluded.project, tags=excluded.tags"
        session_sql = f"""INSERT INTO sys_sessions
                   (session_id, project, started_at, ended_at, cwd, claude_version, model,
                    source, message_count, created_at, notes, tags)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(session_id) DO UPDATE SET {update_cols}"""
        imported_sessions = 0
        for sid, session, rows, new_rows in plan:
            meta = mapping[sid]
            session_key = f"copilot_{sid}"
            source = "copilot_agent" if session.get("origin") == "agent" else "copilot_chat"
            models = [t.get("model") for t in session["turns"] if t.get("model")]
            notes = []
            if session.get("truncated"):
                first = min((t["timestamp"] for t in session["turns"] if t.get("timestamp")), default=None)
                notes.append(
                    "history truncated by Copilot"
                    f" (session started {(session.get('created_at') or '?')[:10]},"
                    f" first kept message {(first or '?')[:10]})"
                )
            if session.get("trimmed"):
                notes.append(
                    f"JSONL held {session.get('jsonl_turns')} turns, store held"
                    f" {session.get('store_turns')}; richest source imported"
                )
            if not session.get("workspace"):
                notes.append("no workspace folder recorded")

            conn.execute(
                session_sql,
                (
                    session_key,
                    meta["project"],
                    session.get("created_at"),
                    session.get("updated_at"),
                    session.get("workspace"),
                    None,
                    models[0] if models else None,
                    source,
                    len(rows),
                    now,
                    "; ".join(notes) if notes else None,
                    meta["tags"] or None,
                ),
            )
            conn.executemany(
                """INSERT OR IGNORE INTO transcripts
                   (session_id, project, uuid, parent_uuid, type, role, content, model,
                    timestamp, is_subagent, created_at, source)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
                [
                    (
                        session_key,
                        meta["project"],
                        r["uuid"],
                        r["parent_uuid"],
                        r["type"],
                        r["role"],
                        r["content"],
                        models[0] if models else None,
                        r["timestamp"],
                        now,
                        source,
                    )
                    for r in new_rows
                ],
            )
            if getattr(args, "update_metadata", False):
                conn.execute(
                    "UPDATE transcripts SET project = ? WHERE session_id = ? AND project != ?",
                    (meta["project"], session_key, meta["project"]),
                )
            if new_rows:
                imported_sessions += 1
            existing_uuids.update(r["uuid"] for r in new_rows)

        conn.commit()

        total_transcripts = conn.execute(
            "SELECT COUNT(*) FROM transcripts WHERE session_id LIKE 'copilot_%'"
        ).fetchone()[0]
        total_sessions = conn.execute(
            "SELECT COUNT(*) FROM sys_sessions WHERE session_id LIKE 'copilot_%'"
        ).fetchone()[0]
    finally:
        conn.close()

    print(f"\n  Sessions written    : {imported_sessions} new, {total_sessions} total")
    print(f"  Transcript rows new : {total_new}")
    print(f"  Transcript rows tot : {total_transcripts}")
    print(f"\n  Verify with: python3 scripts/brain_search.py \"copilot\"")
    return 0


def cmd_report(args):
    """List Copilot sessions that are in the brain."""
    config, db_path = load_config()
    if not db_path or not os.path.isfile(db_path):
        print(red(f"Database not found: {db_path}"))
        return 1

    conn = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro", uri=True)
    try:
        sessions = conn.execute(
            """SELECT session_id, project, started_at, message_count, source, tags, notes
               FROM sys_sessions WHERE source LIKE 'copilot%'
               ORDER BY started_at DESC"""
        ).fetchall()
        titles = {}
        for session_id, content in conn.execute(
            """SELECT session_id, content FROM transcripts
               WHERE session_id LIKE 'copilot_%' AND role = 'user'
               ORDER BY session_id, timestamp, id"""
        ):
            if session_id not in titles:
                first = " ".join((content or "").split())
                if first:
                    titles[session_id] = first[:70]
    finally:
        conn.close()

    if not sessions:
        print("No Copilot sessions imported yet.")
        return 0

    by_project = {}
    for session in sessions:
        by_project.setdefault(session[1] or "?", []).append(session)

    lines = ["# Imported Copilot conversations", ""]
    lines.append(f"{len(sessions)} sessions across {len(by_project)} projects.")
    lines.append("")
    total_turns = 0
    for project in sorted(by_project, key=lambda p: (-len(by_project[p]), p or "")):
        group = by_project[project]
        turns = sum(s[3] or 0 for s in group)
        total_turns += turns
        lines.append(f"## {project} — {len(group)} sessions, {turns} messages")
        lines.append("")
        lines.append("| date | msgs | title |")
        lines.append("|---|---|---|")
        for session in group:
            date = (session[2] or "")[:10] or "?"
            title = titles.get(session[0], "(no user message)")
            title = title.replace("|", "\\|")
            lines.append(f"| {date} | {session[3] or 0} | {title} |")
        lines.append("")

    text = "\n".join(lines)
    print(f"Copilot sessions: {len(sessions)} across {len(by_project)} projects, {total_turns} messages\n")
    for project in sorted(by_project, key=lambda p: -len(by_project[p])):
        group = by_project[project]
        print(f"  {project:<22} {len(group):>3} sessions")
    print()
    print(f"  {len(sessions)} sessions in the brain")

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n", encoding="utf-8")
        print(f"\n  Full list written to: {out}")
    return 0


def cmd_scan(args):
    config, db_path = load_config()

    if args.root:
        storage_root = Path(args.root)
        store_path = Path(args.store) if args.store else None
        empty_window_dir = Path(args.empty_window) if args.empty_window else None
        agent_dir = Path(args.agent_dir) if args.agent_dir else None
        source_label = str(storage_root)
    else:
        roots = default_data_roots()
        if not roots and not args.store:
            print(red("No Copilot data found."))
            print("Looked for workspaceStorage and session-store.db under %APPDATA%.")
            return 1
        if args.store:
            storage_root = None
            store_path = Path(args.store)
            empty_window_dir = None
            source_label = str(store_path)
        else:
            variant, primary = roots[0]["variant"], roots[0]
            storage_root = primary["storage"]
            store_path = primary["store"]
            empty_window_dir = primary["empty_window"]
            source_label = f"{variant} ({len(roots)} variant(s) found)"
        agent_dir = Path(args.agent_dir) if args.agent_dir else agent_state_dir()

    print(f"Scanning Copilot Chat history: {source_label}")
    sessions = collect_sessions(
        storage_root, store_path, source=args.source,
        empty_window_dir=empty_window_dir, agent_dir=agent_dir,
    )
    rows = build_scan_rows(sessions, config, db_path)

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    print_scan_report(rows, sessions, source_label)

    output_path = Path(args.output) if args.output else ROOT_DIR / "imports" / "copilot_import_map.csv"
    write_csv(rows, output_path)
    print(f"\n  Mapping written to: {output_path}")
    print(dim("  Review the project column, then import with --map (next phase)."))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Import GitHub Copilot Chat history into claude-brain"
    )
    parser.add_argument("--scan", action="store_true", help="Discover sessions and write a mapping file")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Import using a reviewed mapping file")
    parser.add_argument("--report", action="store_true", help="List Copilot sessions already in the brain")
    parser.add_argument("--map", metavar="FILE", help="Mapping CSV from --scan")
    parser.add_argument("--dry-run", action="store_true", help="Show what --import would write")
    parser.add_argument(
        "--update-metadata",
        action="store_true",
        help="Also overwrite project and tags of sessions that are already imported",
    )
    parser.add_argument("--root", metavar="DIR", help="workspaceStorage directory (default: auto-detect)")
    parser.add_argument("--store", metavar="DB", help="Path to session-store.db")
    parser.add_argument("--empty-window", metavar="DIR", help="emptyWindowChatSessions directory")
    parser.add_argument("--agent-dir", metavar="DIR", help="Agent-host session-state directory")
    parser.add_argument(
        "--source",
        choices=["auto", "jsonl", "store"],
        default="auto",
        help="Which source(s) to read (default: auto = all)",
    )
    parser.add_argument("--output", metavar="FILE", help="Mapping file to write")
    parser.add_argument("--json", action="store_true", help="Print rows as JSON")
    args = parser.parse_args()

    if args.do_import:
        return cmd_import(args)
    if args.report:
        return cmd_report(args)
    if args.scan:
        return cmd_scan(args)
    parser.print_help()
    print("\nUse --scan first, then --import --map <file>.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
