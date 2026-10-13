"""Star detection with subpixel centroiding and background estimation."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import cv2
import numpy as np


@dataclass
class Star:
    """Detected point source star."""
    x: float
    y: float
    brightness: float
    fwhm: float = 2.0


class StarDetector:
    """Detects stars in astrophotography frames with subpixel accuracy."""

    @staticmethod
    def prepare_sky_mask(sky_mask: Optional[np.ndarray]) -> Optional[np.ndarray]:
        """Pre-erode sky mask once to avoid repeating morphology on every frame."""
        if sky_mask is None:
            return None
        mask_bin = (sky_mask > 0.5).astype(np.float32)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        return cv2.erode(mask_bin, kernel)

    @classmethod
    def detect_stars(
        cls,
        image: np.ndarray,
        sky_mask: Optional[np.ndarray] = None,
        max_stars: int = 1000,
        min_distance: int = 5,
        threshold_sigma: float = 3.5,
    ) -> List[Star]:
        """Detect point-source stars within designated sky region."""
        if image.ndim == 3 and image.shape[2] == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        elif image.ndim == 3:
            gray = image[..., 0].copy()
        else:
            gray = image.copy()

        h, w = gray.shape

        if sky_mask is not None:
            if sky_mask.shape != (h, w):
                mask_bin = cv2.resize(sky_mask, (w, h), interpolation=cv2.INTER_NEAREST)
            else:
                mask_bin = sky_mask
            if mask_bin.dtype != np.float32:
                mask_bin = (mask_bin > 0.5).astype(np.float32)
            cv2.multiply(gray, mask_bin, dst=gray)

        bg = cv2.boxFilter(gray, -1, (21, 21), borderType=cv2.BORDER_REPLICATE)
        star_signal = np.maximum(gray - bg, 0.0)

        valid_pixels = star_signal[star_signal > 0] if sky_mask is not None else star_signal
        if valid_pixels.size == 0:
            return []

        if valid_pixels.size > 100_000:
            sample = valid_pixels[:: max(1, valid_pixels.size // 100_000)]
            med = np.median(sample)
            sigma = 1.4826 * float(np.median(np.abs(sample - med)))
        else:
            med = np.median(valid_pixels)
            sigma = 1.4826 * float(np.median(np.abs(valid_pixels - med)))
        cutoff = max(threshold_sigma * sigma, 0.01)

        dilated = cv2.dilate(star_signal, cv2.getStructuringElement(cv2.MORPH_RECT, (min_distance, min_distance)))
        peak_mask = (star_signal == dilated) & (star_signal > cutoff)

        border = 5
        peak_mask[:border, :] = False
        peak_mask[-border:, :] = False
        peak_mask[:, :border] = False
        peak_mask[:, -border:] = False

        peak_y, peak_x = np.where(peak_mask)
        if len(peak_x) == 0:
            return []

        candidate_limit = max(max_stars * 3, 3000)
        if len(peak_x) > candidate_limit:
            peak_strengths = star_signal[peak_y, peak_x]
            top_idx = np.argpartition(peak_strengths, -candidate_limit)[-candidate_limit:]
            peak_y = peak_y[top_idx]
            peak_x = peak_x[top_idx]

        stars: List[Star] = []
        for py, px in zip(peak_y, peak_x):
            patch = star_signal[py - 2 : py + 3, px - 2 : px + 3]
            total_mass = float(np.sum(patch))
            if total_mass <= 1e-6:
                continue

            dy, dx = np.mgrid[-2:3, -2:3]
            sub_x = px + float(np.sum(dx * patch)) / total_mass
            sub_y = py + float(np.sum(dy * patch)) / total_mass
            brightness = float(star_signal[py, px])

            stars.append(Star(x=sub_x, y=sub_y, brightness=brightness))

        if len(stars) <= max_stars:
            stars.sort(key=lambda s: s.brightness, reverse=True)
            return stars

        grid_cols = 8
        grid_rows = 4
        cw = w / grid_cols
        ch = h / grid_rows

        cells: dict[Tuple[int, int], List[Star]] = {}
        for s in stars:
            col = min(int(s.x / cw), grid_cols - 1)
            row = min(int(s.y / ch), grid_rows - 1)
            cells.setdefault((row, col), []).append(s)

        stars_per_cell = max(10, int(np.ceil(max_stars / (grid_cols * grid_rows))))
        selected_set = set()
        selected_stars: List[Star] = []

        for cell_stars in cells.values():
            cell_stars.sort(key=lambda s: s.brightness, reverse=True)
            for s in cell_stars[:stars_per_cell]:
                selected_stars.append(s)
                selected_set.add(id(s))

        if len(selected_stars) < max_stars:
            remaining = [s for s in stars if id(s) not in selected_set]
            remaining.sort(key=lambda s: s.brightness, reverse=True)
            selected_stars.extend(remaining[: max_stars - len(selected_stars)])

        selected_stars.sort(key=lambda s: s.brightness, reverse=True)
        return selected_stars[:max_stars]
