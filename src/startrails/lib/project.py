"""Project state model and persistence for StarTrails mode."""

from __future__ import annotations
from pathlib import Path
from typing import List, Optional

from startrails.lib.file import InputFile, OutputFile, Unpickle
from startrails.lib.project_type import get_project_output_dir
from startrails.lib.startrails.defaults import DEFAULT_PROJECT_FILENAME, STARTRAILS_DEFAULTS


class Project(Unpickle):
    """Project state model for the StarTrails workflow."""

    def __init__(
        self,
        rawInputFiles: Optional[List[InputFile]] = None,
        outputFiles: Optional[List[OutputFile]] = None,
        projectFile: str = DEFAULT_PROJECT_FILENAME,
        sortBy: str = STARTRAILS_DEFAULTS.sort_by,
        sortOrder: str = STARTRAILS_DEFAULTS.sort_order,
        fadeMode: int = STARTRAILS_DEFAULTS.fade_mode,
        fadeAmount: int = STARTRAILS_DEFAULTS.fade_amount,
        batchSize: int = STARTRAILS_DEFAULTS.batch_size,
        useGPU: bool = STARTRAILS_DEFAULTS.use_gpu,
        streaksRemoved: Optional[bool] = STARTRAILS_DEFAULTS.streaks_removed,
    ):
        super().__init__()
        self.rawInputFiles = list(rawInputFiles) if rawInputFiles is not None else []
        self.outputFiles = list(outputFiles) if outputFiles is not None else []
        self.selected = None
        self.operations = {}
        self.projectFile = projectFile
        self.sortBy = sortBy
        self.sortOrder = sortOrder
        self.fadeMode = fadeMode
        self.fadeAmount = fadeAmount
        self.batchSize = batchSize
        self.useGPU = useGPU
        self.streaksRemoved = streaksRemoved
        self.applied_corrections: int = 0

    def __setstate__(self, state: dict) -> None:
        super().__setstate__(state)
        if getattr(self, "fadeMode", None) is None:
            self.fadeMode = STARTRAILS_DEFAULTS.fade_mode
        if getattr(self, "fadeAmount", None) is None:
            self.fadeAmount = STARTRAILS_DEFAULTS.fade_amount
        if getattr(self, "batchSize", None) is None:
            self.batchSize = STARTRAILS_DEFAULTS.batch_size
        if getattr(self, "useGPU", None) is None:
            self.useGPU = STARTRAILS_DEFAULTS.use_gpu
        if getattr(self, "sortBy", None) is None:
            self.sortBy = STARTRAILS_DEFAULTS.sort_by
        if getattr(self, "sortOrder", None) is None:
            self.sortOrder = STARTRAILS_DEFAULTS.sort_order

    def __getattr__(self, name: str):
        if hasattr(STARTRAILS_DEFAULTS, name):
            val = getattr(STARTRAILS_DEFAULTS, name)
            setattr(self, name, val)
            return val
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def get_output_dir(self) -> Path:
        """Resolve the authoritative output directory for this project."""
        return get_project_output_dir(self.projectFile)
