"""Explicit setup-time smoke checks for 3P assets; never runs during inference.

Run with the selected environment after preparing the release model archive.
An optional trusted StarNet installation and sample image exercise CLI exchange.
"""

import argparse
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import onnxruntime as ort

from startrails.lib.finish.graxpert import (
    INPUT_TENSOR_NAME,
    OUTPUT_TENSOR_NAME,
    WINDOW_SIZE,
    compute_graxpert_stats,
    graxpert_tile_postprocess,
    graxpert_tile_preprocess,
)
from startrails.lib.finish.starnet import build_starnet_cli_args, run_starnet_process
from startrails.lib.image_io import imread, imwrite, normalize_image
from startrails.lib.model_manifest import GRAXPERT_MANIFEST
from startrails.lib.signatures import verify_file_integrity
from startrails.lib.starnet_setup import probe_starnet_installation, validate_starnet_installation
from startrails.paths import APPLICATION_DIR

SMOKE_IMAGE_SIZE = 512  # StarNet's minimum unscaled input dimension.
CLI_DIFF_TOLERANCE_SAMPLES = 1


def check_graxpert(model_path: Path, image: np.ndarray) -> dict:
    if not verify_file_integrity(model_path, GRAXPERT_MANIFEST.sha256, GRAXPERT_MANIFEST.size_bytes):
        raise ValueError(f"Missing or unverified GraXpert model: {model_path}")
    started = perf_counter()
    # CPU is the initial release baseline on every app dependency variant.
    # CUDA selection remains gated on separate setup validation of its package lane.
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    median, mad = compute_graxpert_stats(image)
    tile = image[:WINDOW_SIZE, :WINDOW_SIZE]
    batch = graxpert_tile_preprocess(tile, median, mad)[None]
    output = session.run([OUTPUT_TENSOR_NAME], {INPUT_TENSOR_NAME: batch})[0]
    if output.shape != batch.shape or output.dtype != np.float32 or not np.isfinite(output).all():
        raise ValueError("GraXpert produced an invalid denoise tensor")
    restored = graxpert_tile_postprocess(output[0], tile, median, mad)
    if not np.isfinite(restored).all() or np.any(restored < 0) or np.any(restored > 1):
        raise ValueError("GraXpert postprocessing produced invalid pixels")
    return {
        "version": ort.__version__,
        "providers": session.get_providers(),
        "shape": list(output.shape),
        "seconds": perf_counter() - started,
    }


def check_starnet(location: Path, pixels: np.ndarray) -> tuple[np.ndarray, dict]:
    installation = validate_starnet_installation(location)
    probe = probe_starnet_installation(installation)
    started = perf_counter()
    with TemporaryDirectory(prefix="startrails_finish_setup_") as temporary:
        root = Path(temporary)
        source, starless, stars = (root / name for name in ("source.tif", "starless.tif", "stars.tif"))
        imwrite(source, pixels, convertBGR=True, bit_depth=pixels.dtype.itemsize * 8)
        events = []
        cmd = build_starnet_cli_args(str(installation.executable), str(source), str(starless), mask_path=str(stars))
        run_starnet_process(cmd, progress_callback=events.append)
        result = imread(starless, to_rgb=True)
        difference = imread(stars, to_rgb=True)
        if result.shape != pixels.shape or result.dtype != pixels.dtype:
            raise ValueError("StarNet changed the exchange image's dimensions or bit depth")
        if difference.shape != pixels.shape or difference.dtype != pixels.dtype:
            raise ValueError("StarNet produced an invalid difference image")
        expected = np.maximum(pixels.astype(np.int32) - result.astype(np.int32), 0)
        max_error = int(np.max(np.abs(difference.astype(np.int32) - expected)))
        if max_error > CLI_DIFF_TOLERANCE_SAMPLES:
            raise ValueError("StarNet difference image disagrees with source minus saved starless")
    return normalize_image(result), {
        "identity": f"{probe.version}-{probe.build}/{probe.backend_id}",
        "seconds": perf_counter() - started,
        "dtype": str(result.dtype),
        "shape": list(result.shape),
        "difference_max_error_samples": max_error,
        "progress_events": len(events),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graxpert-model", type=Path, default=APPLICATION_DIR / "models" / GRAXPERT_MANIFEST.relative_path
    )
    parser.add_argument("--starnet", type=Path, help="Trusted installation directory or executable")
    parser.add_argument("--image", type=Path, help="Sample RGB image; check its central 512-pixel crop")
    args = parser.parse_args()
    if args.image is None:
        pixels = np.full((SMOKE_IMAGE_SIZE, SMOKE_IMAGE_SIZE, 3), 32768, np.uint16)
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
    if args.starnet is not None:
        image, report["starnet"] = check_starnet(args.starnet, pixels)
    report["graxpert"] = check_graxpert(args.graxpert_model, image)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
