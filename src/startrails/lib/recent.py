"""Management of recent StarTrails project files using persistent QSettings."""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional
from PySide6.QtCore import QSettings

RECENT_PROJECTS_KEY = "recent_projects"
MAX_RECENT_PROJECTS = 10


def get_recent_projects() -> List[Path]:
    """Retrieve list of existing recent project paths."""
    settings = QSettings("StarTrails", "StarTrails")
    raw = settings.value(RECENT_PROJECTS_KEY, [])
    if isinstance(raw, str):
        raw = [raw]
    elif not isinstance(raw, (list, tuple)):
        raw = []

    valid_paths: List[Path] = []
    for item in raw:
        if not item:
            continue
        try:
            p = Path(item).resolve()
            if p.exists() and p not in valid_paths:
                valid_paths.append(p)
        except Exception:
            pass
    return valid_paths


def add_recent_project(project_path: str | Path) -> None:
    """Add a project path to the top of the recent projects list."""
    if not project_path:
        return
    try:
        p = Path(project_path).resolve()
        current = get_recent_projects()
        if p in current:
            current.remove(p)
        current.insert(0, p)
        current = current[:MAX_RECENT_PROJECTS]
        settings = QSettings("StarTrails", "StarTrails")
        settings.setValue(RECENT_PROJECTS_KEY, [str(x) for x in current])
    except Exception:
        pass


def remove_recent_project(project_path: str | Path) -> None:
    """Remove a project path from the recent projects list."""
    if not project_path:
        return
    try:
        p = Path(project_path).resolve()
        current = get_recent_projects()
        if p in current:
            current.remove(p)
            settings = QSettings("StarTrails", "StarTrails")
            settings.setValue(RECENT_PROJECTS_KEY, [str(x) for x in current])
    except Exception:
        pass


def clear_recent_projects() -> None:
    """Clear all recent projects."""
    settings = QSettings("StarTrails", "StarTrails")
    settings.setValue(RECENT_PROJECTS_KEY, [])
