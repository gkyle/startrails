"""Project state model and persistence for StarTrails mode."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Final, List, Optional

import numpy as np

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


def _corrections_signature(payload) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


EMPTY_CORRECTIONS_SIGNATURE: Final[str] = _corrections_signature([])


def _canonical_polygons(masks) -> list[list[list[int]]]:
    """Normalize user-drawn polygons to dtype-independent integer coordinates."""
    polygons = [
        np.asarray(mask, dtype=np.int64).reshape(-1, 2).tolist()
        for mask in masks
    ]
    polygons.sort()
    return polygons


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
        self.applied_corrections_signature: Optional[str] = EMPTY_CORRECTIONS_SIGNATURE

    def __setstate__(self, state: dict) -> None:
        super().__setstate__(state)
        if "applied_corrections_signature" not in state:
            self.applied_corrections_signature = None
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

        signature = getattr(self, "applied_corrections_signature", None)
        if not isinstance(signature, str) or not signature:
            self.applied_corrections_signature = (
                None if self.applied_corrections > 0 else EMPTY_CORRECTIONS_SIGNATURE
            )

    def get_output_dir(self) -> Path:
        """Resolve the authoritative output directory for this project."""
        return get_project_output_dir(self.projectFile)

    def stack_input_files(self) -> List[InputFile]:
        """Return the inputs included in stacking, in project order."""
        return [file for file in self.rawInputFiles if not file.excludeFromStack]

    def corrections_count(self) -> int:
        """Count user corrections on the inputs included in stacking."""
        return sum(
            len(file.streaksManualMasks) + len(file.streaksManualDeletedMasks)
            for file in self.stack_input_files()
        )

    def corrections_signature(self) -> str:
        """Fingerprint included inputs and their manual/deleted polygons."""
        entries = []
        for file in sorted(self.stack_input_files(), key=lambda file: (str(file.path), str(file.basename))):
            manual = _canonical_polygons(file.streaksManualMasks)
            deleted = _canonical_polygons(file.streaksManualDeletedMasks)
            if not manual and not deleted:
                continue
            entries.append({"path": str(file.path), "manual": manual, "deleted": deleted})
        return _corrections_signature(entries)

    def corrections_pending(self) -> bool:
        """Whether current user corrections differ from the last applied stack."""
        return self.corrections_signature() != self.applied_corrections_signature
