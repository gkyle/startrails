"""Project state model and persistence for StarTrails mode."""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from startrails.lib.file import InputFile, OutputFile, Unpickle
from startrails.lib.project_type import get_project_output_dir, STARTRAILS_EXT


class Project(Unpickle):
    """Project state model for the StarTrails workflow."""

    def __init__(
        self,
        rawInputFiles: Optional[List[InputFile]] = None,
        outputFiles: Optional[List[OutputFile]] = None,
        projectFile: str = f"projects/default{STARTRAILS_EXT}",
        sortBy: str = "date",
        sortOrder: str = "asc",
    ):
        super().__init__()
        self.rawInputFiles = list(rawInputFiles) if rawInputFiles is not None else []
        self.outputFiles = list(outputFiles) if outputFiles is not None else []
        self.selected = None
        self.operations = {}
        self.projectFile = projectFile
        self.sortBy = sortBy
        self.sortOrder = sortOrder

    def get_output_dir(self) -> Path:
        """Resolve the authoritative output directory for this project."""
        return get_project_output_dir(self.projectFile)
