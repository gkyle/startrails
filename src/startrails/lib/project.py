"""Project state model and persistence for StarTrails mode."""

from __future__ import annotations

from pathlib import Path
from typing import Final, List, Optional

from startrails.lib.file import InputFile, OutputFile, Unpickle
from startrails.lib.project_type import get_project_output_dir
from startrails.lib.startrails.defaults import DEFAULT_PROJECT_FILENAME, STARTRAILS_DEFAULTS

# Persisted Project field names mapped to their authoritative defaults.
_PERSISTED_SETTING_DEFAULTS: Final[dict[str, str]] = {
    "sortBy": "sort_by",
    "sortOrder": "sort_order",
    "fadeMode": "fade_mode",
    "fadeAmount": "fade_amount",
    "batchSize": "batch_size",
    "useGPU": "use_gpu",
    "streaksRemoved": "streaks_removed",
}

_EMPTY_STRING_SETTINGS: Final[frozenset[str]] = frozenset({"sortBy", "sortOrder"})


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
        self.normalize_loaded_state()

    def normalize_loaded_state(self) -> None:
        """Restore persisted settings omitted or blanked by older project formats."""
        for field_name, default_name in _PERSISTED_SETTING_DEFAULTS.items():
            value = getattr(self, field_name, None)
            if value is None or (field_name in _EMPTY_STRING_SETTINGS and value == ""):
                setattr(self, field_name, getattr(STARTRAILS_DEFAULTS, default_name))

        applied = getattr(self, "applied_corrections", None)
        if not isinstance(applied, int) or isinstance(applied, bool) or applied < 0:
            self.applied_corrections = 0

    def get_output_dir(self) -> Path:
        """Resolve the authoritative output directory for this project."""
        return get_project_output_dir(self.projectFile)
