#!/usr/bin/env python3
"""Tests for scripts/import_copilot.py - JSONL replay, dedupe and scan."""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import import_copilot as ic  # noqa: E402


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def header(session_id, title=None, requests=None, created=1762000000000):
    value = {
        "version": 3,
        "creationDate": created,
        "initialLocation": "panel",
        "sessionId": session_id,
        "requests": requests or [],
    }
    if title is not None:
        value["customTitle"] = title
    return {"kind": 0, "v": value}


def request(text, md_parts, ts=1762000000000, hidden=False):
    req = {
        "requestId": f"r-{ts}",
        "timestamp": ts,
        "message": {"text": text, "parts": []},
        "response": [{"value": md, "supportThemeIcons": False} for md in md_parts],
    }
    if hidden:
        req["hiddenFromTranscript"] = True
    return req


def write_session(tmp_path, session_id, records, workspace_hash="aaaa", workspace_folder=None):
    ws_dir = tmp_path / workspace_hash
    chat_dir = ws_dir / "chatSessions"
    chat_dir.mkdir(parents=True, exist_ok=True)
    if workspace_folder is not None:
        (ws_dir / "workspace.json").write_text(
            json.dumps({"folder": "file:///" + workspace_folder.replace("\\", "/").replace(":", "%3A")}),
            encoding="utf-8",
        )
    path = chat_dir / f"{session_id}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------


def test_replay_applies_full_replacement(tmp_path):
    path = write_session(
        tmp_path,
        "s1",
        [
            header("s1", requests=[request("first", ["A"])]),
            {"kind": 2, "k": ["requests"], "v": [request("second", ["B"])]},
        ],
    )
    header_state = ic.replay_jsonl(path)
    turns = ic.extract_turns(header_state)
    assert len(turns) == 1
    assert turns[0]["user"] == "second"
    assert turns[0]["assistant"] == "B"


def test_replay_applies_field_patch(tmp_path):
    path = write_session(
        tmp_path,
        "s1",
        [
            header("s1", requests=[request("q", ["A"])]),
            {"kind": 1, "k": ["requests", 0, "response"], "v": [{"value": "patched"}]},
        ],
    )
    turns = ic.extract_turns(ic.replay_jsonl(path))
    assert turns[0]["assistant"] == "patched"


def test_replay_tolerates_broken_line(tmp_path):
    path = write_session(tmp_path, "s1", [header("s1", requests=[request("q", ["A"])])])
    with open(path, "a", encoding="utf-8") as f:
        f.write('{"kind": 2, "k": ["requests"], "v": [{"trunc\n')
    turns = ic.extract_turns(ic.replay_jsonl(path))
    assert len(turns) == 1 and turns[0]["assistant"] == "A"


def test_only_kindless_parts_become_assistant_text(tmp_path):
    req = request("q", [])
    req["response"] = [
        {"kind": "thinking", "value": "internal reasoning"},
        {"value": "Visible "},
        {"kind": "toolInvocationSerialized", "invocationMessage": {"value": "tool"}},
        {"value": "answer"},
    ]
    path = write_session(tmp_path, "s1", [header("s1", requests=[req])])
    turns = ic.extract_turns(ic.replay_jsonl(path))
    assert turns[0]["assistant"] == "Visible answer"


def test_hidden_requests_are_skipped(tmp_path):
    path = write_session(
        tmp_path,
        "s1",
        [header("s1", requests=[request("shown", ["A"]), request("hidden", ["B"], hidden=True)])],
    )
    turns = ic.extract_turns(ic.replay_jsonl(path))
    assert [t["user"] for t in turns] == ["shown"]


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------


def test_custom_title_wins_and_falls_back(tmp_path):
    titled = write_session(tmp_path, "s1", [header("s1", "My title", [request("q", ["a"])])])
    assert ic.parse_jsonl_session(titled)["title"] == "My title"

    untitled = write_session(
        tmp_path, "s2", [header("s2", requests=[request("First line\nsecond", ["a"])])], workspace_hash="bbbb"
    )
    assert ic.parse_jsonl_session(untitled)["title"] == "First line"


def test_timestamps_are_iso_utc(tmp_path):
    path = write_session(tmp_path, "s1", [header("s1", requests=[request("q", ["a"], ts=1762000000000)])])
    session = ic.parse_jsonl_session(path)
    assert session["created_at"].endswith("Z")
    assert session["turns"][0]["timestamp"] == session["updated_at"]


def test_workspace_folder_and_orphan_detection(tmp_path):
    missing = tmp_path / "gone"
    path = write_session(
        tmp_path, "s1", [header("s1", requests=[request("q", ["a"])])], workspace_folder=str(missing)
    )
    session = ic.parse_jsonl_session(path)
    session["workspace_hash"], session["workspace_folder"] = ic._workspace_for(path)
    merged = ic.collect_sessions(tmp_path, None)
    row = ic.build_scan_rows(merged, {"projects": []}, None)[0]
    assert row["workspace"] == str(missing)
    assert row["workspace_exists"] == "no"
    assert "orphaned" in row["tags"]


