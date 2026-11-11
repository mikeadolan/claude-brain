"""Resolve where a registered project actually lives.

A project entry may carry an absolute ``path`` when the project is an existing
directory outside the claude-brain root (see issue #2). Without one, the
project is a folder inside ``storage.root_path``.
"""

import os


def resolve_project_path(project, root):
    """Return the absolute directory for a project config entry."""
    raw = (project.get("path") or "").strip()
    if raw:
        return os.path.expandvars(os.path.expanduser(raw))
    folder = (project.get("folder_name") or "").strip()
    return os.path.join(os.path.expandvars(os.path.expanduser(root)), folder)


def is_external(project):
    """True when the project points at a directory outside the brain root."""
    return bool((project.get("path") or "").strip())
