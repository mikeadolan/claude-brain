#!/usr/bin/env python3
"""
copy_chat_file.py - File versioning to chat-files/ per project for claude-brain.

Copies a file to a project's chat-files/ subfolder organized by date/session.

Usage:
    python3 copy_chat_file.py <filepath> --project <prefix> --session <session_id>

Exit codes: 0 = success, 1 = error
"""

import argparse
import datetime
import os
import pathlib
import shutil
import sys

import yaml

# ---------------------------------------------------------------------------
# Config / DB
# ---------------------------------------------------------------------------

def get_root_path():
    return str(pathlib.Path(__file__).resolve().parent.parent)


def load_config(root_path):
    config_path = os.path.join(root_path, "config.yaml")
    if not os.path.exists(config_path):
        raise SystemExit(f"FATAL: config.yaml not found at {config_path}")
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Project validation
# ---------------------------------------------------------------------------

def get_valid_prefixes(config):
    """Get set of valid project prefixes from config."""
    projects = config.get("projects", [])
    return {p["prefix"] for p in projects if isinstance(p, dict) and "prefix" in p}


def get_project_folder(config, prefix):
    """Get folder_name for a project prefix."""
    for p in config.get("projects", []):
        if isinstance(p, dict) and p.get("prefix") == prefix:
            return p.get("folder_name", prefix)
    return None


# ---------------------------------------------------------------------------
# Copy logic
# ---------------------------------------------------------------------------

def copy_chat_file(filepath, project, session_id, root_path=None, config=None):
    """Copy a file to the project's chat-files/ directory.

    Returns dict: {dest_path, exit_code}
    """
    if root_path is None:
        root_path = get_root_path()
    if config is None:
        config = load_config(root_path)

    filepath = os.path.abspath(filepath)

    # Validate source exists
    if not os.path.exists(filepath):
        print(f"Error: Source file not found: {filepath}", file=sys.stderr)
        return {"dest_path": "", "exit_code": 1}

    # Validate project prefix
    valid_prefixes = get_valid_prefixes(config)
    if project not in valid_prefixes:
        print(f"Error: Invalid project prefix '{project}'. Valid: {sorted(valid_prefixes)}", file=sys.stderr)
        return {"dest_path": "", "exit_code": 1}

    # Build destination path
    now = datetime.datetime.now(datetime.timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H%M%S")
    session_short = session_id[:8] if len(session_id) >= 8 else session_id
    subfolder = f"{date_str}_{time_str}_{session_short}"

    project_folder = get_project_folder(config, project)
    dest_dir = os.path.join(root_path, project_folder, "chat-files", subfolder)
    os.makedirs(dest_dir, exist_ok=True)

    # Copy file (preserve metadata)
    filename = os.path.basename(filepath)
    dest_path = os.path.join(dest_dir, filename)
    shutil.copy2(filepath, dest_path)

    return {"dest_path": dest_path, "exit_code": 0}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Copy file to project chat-files/ directory")
    parser.add_argument("filepath", help="Path to file to copy")
    parser.add_argument("--project", required=True, help="Project prefix (jg, gen, etc.)")
    parser.add_argument("--session", required=True, help="Current session UUID")
    args = parser.parse_args()

    result = copy_chat_file(args.filepath, args.project, args.session)

    if result["exit_code"] == 0:
        print(f"Copied {os.path.basename(args.filepath)} -> {result['dest_path']}")
    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
