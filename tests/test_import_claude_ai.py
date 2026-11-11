#!/usr/bin/env python3
"""Tests for scripts/import_claude_ai.py - export format normalization."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import import_claude_ai as ic  # noqa: E402


def exporter_export():
    return {
        "metadata": {
            "title": "Laptop access permissions",
            "dates": {
                "created": "9/24/2026 13:42:55",
                "updated": "9/24/2026 13:44:04",
                "exported": "11/11/2026 13:27:55",
            },
            "link": "https://claude.ai/chat/3519ff1e-9465-4b21-8cfc-554fe2e8a258",
        },
        "messages": [
            {"role": "human", "time": "9/24/2026 13:42:55", "say": "hi there"},
            {"role": "assistant", "time": "9/24/2026 13:44:04", "say": "hello"},
        ],
    }


def test_legacy_format_passes_through():
    legacy = {"uuid": "u1", "name": "n", "chat_messages": [{"uuid": "m1"}]}
    assert ic.normalize_export(legacy) is legacy


def test_exporter_format_is_normalized():
    out = ic.normalize_export(exporter_export())
    assert out["uuid"] == "3519ff1e-9465-4b21-8cfc-554fe2e8a258"
    assert out["name"] == "Laptop access permissions"
    assert out["created_at"] == "2026-09-24T13:42:55"
    msgs = out["chat_messages"]
    assert [m["sender"] for m in msgs] == ["human", "assistant"]
    assert [m["text"] for m in msgs] == ["hi there", "hello"]
    assert msgs[0]["uuid"] != msgs[1]["uuid"]
    assert msgs[1]["parent_message_uuid"] == msgs[0]["uuid"]
    assert msgs[0]["created_at"] == "2026-09-24T13:42:55"


def test_exporter_missing_link_generates_session_id():
    data = exporter_export()
    data["metadata"].pop("link")
    out = ic.normalize_export(data)
    assert out["uuid"] and out["uuid"].startswith("3519ff1e") is False
    assert len(out["uuid"]) == 36


def test_unrecognized_shape_is_left_alone():
    assert ic.normalize_export({"foo": 1}) == {"foo": 1}
    assert ic.normalize_export({"metadata": {}, "messages": "nope"}) == {
        "metadata": {},
        "messages": "nope",
    }
