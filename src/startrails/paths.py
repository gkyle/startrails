"""Application resources and the process working directory at startup."""

import os
from pathlib import Path

APPLICATION_DIR = Path(__file__).resolve().parents[2]
WORK_DIR_ENV = "STARTRAILS_WORK_DIR"


def configure_work_directory(project_path: str | None) -> str | None:
    """Resolve launch arguments before applying the optional working directory."""
    project = str(Path(project_path).resolve()) if project_path is not None else None
    configured = os.environ.get(WORK_DIR_ENV)
    if configured is not None:
        if not configured.strip():
            raise ValueError(f"{WORK_DIR_ENV} must name a directory.")
        directory = Path(configured).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        os.chdir(directory)
    return project
