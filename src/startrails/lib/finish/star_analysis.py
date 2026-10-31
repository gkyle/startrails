"""Common star measurement types for Round Stars, Star Glow, and faint-star suppression."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class StarCandidate:
    """Measured properties of a single detected star candidate."""

    y: float  # Centroid vertical coordinate in full-resolution image pixels
    x: float  # Centroid horizontal coordinate in full-resolution image pixels
    flux: float  # Integrated flux across star footprint
    peak_brightness: float  # Maximum intensity in star footprint
    color_ratio: Tuple[float, float, float]  # Normalized RGB color ratios
    ellipticity: float  # (a - b) / (a + b) from second moments; 0.0 = circular
    orientation_rad: float  # Major axis angle in radians [-pi/2, pi/2]
    footprint_radius_px: float  # Bounding footprint radius in full-resolution pixels
    is_valid: bool = True  # Passed isolation and confidence gates
    is_saturated: bool = False  # Contains clipped/saturated core pixels
    is_blended: bool = False  # Overlaps significantly with neighboring detection


@dataclass(frozen=True)
class StarAnalysisResult:
    """Authoritative output contract of the shared star detection and analysis step."""

    candidates: Tuple[StarCandidate, ...]
    image_shape: Tuple[int, int]
    faint_star_flux_threshold: float = 0.0

    @property
    def valid_stars(self) -> Tuple[StarCandidate, ...]:
        return tuple(s for s in self.candidates if s.is_valid)
