"""Shared defaults and configuration owner for Finish mode.

Keep this module dependency-free so low-level algorithms, workflow dispatch,
and project persistence share the same authoritative settings contracts.
"""

from dataclasses import dataclass
from typing import Final, Literal, Optional, Tuple


DenoiseScopeType = Literal["sky_only", "whole_image"]
BlendModeType = Literal["add", "screen"]

# Project identity and extension constants
PROJECT_TYPE_FINISH: Final[str] = "finish"
FINISH_EXT: Final[str] = ".proj_finish"
FINISH_OUTPUT_DIR_SUFFIX: Final[str] = ".finish"

# Authoritative artifact role identifiers
ROLE_SOURCE_SNAPSHOT: Final[str] = "source_snapshot"
ROLE_SKY_MASK: Final[str] = "sky_mask"
ROLE_UNMASKED_STARLESS: Final[str] = "unmasked_starless"
ROLE_SEPARATED_STARLESS: Final[str] = "separated_starless"
ROLE_SEPARATED_STARS: Final[str] = "separated_stars"
ROLE_DENOISED_STARLESS: Final[str] = "denoised_starless"
ROLE_FINISHED_STARLESS: Final[str] = "finished_starless"
ROLE_FINISHED_COMPOSITE: Final[str] = "finished_composite"

# Scope constants
SCOPE_SKY_ONLY: Final[str] = "sky_only"
SCOPE_WHOLE_IMAGE: Final[str] = "whole_image"

# Recombination blend modes
BLEND_ADD: Final[str] = "add"
BLEND_SCREEN: Final[str] = "screen"

# Proposed default values (percent / units)
DEFAULT_DENOISE_STRENGTH_PERCENT: Final[float] = 50.0
DEFAULT_DENOISE_SCOPE: Final[str] = SCOPE_SKY_ONLY
DEFAULT_STRUCTURE_AMOUNT_PERCENT: Final[float] = 0.0
DEFAULT_DETAIL_AMOUNT_PERCENT: Final[float] = 0.0
DEFAULT_STAR_AMOUNT_PERCENT: Final[float] = 100.0
DEFAULT_BLEND_MODE: Final[str] = BLEND_ADD

# Settings retired by Step 10B and removed with Finish Stars in Step 10R. Old
# development projects may still contain them; loading drops them instead of
# resurrecting controls that no longer own any state.
RETIRED_FINISH_SETTING_NAMES: Final[Tuple[str, ...]] = (
    "faint_star_suppression",
    "faint_star_amount",
    "star_count_cutoff",
    "round_stars_enabled",
    "round_stars_amount",
    "star_glow_enabled",
    "star_glow_amount",
    "star_glow_radius_px",
    "glow_star_count",
    "original_stars_amount",
    "original_stars_blend_mode",
)

# Recombination controls change the composite only; stored layers stay valid.
COMPOSITION_ONLY_SETTING_NAMES: Final[Tuple[str, ...]] = (
    "star_amount",
    "blend_mode",
)

# Lossless intermediates preserve soft mask/model precision even for 8-bit sources.
INTERMEDIATE_BIT_DEPTH: Final[int] = 16

# Codec defaults matching existing application standards
DEFAULT_JPEG_QUALITY: Final[int] = 95
DEFAULT_JPEG_OPTIMIZE: Final[bool] = True
DEFAULT_TIFF_DEFLATE_COMPRESSION: Final[bool] = True
DEFAULT_STARNET_STRIDE: Final[int] = 256

# Neutral identity settings
NEUTRAL_DENOISE_STRENGTH_PERCENT: Final[float] = 0.0
NEUTRAL_STRUCTURE_AMOUNT_PERCENT: Final[float] = 0.0
NEUTRAL_DETAIL_AMOUNT_PERCENT: Final[float] = 0.0
NEUTRAL_STAR_AMOUNT_PERCENT: Final[float] = 100.0

PERCENT_SCALE: Final[float] = 100.0
SUPPORTED_SOURCE_FORMATS: Final[Tuple[str, ...]] = ("jpeg", "tiff")
SUPPORTED_BIT_DEPTHS: Final[Tuple[int, ...]] = (8, 16)
SUPPORTED_CHANNELS: Final[int] = 3


@dataclass(frozen=True)
class FinishSettings:
    """Authoritative owner for persisted and runtime Finish settings."""

    # Sky mask step
    auto_mask_model: str = "nightstack"
    auto_mask_path: Optional[str] = None
    mask_search_radius: Optional[int] = None
    mask_erosion_pixels: int = 5
    mask_foliage_protection: bool = True
    starnet_stride: int = DEFAULT_STARNET_STRIDE

    # Denoise step
    denoise_strength: float = DEFAULT_DENOISE_STRENGTH_PERCENT
    denoise_scope: DenoiseScopeType = DEFAULT_DENOISE_SCOPE

    # Starless sharpening
    structure_amount: float = DEFAULT_STRUCTURE_AMOUNT_PERCENT
    detail_amount: float = DEFAULT_DETAIL_AMOUNT_PERCENT

    # Recombination & Export. The separated stars layer is used unchanged;
    # Stars Amount and the blend mode are its only controls.
    star_amount: float = DEFAULT_STAR_AMOUNT_PERCENT
    blend_mode: BlendModeType = DEFAULT_BLEND_MODE
    jpeg_quality: int = DEFAULT_JPEG_QUALITY
    jpeg_optimize: bool = DEFAULT_JPEG_OPTIMIZE
    tiff_deflate_compression: bool = DEFAULT_TIFF_DEFLATE_COMPRESSION

    # Mask feathering (derived at runtime; canonical mask remains unfeathered)
    mask_feather_radius_px: float = 0.0


FINISH_DEFAULTS: Final[FinishSettings] = FinishSettings()
