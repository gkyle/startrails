"""Explicit setup-time smoke checks for Finish models; never runs during UI startup."""

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np

from startrails.lib.finish.graxpert import WINDOW_SIZE as GRAXPERT_WINDOW_SIZE
from startrails.lib.finish.graxpert_runtime import GraXpertSession
from startrails.lib.finish.nox import (
    DEFAULT_STRIDE,
    NoxSession,
    WINDOW_SIZE as NOX_WINDOW_SIZE,
    apply_radial_chroma_postfilter,
)
from startrails.lib.image_io import imread, normalize_image
from startrails.lib.model_manifest import GRAXPERT_MANIFEST, NOX_MANIFEST
from startrails.lib.signatures import verify_file_integrity
from startrails.paths import APPLICATION_DIR

SMOKE_IMAGE_SIZE = NOX_WINDOW_SIZE


def create_smoke_image(size: int = SMOKE_IMAGE_SIZE) -> np.ndarray:
    """Create a deterministic uint16 RGB starfield sample matching real dynamic range."""
    rng = np.random.default_rng(42)
    y = np.linspace(0.05, 0.18, size, dtype=np.float32)[:, None]
    x = np.linspace(0.04, 0.14, size, dtype=np.float32)[None, :]
    sky = np.stack([y * 0.7 + x * 0.3, y * 0.8 + x * 0.4, y * 0.9 + x * 0.5], axis=-1)
    sky += rng.normal(0.0, 0.008, size=sky.shape).astype(np.float32)

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    for _ in range(40):
        cy = float(rng.uniform(24, size - 24))
        cx = float(rng.uniform(24, size - 24))
        sigma = float(rng.uniform(1.2, 2.6))
        amp = float(rng.uniform(0.35, 0.9))
        spot = amp * np.exp(-((yy - cy) ** 2 + (xx - cx) ** 2) / (2.0 * sigma * sigma))
        sky += spot[:, :, None]

    return np.round(np.clip(sky, 0.0, 1.0) * 65535.0).astype(np.uint16)


def check_graxpert(model_path: Path, image: np.ndarray) -> dict:
    """Verify GraXpert weights and smoke-test tiled PyTorch inference."""
    if not verify_file_integrity(model_path, GRAXPERT_MANIFEST.sha256, GRAXPERT_MANIFEST.size_bytes):
        raise ValueError(f"Missing or unverified GraXpert model: {model_path}")
    started = perf_counter()
    tile = image[:GRAXPERT_WINDOW_SIZE, :GRAXPERT_WINDOW_SIZE]
    if tile.shape != (GRAXPERT_WINDOW_SIZE, GRAXPERT_WINDOW_SIZE, 3):
        raise ValueError("GraXpert setup requires at least a 256-pixel RGB sample.")
    session = GraXpertSession(model_path=model_path)
    denoised = session.denoise_full_strength(tile)
    if denoised.shape != tile.shape or denoised.dtype != np.float32 or not np.isfinite(denoised).all():
        raise ValueError("GraXpert inference returned invalid model output.")
    return {
        "version": GRAXPERT_MANIFEST.version,
        "configured_device": str(session.configured_device),
        "execution_device": session.execution_device,
        "fallback_reason": session.fallback_reason,
        "shape": list(denoised.shape),
        "seconds": perf_counter() - started,
    }


def check_nox(model_path: Path, image: np.ndarray, *, chroma_postfilter: bool = True) -> tuple[np.ndarray, dict]:
    """Verify Nox star removal weights and smoke-test tiled inference."""
    if not verify_file_integrity(model_path, NOX_MANIFEST.sha256, NOX_MANIFEST.size_bytes):
        raise ValueError(f"Missing or unverified Nox model: {model_path}")
    started = perf_counter()
    session = NoxSession(model_path=model_path)
    starless = session.remove_stars(image, stride=DEFAULT_STRIDE)
    if starless.shape != image.shape or starless.dtype != np.float32 or not np.isfinite(starless).all():
        raise ValueError("Nox star removal returned invalid model output.")
    detected_stars = 0
    if chroma_postfilter:
        starless, stats = apply_radial_chroma_postfilter(image, starless)
        detected_stars = stats.detected_stars
    return starless, {
        "version": NOX_MANIFEST.version,
        "configured_device": str(session.configured_device),
        "execution_device": session.execution_device,
        "fallback_reason": session.fallback_reason,
        "shape": list(starless.shape),
        "detected_stars": detected_stars,
        "seconds": perf_counter() - started,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graxpert-model", type=Path, default=APPLICATION_DIR / "models" / GRAXPERT_MANIFEST.relative_path
    )
    parser.add_argument("--nox-model", type=Path, default=APPLICATION_DIR / "models" / NOX_MANIFEST.relative_path)
    parser.add_argument("--skip-nox", action="store_true", help="Skip Nox star removal smoke check")
    parser.add_argument("--image", type=Path, help="Sample RGB image; check its central 512-pixel crop")
    parser.add_argument("--variant", choices=("cpu", "cu118", "cu124", "cu133", "mps"))
    args = parser.parse_args()
    if args.image is None:
        pixels = create_smoke_image()
    else:
        original = imread(args.image, to_rgb=True)
        height, width = original.shape[:2]
        if min(height, width) < SMOKE_IMAGE_SIZE or original.ndim != 3 or original.shape[2] != 3:
            parser.error("Sample image must be RGB and at least 512 pixels in each dimension")
        row, col = (height - SMOKE_IMAGE_SIZE) // 2, (width - SMOKE_IMAGE_SIZE) // 2
        pixels = original[row : row + SMOKE_IMAGE_SIZE, col : col + SMOKE_IMAGE_SIZE].copy()
        del original
    image = normalize_image(pixels)
    report = {}
    if not args.skip_nox:
        image, report["nox"] = check_nox(args.nox_model, image)
    report["graxpert"] = check_graxpert(args.graxpert_model, image)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