# ---------------------------------------------------------------------------
# Merge / dedupe
# ---------------------------------------------------------------------------


def test_dedupe_keeps_richest_copy(tmp_path):
    write_session(tmp_path, "s1", [header("s1", requests=[request("only", ["one"])])], "aaaa")
    write_session(
        tmp_path,
        "s1",
        [header("s1", requests=[request("one", ["a"]), request("two", ["b"], ts=1762000001000)])],
        "bbbb",
    )
    merged = ic.collect_sessions(tmp_path, None)
    assert len(merged) == 1
    assert len(merged["s1"]["turns"]) == 2


def make_store(path, session_id, turns, cwd=None):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, cwd TEXT, repository TEXT,
            host_type TEXT, branch TEXT, summary TEXT, agent_name TEXT, agent_description TEXT,
            created_at TEXT, updated_at TEXT);
        CREATE TABLE IF NOT EXISTS turns (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
            turn_index INTEGER, user_message TEXT, assistant_response TEXT, timestamp TEXT);
        """
    )
    conn.execute(
        "INSERT OR REPLACE INTO sessions (id, cwd, summary, created_at, updated_at)"
        " VALUES (?,?,?,?,?)",
        (session_id, cwd, "Stored summary", "2026-11-01T10:00:00.000Z", "2026-11-01T11:00:00.000Z"),
    )
    conn.executemany(
        "INSERT INTO turns (session_id, turn_index, user_message, assistant_response, timestamp)"
        " VALUES (?,?,?,?,?)",
        [(session_id, i, f"u{i}", f"a{i}", f"2026-11-01T10:0{i}:00.000Z") for i in range(turns)],
    )
    conn.commit()
    conn.close()


def test_store_wins_when_jsonl_is_trimmed(tmp_path):
    write_session(tmp_path, "s1", [header("s1", requests=[request("u0", ["a0"])])])
    store = tmp_path / "session-store.db"
    make_store(store, "s1", turns=5, cwd=str(tmp_path))

    merged = ic.collect_sessions(tmp_path, store)
    session = merged["s1"]
    assert len(session["turns"]) == 5
    assert session["store_turns"] == 5
    assert session["jsonl_turns"] == 1
    assert session["trimmed"] is True
    assert session["sources"] == {"jsonl", "store"}


def test_store_only_sessions_are_included(tmp_path):
    (tmp_path / "empty").mkdir()
    store = tmp_path / "session-store.db"
    make_store(store, "only-store", turns=2, cwd=str(tmp_path))
    merged = ic.collect_sessions(tmp_path, store)
    assert list(merged) == ["only-store"]
    assert merged["only-store"]["title"] == "Stored summary"


# ---------------------------------------------------------------------------
# Project suggestion / scan output
# ---------------------------------------------------------------------------


def test_suggest_project_matches_folder_name():
    projects = [{"folder_name": "claude-brain", "prefix": "brain"}]
    assert ic.suggest_project(r"C:\GIT\claude-brain", projects) == "brain"
    assert ic.suggest_project(r"C:\GIT\claude-brain\sub", projects) == "brain"
    assert ic.suggest_project(r"C:\GIT\other", projects) == "other"
    assert ic.suggest_project(None, projects) == ic.DEFAULT_PROJECT


def test_sanitize_project_name():
    assert ic.sanitize_project_name(r"C:\GIT\Tradingview_indicators") == "tradingview-indica"
    assert ic.sanitize_project_name(r"C:\GIT\Browse-CopilotChats-main") == "browse-copilotchat"
    assert ic.sanitize_project_name("s:\\") == "s-drive"
    assert ic.sanitize_project_name("") == ic.DEFAULT_PROJECT


def test_scan_writes_csv(tmp_path, monkeypatch):
    write_session(tmp_path, "s1", [header("s1", "Title A", [request("q", ["a"])])])
    out = tmp_path / "map.csv"
    monkeypatch.setattr(
        sys, "argv", ["import_copilot.py", "--scan", "--root", str(tmp_path), "--output", str(out)]
    )
    assert ic.main() == 0
    assert out.is_file()
    rows = list(__import__("csv").DictReader(open(out, encoding="utf-8")))
    assert len(rows) == 1
    assert rows[0]["session_id"] == "s1"
    assert rows[0]["status"] == "NEW"
    assert rows[0]["turns"] == "1"


def test_imported_sessions_are_marked(tmp_path):
    write_session(tmp_path, "s1", [header("s1", requests=[request("q", ["a"])])])
    db = tmp_path / "brain.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE sys_sessions (session_id TEXT, source TEXT)")
    conn.execute("INSERT INTO sys_sessions VALUES ('copilot_s1', 'copilot_chat')")
    conn.commit()
    conn.close()

    merged = ic.collect_sessions(tmp_path, None)
    row = ic.build_scan_rows(merged, {"projects": []}, str(db))[0]
    assert row["status"] == "IMPORTED"


def test_empty_session_is_ignored(tmp_path):
    write_session(tmp_path, "s1", [header("s1", requests=[])])
    assert ic.collect_sessions(tmp_path, None) == {}


# ---------------------------------------------------------------------------
# Inline references, agent host, empty-window chats
# ---------------------------------------------------------------------------


def test_inline_references_are_rendered_as_labels(tmp_path):
    req = request("q", [])
    req["response"] = [
        {"value": "die lijst heb ik uit "},
        {"kind": "inlineReference", "inlineReference": {"name": "pos", "kind": 12}},
        {"value": " gehaald en "},
        {"kind": "inlineReference", "inlineReference": {"fsPath": "c:\\GIT\\x\\batch_update.py"}},
    ]
    path = write_session(tmp_path, "s1", [header("s1", requests=[req])])
    turns = ic.extract_turns(ic.replay_jsonl(path))
    assert turns[0]["assistant"] == "die lijst heb ik uit [pos] gehaald en [batch_update.py]"


def write_agent_session(base, session_id, model="deepseek-v4-test", cwd=None):
    folder = base / session_id
    folder.mkdir(parents=True)
    import yaml

    (folder / "workspace.yaml").write_text(
        yaml.safe_dump(
            {
                "id": session_id,
                "cwd": cwd,
                "repository": "owner/repo",
                "name": "Agent chat title",
                "created_at": "2026-11-11T10:00:00.000Z",
                "updated_at": "2026-11-11T10:05:00.000Z",
            }
        ),
        encoding="utf-8",
    )
    events = [
        {"type": "session.start", "data": {"sessionId": session_id, "selectedModel": model}},
        {"type": "user.message", "data": {"content": "vraag een"}, "timestamp": "2026-11-11T10:00:00.000Z"},
        {"type": "assistant.message", "data": {"content": "deel "}, "timestamp": "2026-11-11T10:00:01.000Z"},
        {"type": "assistant.message", "data": {"content": ""}, "timestamp": "2026-11-11T10:00:01.500Z"},
        {"type": "assistant.message", "data": {"content": "antwoord"}, "timestamp": "2026-11-11T10:00:02.000Z"},
        {"type": "tool.execution_start", "data": {"name": "read"}},
        {"type": "user.message", "data": {"content": "vraag twee"}, "timestamp": "2026-11-11T10:01:00.000Z"},
        {"type": "assistant.message", "data": {"content": "tweede antwoord"}, "timestamp": "2026-11-11T10:01:01.000Z"},
    ]
    (folder / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8"
    )
    return folder


def test_agent_sessions_join_streamed_assistant_chunks(tmp_path):
    base = tmp_path / "agent"
    write_agent_session(base, "a1", cwd=str(tmp_path))
    sessions = ic.read_agent_sessions(base)
    assert len(sessions) == 1
    session = sessions[0]
    assert session["title"] == "Agent chat title"
    assert len(session["turns"]) == 2
    assert session["turns"][0]["assistant"] == "deel \n\nantwoord"
    assert session["turns"][0]["model"] == "deepseek-v4-test"
    assert session["sources"] == {"agent"}


def test_empty_window_sessions_are_collected(tmp_path):
    empty = tmp_path / "emptyWindowChatSessions"
    empty.mkdir()
    records = [header("e1", "Empty window chat", [request("q", ["a"])])]
    (empty / "e1.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    sessions = ic.collect_sessions(None, None, empty_window_dir=empty)
    assert list(sessions) == ["e1"]
    assert sessions["e1"]["workspace"] is None


def test_truncated_detection(tmp_path):
    # created 2026-01-01, first kept message months later
    created = 1767225600000  # 2026-01-01T00:00:00Z
    later = 1780000000000
    path = write_session(tmp_path, "s1", [header("s1", requests=[request("q", ["a"], ts=later)], created=created)])
    session = ic.parse_jsonl_session(path)
    assert ic._looks_truncated(session) is True

    path2 = write_session(
        tmp_path, "s2", [header("s2", requests=[request("q", ["a"], ts=created + 5000)], created=created)],
        workspace_hash="bbbb",
    )
    assert ic._looks_truncated(ic.parse_jsonl_session(path2)) is False


# ---------------------------------------------------------------------------
# Import
# ---------------------------------------------------------------------------


def make_brain_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE sys_sessions (session_id TEXT PRIMARY KEY, project TEXT, started_at TEXT,
            ended_at TEXT, cwd TEXT, claude_version TEXT, model TEXT, source TEXT,
            message_count INTEGER DEFAULT 0, created_at TEXT, quality_score INTEGER,
            quality_tags TEXT, notes TEXT, tags TEXT);
        CREATE TABLE transcripts (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT,
            project TEXT, uuid TEXT UNIQUE, parent_uuid TEXT, type TEXT, subtype TEXT, role TEXT,
            content TEXT, model TEXT, timestamp TEXT, token_input INTEGER, token_output INTEGER,
            stop_reason TEXT, is_subagent INTEGER DEFAULT 0, source_file TEXT, raw_json TEXT,
            created_at TEXT, source TEXT);
        """
    )
    conn.commit()
    conn.close()


