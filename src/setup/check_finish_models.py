"""Explicit setup-time smoke checks for Finish models; never runs during UI startup."""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import onnxruntime as ort

from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.graxpert import (
    INPUT_TENSOR_NAME,
    OUTPUT_TENSOR_NAME,
    WINDOW_SIZE as GRAXPERT_WINDOW_SIZE,
    compute_graxpert_stats,
    graxpert_tile_postprocess,
    graxpert_tile_preprocess,
)
from startrails.lib.finish.graxpert_runtime import GRAXPERT_RUNTIME_POLICY_PATH
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


def check_graxpert(model_path: Path, image: np.ndarray, *, variant: str) -> dict:
    """Setup owns selection; verify actual GPU kernels, explicitly report CPU fallback."""
    if not verify_file_integrity(model_path, GRAXPERT_MANIFEST.sha256, GRAXPERT_MANIFEST.size_bytes):
        raise ValueError(f"Missing or unverified GraXpert model: {model_path}")
    started = perf_counter()
    median, mad = compute_graxpert_stats(image)
    tile = image[:GRAXPERT_WINDOW_SIZE, :GRAXPERT_WINDOW_SIZE]
    if tile.shape != (GRAXPERT_WINDOW_SIZE, GRAXPERT_WINDOW_SIZE, 3):
        raise ValueError("GraXpert setup requires at least a 256-pixel RGB sample.")
    batch = graxpert_tile_preprocess(tile, median, mad)[None]

    def run(provider):
        with TemporaryDirectory(prefix="startrails-ort-profile-") as temporary:
            options = ort.SessionOptions()
            options.enable_profiling = provider == "CUDAExecutionProvider"
            options.profile_file_prefix = str(Path(temporary) / "profile")
            session = ort.InferenceSession(str(model_path), sess_options=options, providers=[provider])
            session.disable_fallback()
            if session.get_providers()[0] != provider:
                raise RuntimeError(f"Requested {provider}, but ONNX Runtime fell back to CPU.")
            output = session.run([OUTPUT_TENSOR_NAME], {INPUT_TENSOR_NAME: batch})[0]
            if output.shape != batch.shape or output.dtype != np.float32 or not np.isfinite(output).all():
                raise ValueError("GraXpert inference returned invalid model output.")
            if options.enable_profiling:
                profile = json.loads(Path(session.end_profiling()).read_text())
                if not any(event.get("args", {}).get("provider") == provider for event in profile):
                    raise RuntimeError("GraXpert inference did not execute any CUDA kernels.")
            restored = graxpert_tile_postprocess(output[0], tile, median, mad)
            if not np.isfinite(restored).all():
                raise ValueError("GraXpert postprocessing returned non-finite output.")
            return session.get_providers(), list(output.shape)

    if variant == "cu133":
        # Match the application's Torch import before initializing native CUDA libraries.
        import torch  # noqa: F401

    gpu_error = None
    provider = "CUDAExecutionProvider" if variant == "cu133" else "CPUExecutionProvider"
    try:
        providers, shape = run(provider)
    except Exception as error:
        if provider == "CPUExecutionProvider":
            raise
        gpu_error = str(error)
        provider = "CPUExecutionProvider"
        providers, shape = run(provider)
    policy = {
        "provider": provider,
        "device": "cuda" if provider == "CUDAExecutionProvider" else "cpu",
        "variant": variant,
        "ort_version": ort.__version__,
        "model_sha256": GRAXPERT_MANIFEST.sha256,
        "gpu_error": gpu_error,
        "verified": True,
    }
    return {
        "version": ort.__version__,
        "providers": providers,
        "selected_policy": policy,
        "shape": shape,
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


def persist_graxpert_policy(policy: dict, path: Path) -> None:
    with ArtifactTransaction() as transaction:
        staged = transaction.stage(path)
        staged.write_text(json.dumps(policy, indent=2), encoding="utf-8")
        transaction.commit()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graxpert-model", type=Path, default=APPLICATION_DIR / "models" / GRAXPERT_MANIFEST.relative_path
    )
    parser.add_argument("--nox-model", type=Path, default=APPLICATION_DIR / "models" / NOX_MANIFEST.relative_path)
    parser.add_argument("--skip-nox", action="store_true", help="Skip Nox star removal smoke check")
    parser.add_argument("--image", type=Path, help="Sample RGB image; check its central 512-pixel crop")
    parser.add_argument("--variant", choices=("cpu", "cu118", "cu124", "cu133", "mps"))
    parser.add_argument("--runtime-policy", type=Path, default=GRAXPERT_RUNTIME_POLICY_PATH)
    args = parser.parse_args()
    if args.variant is None:
        parser.error("--variant must match the installed setup variant")
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
    report["graxpert"] = check_graxpert(args.graxpert_model, image, variant=args.variant)
    persist_graxpert_policy(report["graxpert"]["selected_policy"], args.runtime_policy)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
