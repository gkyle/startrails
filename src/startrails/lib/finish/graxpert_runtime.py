"""GraXpert session initialization, runtime policy resolution, and tiled inference engine."""

from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
import json
from typing import Any, Callable, Dict, Optional

import numpy as np
import onnxruntime as ort

from startrails.lib.finish.graxpert import (
    DEFAULT_STRIDE,
    INPUT_TENSOR_NAME,
    OUTPUT_TENSOR_NAME,
    WINDOW_SIZE,
    compute_graxpert_stats,
    graxpert_model_identity,
    graxpert_tile_postprocess,
    graxpert_tile_preprocess,
)
from startrails.lib.image_io import validate_image_array
from startrails.lib.model_manifest import GRAXPERT_MANIFEST
from startrails.paths import APPLICATION_DIR


GRAXPERT_RUNTIME_POLICY_PATH = APPLICATION_DIR / "runtime" / "graxpert-runtime.json"

CPU_EXECUTION_PROVIDER = "CPUExecutionProvider"
CUDA_EXECUTION_PROVIDER = "CUDAExecutionProvider"

# CUDA allocation failures are the only recognized recoverable execution errors.
# Tile inference runs one 256-pixel window at a time, so no smaller batch exists;
# recovery is an explained CPU retry of the whole image.
CUDA_ALLOCATION_ERROR_MARKERS = (
    "out of memory",
    "outofmemory",
    "out_of_memory",
    "cuda_error_out_of_memory",
    "cuda_error_launch_out_of_resources",
    "failed to allocate",
    "allocation failed",
    "cublas_status_alloc_failed",
    "cudnn_status_alloc_failed",
    "bad_alloc",
    "resource exhausted",
)


def is_cuda_allocation_failure(error: BaseException) -> bool:
    """Return whether an execution error is a recognizable allocation failure."""
    if isinstance(error, MemoryError):
        return True
    message = str(error).casefold()
    return any(marker in message for marker in CUDA_ALLOCATION_ERROR_MARKERS)


def resolve_graxpert_runtime_policy(policy_path: Path = GRAXPERT_RUNTIME_POLICY_PATH) -> Dict[str, Any]:
    """Read the environment's setup result; never probe or select providers here.

    Setup/repair replaces this file after real inference. It is independent of
    per-working-directory app state so every project uses the same verified lane.
    """
    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError("GraXpert runtime is not configured. Run StarTrails setup or repair.") from error
    if isinstance(policy, dict) and policy.get("verified") is False and policy.get("setup_error"):
        raise RuntimeError(policy["setup_error"])
    if (
        not isinstance(policy, dict)
        or policy.get("verified") is not True
        or policy.get("ort_version") != ort.__version__
        or policy.get("model_sha256") != GRAXPERT_MANIFEST.sha256
        or policy.get("provider") not in (CPU_EXECUTION_PROVIDER, CUDA_EXECUTION_PROVIDER)
    ):
        raise RuntimeError("GraXpert setup result is stale or invalid. Run StarTrails repair.")
    return policy


