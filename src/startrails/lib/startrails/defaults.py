"""Shared defaults and configuration owner for StarTrails mode.

Keep this module dependency-free so low-level algorithms, workflow dispatch,
and project persistence share the same authoritative settings contracts.
"""

from dataclasses import dataclass
from typing import Final, Optional, Tuple

# Project identity and extension constants
PROJECT_TYPE_STARTRAILS: Final[str] = "startrails"
STARTRAILS_EXT: Final[str] = ".proj_startrails"
LEGACY_STARTRAILS_EXT: Final[str] = ".project.json"
DEFAULT_PROJECT_FILENAME: Final[str] = f"projects/default{STARTRAILS_EXT}"

# Stacking fade modes (mapped to UI segmented button: Off, Start, End, Both)
FADE_MODE_OFF: Final[int] = 0
FADE_MODE_START: Final[int] = 1
FADE_MODE_END: Final[int] = 2
FADE_MODE_BOTH: Final[int] = 3

# Stacking streaks handling (mapped to UI segmented button: Keep, Remove)
STREAKS_KEEP_INDEX: Final[int] = 0
STREAKS_REMOVE_INDEX: Final[int] = 1

# Streak detection merge methods
MERGE_METHOD_NMS: Final[str] = "NMS"
MERGE_METHOD_GREEDY_NMM: Final[str] = "GREEDYNMM"
MERGE_METHODS: Final[Tuple[str, ...]] = (MERGE_METHOD_NMS, MERGE_METHOD_GREEDY_NMM)

# Authoritative default values
DEFAULT_SORT_BY: Final[str] = "date"
DEFAULT_SORT_ORDER: Final[str] = "asc"
DEFAULT_FADE_MODE: Final[int] = FADE_MODE_BOTH
DEFAULT_FADE_AMOUNT_PERCENT: Final[int] = 10
DEFAULT_BATCH_SIZE: Final[int] = 1
DEFAULT_USE_GPU: Final[bool] = True

DEFAULT_CONFIDENCE_THRESHOLD: Final[float] = 0.3
DEFAULT_MERGE_THRESHOLD: Final[float] = 0.2
DEFAULT_MERGE_METHOD: Final[str] = MERGE_METHOD_GREEDY_NMM
DEFAULT_MERGE_METHOD_INDEX: Final[int] = 1

PERCENT_SCALE: Final[float] = 100.0


@dataclass(frozen=True)
class StartrailsSettings:
    """Authoritative defaults for persisted and runtime StarTrails settings."""

    # Stacking and project settings
    sort_by: str = DEFAULT_SORT_BY
    sort_order: str = DEFAULT_SORT_ORDER
    fade_mode: int = DEFAULT_FADE_MODE
    fade_amount: int = DEFAULT_FADE_AMOUNT_PERCENT
    batch_size: int = DEFAULT_BATCH_SIZE
    use_gpu: bool = DEFAULT_USE_GPU
    streaks_removed: Optional[bool] = None

    # Streak detection defaults
    conf_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    merge_threshold: float = DEFAULT_MERGE_THRESHOLD
    merge_method: str = DEFAULT_MERGE_METHOD


STARTRAILS_DEFAULTS: Final[StartrailsSettings] = StartrailsSettings()
