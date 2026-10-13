"""Configuration data structures for Denoise processing parameters."""

from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import numpy as np


@dataclass
class DenoiseConfig:
    """Complete configuration settings for a Denoise stacking run."""

    # Input / Output
    star_images: List[Path] = field(default_factory=list)
    base_image: Optional[Path] = None
    noise_images: List[Path] = field(default_factory=list)
    vignetting_images: List[Path] = field(default_factory=list)
    output_path: Optional[Path] = None

    # Cached intermediate base stacks
    sky_stack_path: Optional[Path] = None
    ground_stack_path: Optional[Path] = None

    # Masking
    mask_path: Optional[Path] = None
    mask_array: Optional[np.ndarray] = None
    mask_search_radius: Optional[int] = None
    mask_erosion_pixels: int = 5
    mask_foliage_protection: bool = True
    refine_sky_mask: bool = False
    auto_mask: bool = False
    auto_mask_model: Optional[str] = None
    auto_mask_path: Optional[str] = None
    export_refined_mask: bool = True
    refined_mask_path: Optional[Path] = None

    # Gradient mask export
    export_gradient_mask: bool = True
    gradient_mask_path: Optional[Path] = None

    # Mask boundary tapering
    taper_mask_edges: bool = True
    mask_taper_pixels: int = 5

    # Horizon transition band corrections & tuning
    enable_horizon_corrections: bool = True
    denoise_horizon_band: bool = True
    horizon_denoise_radius: int = 5
    horizon_denoise_eps: float = 1e-3
    horizon_denoise_strength: float = 0.2
    horizon_color_denoise_strength: float = 1.0
    horizon_value_denoise_strength: float = 0.2
    horizon_blend_percent: float = 60.0
    horizon_blur_radius: float = 2.0

    # Stacking method
    stack_method: str = "sigma_clipped"  # "sigma_clipped" or "mean"
    sigma_clip_threshold: float = 1.2
    sigma_clip_iterations: int = 3

    # Cached alignment homographies
    homographies: dict[Path, np.ndarray] = field(default_factory=dict)

    # Hardware acceleration
    use_gpu: bool = True
    max_workers: Optional[int] = None
    verbose: bool = False


Config = DenoiseConfig
