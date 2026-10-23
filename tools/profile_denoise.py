"""Profile denoise operations without replacing the project's stack artifacts.

Run with PYTHONPATH=src .venv/bin/python tools/profile_denoise.py PROJECT.
All scratch files and encoded output images live in a temporary directory.
The project's persistent master-dark cache is reused (or populated). Timings of nested calls
overlap; timings of parallel calls are summed, not elapsed wall time.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
from functools import wraps
import json
from pathlib import Path
import platform
import resource
from tempfile import TemporaryDirectory
from threading import Lock
from time import perf_counter
from unittest.mock import patch

import cv2
import jsonpickle
import numpy as np

from startrails.lib.denoise.alignment.detector import StarDetector
from startrails.lib.denoise.alignment.matcher import StarMatcher
from startrails.lib.denoise.alignment.warper import ImageWarper
from startrails.lib.denoise.calibration import dark
from startrails.lib.denoise.stacking import freeze_ground
from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
from startrails.lib.denoise.stacking.disk_buffer import DiskFrameBuffer
from startrails.lib.gpu import get_array_module
from startrails.lib.project_denoise import DenoiseProject
from startrails.op.denoise import align_stars, stack_denoise


class Timings:
    def __init__(self):
        self.calls = defaultdict(lambda: {"calls": 0, "seconds": 0.0})
        self.lock = Lock()

    def wrap(self, label, function):
        @wraps(function)
        def measured(*args, **kwargs):
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                elapsed = perf_counter() - start
                with self.lock:
                    self.calls[label]["calls"] += 1
                    self.calls[label]["seconds"] += elapsed
        return measured

    def install(self, patches):
        targets = [
            (align_stars, "imread", "alignment.decode"),
            (dark, "imread", "dark.decode"),
            (freeze_ground, "imread", "stack.decode"),
            (stack_denoise, "imwrite", "output.encode"),
            (dark.DarkCalibrator, "compute_master_dark_from_paths", "dark.total"),
            (dark.DarkCalibrator, "compute_master_dark", "dark.integrate"),
            (dark.DarkCalibrator, "subtract_dark", "calibration.subtract"),
            (StarDetector, "detect_stars", "alignment.detect"),
            (StarMatcher, "match_stars", "alignment.match"),
            (ImageWarper, "warp", "stack.warp"),
            (ImageWarper, "warp_mask", "stack.warp_mask"),
            (ImageWarper, "compute_tapered_mask", "stack.taper"),
            (DiskFrameBuffer, "write_frame", "scratch.write"),
            (DiskFrameBuffer, "read_rows", "scratch.read"),
            (np.memmap, "flush", "scratch.flush"),
            (freeze_ground.FreezeGroundStacker, "stack_frames", "stack.reduce"),
            (HorizonCompositor, "__init__", "compositor.prepare"),
        ]
        for owner, name, label in targets:
            patches.enter_context(patch.object(owner, name, self.wrap(label, getattr(owner, name))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path)
    parser.add_argument("--operation", choices=("align", "stack", "both"), default="both")
    parser.add_argument("--reuse-alignment", action="store_true", help="Keep cached transforms during Align Stars")
    parser.add_argument("--output", type=Path, help="Write a JSON timing report")
    parser.add_argument("--scratch-dir", type=Path, help="Parent for temporary benchmark files")
    parser.add_argument("--compress-intermediates", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--max-workers", type=int)
    parser.add_argument("--verify-existing", action="store_true", help="Compare saved sky/ground/base pixels")
    args = parser.parse_args()

    project = jsonpickle.decode(args.project.read_text(), keys=True)
    if not isinstance(project, DenoiseProject):
        parser.error("Expected a DenoiseProject")
    config = project.to_denoise_config()
    if args.compress_intermediates is not None:
        config.compress_intermediate_tiffs = args.compress_intermediates
    if args.max_workers is not None:
        config.max_workers = args.max_workers
    if args.operation in ("align", "both") and not args.reuse_alignment:
        config.homographies = {}
    if args.operation == "stack":
        base = align_stars.AlignStars.get_base_image_path(config)
        missing = [p for p in config.star_images if p.resolve() != base and p.resolve() not in config.homographies]
        if missing:
            parser.error("Stack profiling requires saved transforms; use --operation both to align first")

    backend, _ = get_array_module(config.use_gpu)
    report = {
        "project": str(args.project),
        "platform": platform.platform(),
        "numpy": np.__version__,
        "opencv": cv2.__version__,
        "opencv_threads": cv2.getNumThreads(),
        "stack_backend": backend.__name__,
        "light_frames": len(config.star_images),
        "dark_frames": len(config.noise_images),
        "stack_method": config.stack_method,
        "sigma_threshold": config.sigma_clip_threshold,
        "sigma_iterations": config.sigma_clip_iterations,
        "max_workers_setting": config.max_workers,
        "compress_intermediate_tiffs": getattr(config, "compress_intermediate_tiffs", True),
        "alignment_mode": "saved" if args.operation == "stack" or args.reuse_alignment else "fresh",
        "operations": {},
    }
    with TemporaryDirectory(prefix="startrails_profile_", dir=args.scratch_dir) as scratch:
        for name, filename in (
            ("output_path", "output.tif"), ("sky_stack_path", "sky_stack.tif"),
            ("ground_stack_path", "ground_stack.tif"), ("gradient_mask_path", "gradient_mask.png"),
        ):
            setattr(config, name, Path(scratch) / filename)

        for name in (("align", "stack") if args.operation == "both" else (args.operation,)):
            timings = Timings()
            start = perf_counter()

            def progress(total, increment, count, done, data):
                description = (data.get("desc") or data.get("filename") or data.get("stage")) if data else "starting"
                print(f"{name} {perf_counter() - start:.1f}s {count}/{total}: {description}", flush=True)

            operation = align_stars.AlignStars() if name == "align" else stack_denoise.StackDenoise()
            operation.addObserver(progress)
            with ExitStack() as patches:
                timings.install(patches)
                result = operation.align(config, warp_frames=False) if name == "align" else operation.stack(config)
            if result is None:
                raise RuntimeError(f"{name} was interrupted")
            detail = {"wall_seconds": perf_counter() - start, "timings": dict(timings.calls)}
            if name == "align":
                detail["aligned_frames"] = len(result.homographies)
            elif args.verify_existing:
                for filename, pixels in (("sky_stack.tif", result.sky_stack),
                                         ("ground_stack.tif", result.ground_stack),
                                         ("base_composite.tif", result.base_composite)):
                    reference = cv2.imread(str(project.get_output_dir() / filename), cv2.IMREAD_UNCHANGED)
                    if reference is None or reference.dtype != np.uint16:
                        raise ValueError(f"Expected uint16 reference {filename}")
                    if reference.ndim == 3:
                        reference = reference[..., ::-1]
                    for row in range(0, len(pixels), 64):
                        encoded_pixels = np.clip(pixels[row:row+64] * 65535.0 + 0.5, 0, 65535).astype(np.uint16)
                        np.testing.assert_array_equal(encoded_pixels, reference[row:row+64])
                    print(f"Exact pixel match: {filename}", flush=True)
                    del reference
                detail["exact_pixel_match"] = True
            report["operations"][name] = detail
            del result
            print(json.dumps(detail, indent=2), flush=True)

    # ru_maxrss is bytes on macOS and KiB on Linux; it is cumulative for both operations.
    peak_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report["peak_rss_bytes"] = peak_rss if platform.system() == "Darwin" else peak_rss * 1024
    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.write_text(encoded + "\n")
    print(encoded)


if __name__ == "__main__":
    main()
