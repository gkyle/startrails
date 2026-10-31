"""GraXpert AI Denoise preprocessing, highlight gating, tile contracts, and runtime helpers."""

from typing import Tuple
import numpy as np

INPUT_TENSOR_NAME = "gen_input_image"
OUTPUT_TENSOR_NAME = "output"
CHANNELS = 3
WINDOW_SIZE = 256
DEFAULT_STRIDE = 128
MODEL_SCALE_FACTOR = 0.04
MODEL_THRESHOLD = 10.0
MIN_MAD_EPSILON = 1e-6
STATS_SAMPLE_STRIDE = 4

DEFAULT_CPU_BATCH_SIZE = 1  # Setup smoke-validated CPU baseline; CUDA policy remains gated.


def compute_graxpert_stats(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Compute per-channel median and MAD for GraXpert normalization.

    Args:
        image: float32 image array with shape (H, W, C) in [0.0, 1.0].

    Returns:
        Tuple of (median, mad), each shape (C,).
    """
    subsampled = image[::STATS_SAMPLE_STRIDE, ::STATS_SAMPLE_STRIDE, :]
    median = np.median(subsampled, axis=(0, 1))
    mad = np.median(np.abs(subsampled - median), axis=(0, 1))
    mad = np.maximum(mad, MIN_MAD_EPSILON)
    return median.astype(np.float32), mad.astype(np.float32)


def graxpert_tile_preprocess(
    tile: np.ndarray,
    median: np.ndarray,
    mad: np.ndarray,
) -> np.ndarray:
    """Standardize a (256, 256, 3) image tile for the GraXpert ONNX input.

    Formula: clip((tile - median) / mad * 0.04, -10.0, 10.0)
    """
    scaled = (tile - median) / mad * MODEL_SCALE_FACTOR
    return np.clip(scaled, -MODEL_THRESHOLD, MODEL_THRESHOLD).astype(np.float32)


def graxpert_tile_postprocess(
    denoised_tile: np.ndarray,
    orig_tile: np.ndarray,
    median: np.ndarray,
    mad: np.ndarray,
) -> np.ndarray:
    """Reverse standardization and apply highlight protection to a denoised tile."""
    orig_scaled = (orig_tile - median) / mad * MODEL_SCALE_FACTOR
    gated = np.where(orig_scaled < MODEL_THRESHOLD, denoised_tile, orig_scaled)
    restored = gated / MODEL_SCALE_FACTOR * mad + median
    return np.clip(restored, 0.0, 1.0).astype(np.float32)


def blend_graxpert_denoised(
    orig: np.ndarray,
    denoised: np.ndarray,
    median: np.ndarray,
    mad: np.ndarray,
    strength: float = 0.5,
) -> np.ndarray:
    """Apply adaptive highlight gating and linear alpha-blend with the original image.

    Strength: 0.0 returns orig exactly, 1.0 returns fully denoised plate with highlight protection.
    """
    if strength <= 0.0:
        return orig.copy()

    threshold = (MODEL_THRESHOLD / MODEL_SCALE_FACTOR) * mad + median
    gated = np.where(orig < threshold, denoised, orig)
    if strength >= 1.0:
        return np.clip(gated, 0.0, 1.0).astype(np.float32)

    blended = gated * float(strength) + orig * (1.0 - float(strength))
    return np.clip(blended, 0.0, 1.0).astype(np.float32)