class GraXpertSession:
    """Manages an active GraXpert ONNX inference session and seamless tiled denoising."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        *,
        provider: str,
    ):
        self.model_path = model_path or (APPLICATION_DIR / "models" / GRAXPERT_MANIFEST.relative_path)
        if not self.model_path.is_file():
            raise FileNotFoundError(f"GraXpert model file not found: {self.model_path}")

        # Setup/repair already verified this pinned model. Processing consumes the
        # saved policy without rehashing or probing readiness at inference time.
        self.provider = provider
        self.configured_provider = provider
        self.execution_provider = provider
        self.fallback_reason: Optional[str] = None
        self.model_identity = graxpert_model_identity()

        try:
            self.session = self._create_ort_session(provider)
        except Exception as error:
            if not self._can_retry_on_cpu(error):
                raise
            self._activate_cpu_fallback(error)

    def _create_ort_session(self, provider: str):
        sess_options = ort.SessionOptions()
        sess_options.enable_cpu_mem_arena = True
        session = ort.InferenceSession(str(self.model_path), sess_options=sess_options, providers=[provider])
        session.disable_fallback()
        if session.get_providers()[0] != provider:
            raise RuntimeError(f"GraXpert could not use the configured provider {provider}. Run repair.")
        return session

    def _can_retry_on_cpu(self, error: BaseException) -> bool:
        return self.execution_provider == CUDA_EXECUTION_PROVIDER and is_cuda_allocation_failure(error)

    def _activate_cpu_fallback(self, error: BaseException) -> None:
        """Retry the whole image on CPU after a recognized CUDA allocation failure."""
        failed_provider = self.execution_provider
        try:
            self.session = self._create_ort_session(CPU_EXECUTION_PROVIDER)
        except Exception as cpu_error:
            raise RuntimeError(
                f"GraXpert {failed_provider} execution failed ({error}); CPU retry also failed: {cpu_error}"
            ) from cpu_error
        self.execution_provider = CPU_EXECUTION_PROVIDER
        self.fallback_reason = f"{failed_provider} allocation failure: {error}; retried on {CPU_EXECUTION_PROVIDER}."

    def denoise_full_strength(
        self,
        image: np.ndarray,
        progress_bar: Optional[Callable[[int, int, int, bool, Optional[dict]], None]] = None,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> np.ndarray:
        """Return the full-strength GraXpert endpoint with overlapping tiled blending.

        Interactive strength/scope blending happens in the composition owner, never
        here, so this endpoint can be cached once per separation/model identity.
        Recognized CUDA allocation failures retry the image on CPU; other errors
        surface unchanged.
        """
        validate_image_array(image)
        try:
            return self._denoise_with_active_session(image, progress_bar, should_interrupt)
        except Exception as error:
            if not self._can_retry_on_cpu(error):
                raise
            self._activate_cpu_fallback(error)
            return self._denoise_with_active_session(image, progress_bar, should_interrupt)

    def _denoise_with_active_session(
        self,
        image: np.ndarray,
        progress_bar: Optional[Callable[[int, int, int, bool, Optional[dict]], None]],
        should_interrupt: Optional[Callable[[], bool]],
    ) -> np.ndarray:
        if should_interrupt and should_interrupt():
            raise CancelledError("GraXpert denoising cancelled before start")

        source_h, source_w, c = image.shape
        median, mad = compute_graxpert_stats(image)
        # The model has a fixed 256-pixel input. Symmetric padding also handles
        # a one-pixel dimension; crop only after full-size tile accumulation.
        padded = (
            np.pad(
                image,
                ((0, max(0, WINDOW_SIZE - source_h)), (0, max(0, WINDOW_SIZE - source_w)), (0, 0)),
                mode="symmetric",
            )
            if source_h < WINDOW_SIZE or source_w < WINDOW_SIZE
            else image
        )
        h, w = padded.shape[:2]

        # 2D Hann window for smooth overlap interpolation without boundary grid seams
        w1d = np.sin(np.pi * (np.arange(WINDOW_SIZE) + 0.5) / WINDOW_SIZE) ** 2
        window_weight = np.outer(w1d, w1d)[:, :, None].astype(np.float32)

        y_coords = list(range(0, max(1, h - WINDOW_SIZE + 1), DEFAULT_STRIDE))
        if not y_coords or y_coords[-1] + WINDOW_SIZE < h:
            y_coords.append(max(0, h - WINDOW_SIZE))

        x_coords = list(range(0, max(1, w - WINDOW_SIZE + 1), DEFAULT_STRIDE))
        if not x_coords or x_coords[-1] + WINDOW_SIZE < w:
            x_coords.append(max(0, w - WINDOW_SIZE))

        total_tiles = len(y_coords) * len(x_coords)
        accum_denoised = np.zeros((h, w, c), dtype=np.float32)
        accum_weight = np.zeros((h, w, 1), dtype=np.float32)

        completed_tiles = 0
        if progress_bar is not None:
            progress_bar(total_tiles, 0, 0, False, {"desc": "Denoising starless image..."})

        for y in y_coords:
            for x in x_coords:
                if should_interrupt and should_interrupt():
                    raise CancelledError("GraXpert denoising cancelled by user")

                actual_y = min(y, max(0, h - WINDOW_SIZE))
                actual_x = min(x, max(0, w - WINDOW_SIZE))
                tile = padded[actual_y : actual_y + WINDOW_SIZE, actual_x : actual_x + WINDOW_SIZE]

                # Preprocess tile
                batch = graxpert_tile_preprocess(tile, median, mad)[None]
                output = self.session.run([OUTPUT_TENSOR_NAME], {INPUT_TENSOR_NAME: batch})[0]
                denoised_tile = graxpert_tile_postprocess(output[0], tile, median, mad)

                accum_denoised[actual_y : actual_y + WINDOW_SIZE, actual_x : actual_x + WINDOW_SIZE] += (
                    denoised_tile * window_weight
                )
                accum_weight[actual_y : actual_y + WINDOW_SIZE, actual_x : actual_x + WINDOW_SIZE] += window_weight

                completed_tiles += 1
                if progress_bar is not None:
                    progress_bar(
                        total_tiles,
                        1,
                        completed_tiles,
                        completed_tiles == total_tiles,
                        {"desc": f"Denoising tile {completed_tiles}/{total_tiles}..."},
                    )

        # Every covered weight is positive, even at image corners. Flooring tiny
        # Hann weights would darken those pixels instead of normalizing them.
        denoised_full = (accum_denoised / accum_weight)[:source_h, :source_w]
        denoised_full = np.clip(denoised_full, 0.0, 1.0).astype(np.float32)

        return denoised_full
