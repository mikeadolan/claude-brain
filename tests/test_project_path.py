"""Tests for project path resolution (external projects, upstream issue #2)."""

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import project_path  # noqa: E402


def test_resolve_uses_root_when_no_path():
    project = {"folder_name": "my-project", "prefix": "mp"}
    assert project_path.resolve_project_path(project, "/brain") == os.path.join("/brain", "my-project")


def test_resolve_prefers_explicit_path():
    project = {"folder_name": "repo", "prefix": "rp", "path": "/elsewhere/repo"}
    assert project_path.resolve_project_path(project, "/brain") == "/elsewhere/repo"


def test_resolve_ignores_blank_path():
    project = {"folder_name": "repo", "prefix": "rp", "path": "   "}
    assert project_path.resolve_project_path(project, "/brain") == os.path.join("/brain", "repo")


def test_is_external():
    assert project_path.is_external({"path": "/elsewhere/repo"})
    assert not project_path.is_external({"path": "  "})
    assert not project_path.is_external({"folder_name": "repo"})


def test_detect_project_prefers_specific_nested_path():
    ingest = pytest.importorskip("ingest_jsonl")
    config = {
        "jsonl_project_mapping": {
            "parent": "par",
            "parent/child": "chi",
            "parent-child": "chi",
        }
    }
    mappings = ingest.build_project_mappings(config)
    # Claude Code encodes the cwd into the transcript folder name, so a nested
    # project shows up as one hyphenated segment.
    nested = r"C:\Users\me\.claude\projects\C--code-parent-child\s1.jsonl"
    plain = r"C:\Users\me\.claude\projects\C--code-parent\s1.jsonl"
    assert ingest.detect_project(nested, {"cwd": r"C:\code\parent\child"}, mappings) == "chi"
    assert ingest.detect_project(plain, {"cwd": r"C:\code\parent"}, mappings) == "par"
    # cwd is only consulted when the transcript folder name matches nothing
    unknown = r"C:\Users\me\.claude\projects\C--temp-xyz\s1.jsonl"
    assert ingest.detect_project(unknown, {"cwd": r"C:\code\parent\child"}, mappings) == "chi"
