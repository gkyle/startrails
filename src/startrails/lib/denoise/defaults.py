"""Shared defaults for denoise projects, processing APIs, and UI bindings.

Keep this module dependency-free so low-level algorithms can use the same
values as project persistence. Projects copy these immutable defaults before
applying saved values or user overrides. None in an algorithm signature may
still mean "inherit another argument", rather than a default setting.
"""

from dataclasses import dataclass
from typing import Final, Optional


@dataclass(frozen=True)
class DenoiseSettings:
    """Authoritative defaults for persisted and runtime denoise settings."""

    jpeg_quality: int = 95
    jpeg_optimize: bool = True
    mask_search_radius: Optional[int] = None
    mask_erosion_pixels: int = 5
    mask_foliage_protection: bool = True
    refine_sky_mask: bool = False
    auto_mask: bool = False
    auto_mask_model: str = "nightstack"
    auto_mask_path: Optional[str] = None
    export_refined_mask: bool = True
    export_gradient_mask: bool = True
    taper_mask_edges: bool = True
    mask_taper_pixels: int = 5
    enable_horizon_corrections: bool = True
    denoise_horizon_band: bool = True
    horizon_denoise_radius: int = 5
    horizon_denoise_eps: float = 1e-3
    horizon_denoise_strength: float = 0.2
    horizon_color_denoise_strength: float = 1.0
    horizon_value_denoise_strength: float = 0.2
    horizon_blend_percent: float = 30.0  # Percent (0–100), not a 0–1 ratio.
    horizon_blur_radius: float = 2.0
    stack_method: str = "sigma_clipped"
    sigma_clip_threshold: float = 1.2
    sigma_clip_iterations: int = 3
    compress_intermediate_tiffs: bool = False
    use_gpu: bool = True
    max_workers: Optional[int] = None
    verbose: bool = False


DENOISE_DEFAULTS: Final[DenoiseSettings] = DenoiseSettings()

# Shared defaults that are not persisted project settings.
DEFAULT_HORIZON_FEATHER_RADIUS: Final = 3.0
DEFAULT_SKY_DETECTION_DEVICE: Final = "auto"
DEFAULT_SKY_DETECTION_INPUT_SIZE: Final = 1024
DEFAULT_MASK_BRUSH_RADIUS: Final = 25
