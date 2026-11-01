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
from startrails.lib.finish.graxpert_runtime import GRAXPERT_RUNTIME_POLICY_PATH
from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.finish.starnet import build_starnet_cli_args, run_starnet_process
from startrails.lib.image_io import imread, imwrite, normalize_image
from startrails.lib.model_manifest import GRAXPERT_MANIFEST
from startrails.lib.signatures import verify_file_integrity
from startrails.lib.starnet_setup import (
    probe_starnet_installation,
    record_starnet_installation,
    validate_starnet_installation,
    STARNET_TERMS_TEXT,
    starnet_terms_accepted,
    create_starnet_smoke_image,
    STARNET_SMOKE_SIZE_PIXELS,
)
from startrails.paths import APPLICATION_DIR

SMOKE_IMAGE_SIZE = STARNET_SMOKE_SIZE_PIXELS
CLI_DIFF_TOLERANCE_SAMPLES = 1


def check_graxpert(model_path: Path, image: np.ndarray, *, variant: str) -> dict:
    """Setup owns selection; verify actual GPU kernels, explicitly report CPU fallback."""
    if not verify_file_integrity(model_path, GRAXPERT_MANIFEST.sha256, GRAXPERT_MANIFEST.size_bytes):
        raise ValueError(f"Missing or unverified GraXpert model: {model_path}")
    started = perf_counter()
    median, mad = compute_graxpert_stats(image)
    tile = image[:WINDOW_SIZE, :WINDOW_SIZE]
    if tile.shape != (WINDOW_SIZE, WINDOW_SIZE, 3):
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


def persist_graxpert_policy(policy: dict, path: Path) -> None:
    with ArtifactTransaction() as transaction:
        staged = transaction.stage(path)
        staged.write_text(json.dumps(policy, indent=2), encoding="utf-8")
        transaction.commit()


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
    parser.add_argument(
        "--persist-state",
        type=Path,
        nargs="?",
        const=Path("app.json"),
        help="Persist the verified StarNet installation and accepted terms into application state JSON",
    )
    parser.add_argument("--variant", choices=("cpu", "cu118", "cu124", "cu133", "mps"))
    parser.add_argument("--runtime-policy", type=Path, default=GRAXPERT_RUNTIME_POLICY_PATH)
    parser.add_argument("--show-starnet-terms", action="store_true", help="Print the full applicable agreement")
    parser.add_argument(
        "--accept-starnet-terms", action="store_true", help="Affirm acceptance of the displayed full agreement"
    )
    args = parser.parse_args()
    if args.show_starnet_terms:
        print(STARNET_TERMS_TEXT)
        return
    if args.variant is None:
        parser.error("--variant must match the installed setup variant")
    state = {}
    if args.persist_state is not None and args.persist_state.is_file():
        state = json.loads(args.persist_state.read_text(encoding="utf-8"))
        if not isinstance(state, dict):
            raise ValueError("Application state must be a JSON object.")
    if args.starnet is not None and not (args.accept_starnet_terms or starnet_terms_accepted(state)):
        parser.error("Read --show-starnet-terms, then pass --accept-starnet-terms before testing StarNet.")
    if args.image is None:
        pixels = create_starnet_smoke_image()
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
    starnet_inst = None
    if args.starnet is not None:
        image, report["starnet"] = check_starnet(args.starnet, pixels)
        starnet_inst = validate_starnet_installation(args.starnet)
    report["graxpert"] = check_graxpert(args.graxpert_model, image, variant=args.variant)
    persist_graxpert_policy(report["graxpert"]["selected_policy"], args.runtime_policy)
    print(json.dumps(report, indent=2))

    if args.persist_state is not None:
        state_path = args.persist_state
        if starnet_inst is not None:
            record_starnet_installation(state, starnet_inst, managed=False, terms_accepted=True)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with ArtifactTransaction() as transaction:
            staged = transaction.stage(state_path)
            staged.write_text(json.dumps(state, indent=4), encoding="utf-8")
            transaction.commit()
        print(f"Persisted setup state to {state_path}")


if __name__ == "__main__":
    main()
