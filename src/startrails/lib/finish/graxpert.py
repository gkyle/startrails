"""GraXpert AI Denoise preprocessing, highlight gating, tile contracts, and model identity."""

from typing import Tuple
import numpy as np

from startrails.lib.model_manifest import GRAXPERT_MODEL_SHA256, GRAXPERT_MODEL_VERSION

INPUT_TENSOR_NAME = "gen_input_image"
OUTPUT_TENSOR_NAME = "output"
CHANNELS = 3
WINDOW_SIZE = 256
DEFAULT_STRIDE = 128
MODEL_SCALE_FACTOR = 0.04
MODEL_THRESHOLD = 10.0
MIN_MAD_EPSILON = 1e-6
STATS_SAMPLE_STRIDE = 4


def graxpert_model_identity() -> str:
    """Return the pinned model identity used in full-strength inference cache keys.

    Provider selection is deliberately excluded: CPU and CUDA lanes run the same
    numerical pipeline, so switching an accelerator does not invalidate endpoints.
    """
    return f"{GRAXPERT_MODEL_VERSION}:{GRAXPERT_MODEL_SHA256}"


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
    """Reverse standardization and apply highlight protection to a denoised tile.

    Tiles whose source standardization reaches MODEL_THRESHOLD keep their original
    sample, so bright structures keep their measured highlights.
    """
    orig_scaled = (orig_tile - median) / mad * MODEL_SCALE_FACTOR
    gated = np.where(orig_scaled < MODEL_THRESHOLD, denoised_tile, orig_scaled)
    restored = gated / MODEL_SCALE_FACTOR * mad + median
    return np.clip(restored, 0.0, 1.0).astype(np.float32)


__all__ = [
    "CHANNELS",
    "DEFAULT_STRIDE",
    "INPUT_TENSOR_NAME",
    "MIN_MAD_EPSILON",
    "MODEL_SCALE_FACTOR",
    "MODEL_THRESHOLD",
    "OUTPUT_TENSOR_NAME",
    "STATS_SAMPLE_STRIDE",
    "WINDOW_SIZE",
    "compute_graxpert_stats",
    "graxpert_model_identity",
    "graxpert_tile_postprocess",
    "graxpert_tile_preprocess",
]