def test_session_rows_skip_empty_assistant(tmp_path):
    req = request("alleen een vraag", [])
    req["response"] = [{"kind": "thinking", "value": "hmm"}]
    path = write_session(tmp_path, "s1", [header("s1", requests=[req])])
    session = ic.parse_jsonl_session(path)
    rows = ic._session_rows(session)
    assert [r["role"] for r in rows] == ["user"]
    assert rows[0]["type"] == "user"


def test_turn_uuid_is_deterministic():
    a = ic._turn_uuid("copilot_x", 3, "assistant")
    b = ic._turn_uuid("copilot_x", 3, "assistant")
    assert a == b
    assert a != ic._turn_uuid("copilot_x", 4, "assistant")


def test_import_writes_rows_and_is_idempotent(tmp_path, monkeypatch):
    write_session(tmp_path, "s1", [header("s1", "Titel", [request("vraag", ["antwoord"])])])
    db = tmp_path / "brain.db"
    make_brain_db(db)
    mapping = tmp_path / "map.csv"
    mapping.write_text(
        "session_id,date,turns,project,tags,status,title\ns1,2026-11-01,1,brain,,NEW,Titel\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(ic, "load_config", lambda: ({"projects": []}, str(db)))

    args = type(
        "A",
        (),
        {
            "map": str(mapping), "root": str(tmp_path), "store": None, "empty_window": None,
            "agent_dir": str(tmp_path / "none"), "source": "jsonl", "dry_run": False,
        },
    )()
    assert ic.cmd_import(args) == 0

    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == 2
    session = conn.execute(
        "SELECT project, source, message_count, notes FROM sys_sessions"
    ).fetchone()
    assert session[0] == "brain"
    assert session[1] == "copilot_chat"
    assert session[2] == 2
    conn.close()

    # Second run must not duplicate anything
    assert ic.cmd_import(args) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM sys_sessions").fetchone()[0] == 1
    conn.close()


def test_reimport_keeps_project_unless_update_metadata(tmp_path, monkeypatch):
    """A second import must not undo a project the user reviewed."""
    write_session(tmp_path, "s1", [header("s1", requests=[request("vraag", ["antwoord"])])])
    db = tmp_path / "brain.db"
    make_brain_db(db)
    mapping = tmp_path / "map.csv"
    mapping.write_text("session_id,project\ns1,brain\n", encoding="utf-8")
    monkeypatch.setattr(ic, "load_config", lambda: ({"projects": []}, str(db)))

    def args_for(project, update=False):
        mapping.write_text(f"session_id,project\ns1,{project}\n", encoding="utf-8")
        return type(
            "A",
            (),
            {
                "map": str(mapping), "root": str(tmp_path), "store": None, "empty_window": None,
                "agent_dir": str(tmp_path / "none"), "source": "jsonl", "dry_run": False,
                "update_metadata": update,
            },
        )()

    assert ic.cmd_import(args_for("brain")) == 0
    assert ic.cmd_import(args_for("oth")) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT project FROM sys_sessions").fetchone()[0] == "brain"
    conn.close()

    assert ic.cmd_import(args_for("oth", update=True)) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT project FROM sys_sessions").fetchone()[0] == "oth"
    conn.close()


def test_dry_run_writes_nothing(tmp_path, monkeypatch):
    write_session(tmp_path, "s1", [header("s1", requests=[request("vraag", ["antwoord"])])])
    db = tmp_path / "brain.db"
    make_brain_db(db)
    mapping = tmp_path / "map.csv"
    mapping.write_text("session_id,project\ns1,brain\n", encoding="utf-8")
    monkeypatch.setattr(ic, "load_config", lambda: ({"projects": []}, str(db)))
    args = type(
        "A",
        (),
        {
            "map": str(mapping), "root": str(tmp_path), "store": None, "empty_window": None,
            "agent_dir": str(tmp_path / "none"), "source": "jsonl", "dry_run": True,
        },
    )()
    assert ic.cmd_import(args) == 0
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0] == 0
    conn.close()
