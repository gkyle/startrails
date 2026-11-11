"""NoxColor PyTorch star-removal model, tiled Hann-blended inference, and radial chroma post-filter."""

from __future__ import annotations

from collections import OrderedDict
from concurrent.futures import CancelledError
from dataclasses import dataclass
import math
from pathlib import Path
import time
from typing import Callable, List, Optional, Tuple, Union

import cv2
import numpy as np
import scipy.ndimage as ndi
import torch
import torch.nn as nn
import torch.nn.functional as F

from startrails.lib.finish.defaults import (
    DEFAULT_NOX_STRIDE,
    NOX_MODEL_FILENAME,
    NOX_MODEL_RELATIVE_PATH,
)
from startrails.lib.gpu import (
    free_gpu_memory,
    is_cuda_allocation_failure,
    resolve_torch_device as resolve_nox_device,
)
from startrails.lib.image_io import validate_image_array
from startrails.paths import APPLICATION_DIR


FILTERS: Tuple[int, ...] = (64, 128, 256, 512, 512, 512, 512, 512, 512, 512, 512, 512, 256, 128, 64)
NUM_ENCODER_LAYERS = 8
NUM_DECODER_LAYERS = 8
IN_CHANNELS = 3
OUT_CHANNELS = 3
KERNEL_SIZE = 4
CONV_STRIDE = 2
PADDING = 1
LAYER_NORM_EPS = 1e-3
LEAKY_ALPHA = 0.2
MIN_SPATIAL_SIZE = 256
SPATIAL_SIZE_MULTIPLE = 256
EXPECTED_PARAM_COUNT = 54_420_483
EXPECTED_WEIGHT_TENSOR_COUNT = 60
ARCHITECTURE = "nox_color"

WINDOW_SIZE = 512
DEFAULT_STRIDE = DEFAULT_NOX_STRIDE
MIN_STRIDE = 2
MAX_STRIDE = 512
DEFAULT_BATCH_SIZE = 4
HANN_MIN_WEIGHT = 1e-4
WEIGHT_NORM_EPS = 1e-8


def nox_model_identity() -> str:
    """Return the identity of the bundled Nox weights used in separation cache keys."""
    return f"{ARCHITECTURE}:{NOX_MODEL_RELATIVE_PATH}"


def validate_separation_stride(stride: int, window_size: int = WINDOW_SIZE) -> None:
    """Validate that the tile stride is an even integer within [MIN_STRIDE, window_size]."""
    if type(stride) is not int or stride < MIN_STRIDE or stride > window_size or stride % 2 != 0:
        raise ValueError(f"Stride must be an even integer between {MIN_STRIDE} and {window_size}, got {stride}")


def encoder_channels(layer_index: int) -> Tuple[int, int]:
    """Return (in_channels, out_channels) for encoder convolution i."""
    if not 0 <= layer_index < NUM_ENCODER_LAYERS:
        raise ValueError(f"encoder layer index out of range: {layer_index}")
    in_channels = IN_CHANNELS if layer_index == 0 else FILTERS[layer_index - 1]
    return in_channels, FILTERS[layer_index]


def decoder_channels(layer_index: int) -> Tuple[int, int]:
    """Return (in_channels, out_channels) for decoder block j."""
    if not 0 <= layer_index < NUM_DECODER_LAYERS:
        raise ValueError(f"decoder block index out of range: {layer_index}")
    keras_layer = layer_index + 8
    out_channels = OUT_CHANNELS if layer_index == NUM_DECODER_LAYERS - 1 else FILTERS[keras_layer]
    if layer_index == 0:
        in_channels = FILTERS[NUM_ENCODER_LAYERS - 1]
    else:
        in_channels = FILTERS[keras_layer - 1] + FILTERS[15 - keras_layer]
    return in_channels, out_channels


def expected_state_dict_shapes() -> "OrderedDict[str, Tuple[int, ...]]":
    """Return the exact state-dict keys and shapes of NoxColor."""
    shapes: "OrderedDict[str, Tuple[int, ...]]" = OrderedDict()

    for i in range(NUM_ENCODER_LAYERS):
        in_ch, out_ch = encoder_channels(i)
        shapes[f"encoders.{i}.conv.weight"] = (out_ch, in_ch, KERNEL_SIZE, KERNEL_SIZE)
        shapes[f"encoders.{i}.conv.bias"] = (out_ch,)
        if i > 0:
            shapes[f"encoders.{i}.norm.gamma"] = (out_ch,)
            shapes[f"encoders.{i}.norm.beta"] = (out_ch,)

    for j in range(NUM_DECODER_LAYERS):
        in_ch, out_ch = decoder_channels(j)
        shapes[f"decoders.{j}.deconv.weight"] = (in_ch, out_ch, KERNEL_SIZE, KERNEL_SIZE)
        shapes[f"decoders.{j}.deconv.bias"] = (out_ch,)
        if j < NUM_DECODER_LAYERS - 1:
            shapes[f"decoders.{j}.norm.gamma"] = (out_ch,)
            shapes[f"decoders.{j}.norm.beta"] = (out_ch,)

    return shapes


class ChannelLayerNorm(nn.Module):
    """LayerNorm over channels only, with explicit primitive operations."""

    def __init__(self, num_channels: int, eps: float = LAYER_NORM_EPS) -> None:
        super().__init__()
        self.num_channels = int(num_channels)
        self.eps = float(eps)
        self.gamma = nn.Parameter(torch.ones(self.num_channels))
        self.beta = nn.Parameter(torch.zeros(self.num_channels))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mean = x.mean(dim=1, keepdim=True)
        diff = x - mean
        variance = (diff * diff).mean(dim=1, keepdim=True)
        normalized = diff / torch.sqrt(variance + self.eps)
        return normalized * self.gamma.view(1, -1, 1, 1) + self.beta.view(1, -1, 1, 1)

    def extra_repr(self) -> str:
        return f"{self.num_channels}, eps={self.eps}"


class EncoderBlock(nn.Module):
    """One encoder convolution, optional pre-activation and post-LayerNorm."""

    def __init__(self, in_channels: int, out_channels: int, *, normalize: bool) -> None:
        super().__init__()
        self.conv = nn.Conv2d(
            in_channels,
            out_channels,
            kernel_size=KERNEL_SIZE,
            stride=CONV_STRIDE,
            padding=PADDING,
            bias=True,
        )
        self.norm: Optional[ChannelLayerNorm] = ChannelLayerNorm(out_channels) if normalize else None

    def forward(self, x: torch.Tensor, *, apply_leaky_relu: bool) -> torch.Tensor:
        if apply_leaky_relu:
            x = F.leaky_relu(x, negative_slope=LEAKY_ALPHA)
        x = self.conv(x)
        if self.norm is not None:
            x = self.norm(x)
        return x


class DecoderBlock(nn.Module):
    """One transposed convolution with optional post-LayerNorm."""

    def __init__(self, in_channels: int, out_channels: int, *, normalize: bool) -> None:
        super().__init__()
        self.deconv = nn.ConvTranspose2d(
            in_channels,
            out_channels,
            kernel_size=KERNEL_SIZE,
            stride=CONV_STRIDE,
            padding=PADDING,
            bias=True,
        )
        self.norm: Optional[ChannelLayerNorm] = ChannelLayerNorm(out_channels) if normalize else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.deconv(x)
        if self.norm is not None:
            x = self.norm(x)
        return x


class NoxColor(nn.Module):
    """NCHW Nox color star-removal generator."""

    def __init__(self) -> None:
        super().__init__()
        encoders = []
        for i in range(NUM_ENCODER_LAYERS):
            in_ch, out_ch = encoder_channels(i)
            encoders.append(EncoderBlock(in_ch, out_ch, normalize=i > 0))
        self.encoders = nn.ModuleList(encoders)

        decoders = []
        for j in range(NUM_DECODER_LAYERS):
            in_ch, out_ch = decoder_channels(j)
            decoders.append(DecoderBlock(in_ch, out_ch, normalize=j < NUM_DECODER_LAYERS - 1))
        self.decoders = nn.ModuleList(decoders)

    @staticmethod
    def validate_input(x: torch.Tensor) -> None:
        """Validate an NCHW image/normalized tensor before inference."""
        if not isinstance(x, torch.Tensor):
            raise TypeError(f"expected a torch.Tensor, got {type(x).__name__}")
        if not torch.is_floating_point(x):
            raise TypeError(f"expected a floating-point tensor (e.g. float32), got dtype {x.dtype}")
        if x.ndim != 4:
            raise ValueError(f"expected NCHW rank-4 input, got shape {tuple(x.shape)}")
        if x.shape[1] != IN_CHANNELS:
            raise ValueError(f"expected {IN_CHANNELS} channels (RGB), got {x.shape[1]}")
        height, width = int(x.shape[-2]), int(x.shape[-1])
        if height < MIN_SPATIAL_SIZE or width < MIN_SPATIAL_SIZE:
            raise ValueError(
                f"spatial dimensions must be at least {MIN_SPATIAL_SIZE}x{MIN_SPATIAL_SIZE}, got {height}x{width}"
            )
        if height % SPATIAL_SIZE_MULTIPLE != 0 or width % SPATIAL_SIZE_MULTIPLE != 0:
            raise ValueError(
                f"spatial dimensions must be divisible by {SPATIAL_SIZE_MULTIPLE}, got {height}x{width}"
            )

    def _check_input_dtype(self, x: torch.Tensor) -> None:
        parameter = next(self.parameters())
        if x.dtype != parameter.dtype:
            raise TypeError(
                f"input dtype {x.dtype} does not match model parameter dtype "
                f"{parameter.dtype}; convert the input or model explicitly"
            )

    def _forward_normalized(self, x_norm: torch.Tensor) -> torch.Tensor:
        normalized_input = x_norm
        skips = []
        for i, block in enumerate(self.encoders):
            x_norm = block(x_norm, apply_leaky_relu=i > 0)
            skips.append(x_norm)

        for j, block in enumerate(self.decoders):
            keras_layer = j + 8
            if keras_layer == 8:
                x_norm = F.relu(x_norm)
            else:
                x_norm = torch.cat([x_norm, skips[15 - keras_layer]], dim=1)
                x_norm = F.relu(x_norm)
            x_norm = block(x_norm)

        residual = F.relu(x_norm)
        return normalized_input - residual

    def forward(self, image: torch.Tensor) -> torch.Tensor:
        """Map image-space [0, 1] NCHW input to unclipped image-space output."""
        self.validate_input(image)
        self._check_input_dtype(image)
        x_norm = image * 2.0 - 1.0
        out_norm = self._forward_normalized(x_norm)
        return (out_norm + 1.0) * 0.5

    def forward_normalized(self, x_norm: torch.Tensor) -> torch.Tensor:
        """Run the normalized [-1, 1] core and return unclipped values."""
        self.validate_input(x_norm)
        self._check_input_dtype(x_norm)
        return self._forward_normalized(x_norm)

    def num_parameters(self) -> int:
        """Total number of scalar parameters (expected 54,420,483)."""
        return sum(p.numel() for p in self.parameters())

    def num_weight_tensors(self) -> int:
        """Number of stored state-dict tensors (expected 60)."""
        return len(self.state_dict())


# -----------------------------------------------------------------------------
# Radial Chrominance Post-Filter
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class RadialChromaConfig:
    """Parameters controlling targeted radial chrominance neutralization."""

    peak_thresh: float = 0.4
    nms_size: int = 21
    inner_radius: float = 16.0
    outer_radius: float = 28.0
    exclude_radius: float = 12.0
    min_ring_pixels: int = 20


@dataclass(frozen=True)
class PostfilterStats:
    """Summary diagnostics from applying the radial chrominance post-filter."""

    detected_stars: int
    applied_stars: int
    touched_fraction: float
    elapsed_seconds: float


def detect_removed_star_centroids(
    inp: np.ndarray,
    pred: np.ndarray,
    peak_thresh: float = 0.4,
    nms_size: int = 21,
) -> np.ndarray:
    """Return (N, 2) integer (y, x) centroids of bright removed stars."""
    diff_luma = np.mean(np.clip(inp - pred, 0.0, 1.0), axis=-1)
    max_filt = ndi.maximum_filter(diff_luma, size=nms_size)
    peaks = (diff_luma > peak_thresh) & (max_filt == diff_luma)
    return np.argwhere(peaks)


def _local_grid_distances(
    cy: int,
    cx: int,
    y0: int,
    y1: int,
    x0: int,
    x1: int,
) -> np.ndarray:
    """Compute Euclidean pixel distances from (cy, cx) on a sliced patch."""
    yy, xx = np.ogrid[y0:y1, x0:x1]
    return np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2).astype(np.float32)


def _build_star_exclusion_mask(
    shape: Tuple[int, int],
    centroids: np.ndarray,
    exclude_radius: float,
) -> np.ndarray:
    """Mask pixels within exclude_radius of detected stars so rings avoid neighbors."""
    h, w = shape
    mask = np.zeros((h, w), dtype=bool)
    r_pad = int(math.ceil(exclude_radius))
    r2 = float(exclude_radius * exclude_radius)
    for cy_i, cx_i in centroids:
        cy, cx = int(cy_i), int(cx_i)
        y0, y1 = max(0, cy - r_pad), min(h, cy + r_pad + 1)
        x0, x1 = max(0, cx - r_pad), min(w, cx + r_pad + 1)
        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask[y0:y1, x0:x1] |= ((xx - cx) ** 2 + (yy - cy) ** 2) <= r2
    return mask


def apply_radial_chroma_postfilter(
    inp: np.ndarray,
    pred: np.ndarray,
    config: Optional[RadialChromaConfig] = None,
    *,
    progress_bar: Optional[Callable[[int, int, int, bool, Optional[dict]], None]] = None,
    should_interrupt: Optional[Callable[[], bool]] = None,
) -> Tuple[np.ndarray, PostfilterStats]:
    """Apply targeted radial chroma neutralization to pred given inp.

    Both inp and pred must be HWC float32 arrays normalized to [0, 1].
    Pixels outside config.inner_radius of any detected removed star centroid
    are returned bit-exact identical to pred.
    """
    if should_interrupt and should_interrupt():
        raise CancelledError("Chroma post-filter cancelled before starting.")
    t0 = time.perf_counter()
    cfg = config or RadialChromaConfig()
    inp_f = np.asarray(inp, dtype=np.float32)
    pred_f = np.asarray(pred, dtype=np.float32)
    h, w = pred_f.shape[:2]

    if progress_bar is not None:
        progress_bar(1, 0, 0, False, {"desc": "Applying chroma post-filter: detecting star halos..."})

    centroids = detect_removed_star_centroids(
        inp_f,
        pred_f,
        peak_thresh=cfg.peak_thresh,
        nms_size=cfg.nms_size,
    )
    if should_interrupt and should_interrupt():
        raise CancelledError("Chroma post-filter cancelled after star detection.")
    total_stars = int(len(centroids))
    if total_stars == 0:
        if progress_bar is not None:
            progress_bar(1, 1, 1, True, {"desc": "Chroma post-filter complete (no bright halos)."})
        return pred_f.copy(), PostfilterStats(0, 0, 0.0, time.perf_counter() - t0)

    pred_clipped = np.clip(pred_f, 0.0, 1.0)
    yuv = cv2.cvtColor(pred_clipped, cv2.COLOR_RGB2YCrCb)
    y_orig, cr_orig, cb_orig = yuv[:, :, 0], yuv[:, :, 1], yuv[:, :, 2]

    exclusion_mask = _build_star_exclusion_mask((h, w), centroids, cfg.exclude_radius)
    pad = int(math.ceil(cfg.outer_radius))

    max_w = np.zeros((h, w), dtype=np.float32)
    cr_sum = np.zeros((h, w), dtype=np.float32)
    cb_sum = np.zeros((h, w), dtype=np.float32)
    w_sum = np.zeros((h, w), dtype=np.float32)
    applied = 0
    report_interval = max(1, total_stars // 10)
    last_reported = 0

    for idx, (cy_i, cx_i) in enumerate(centroids, start=1):
        if should_interrupt and should_interrupt():
            raise CancelledError("Chroma post-filter cancelled.")
        cy, cx = int(cy_i), int(cx_i)
        y0, y1 = max(0, cy - pad), min(h, cy + pad + 1)
        x0, x1 = max(0, cx - pad), min(w, cx + pad + 1)

        dist = _local_grid_distances(cy, cx, y0, y1, x0, x1)
        ring_base = (dist >= cfg.inner_radius) & (dist <= cfg.outer_radius)
        ring = ring_base & (~exclusion_mask[y0:y1, x0:x1])
        if np.count_nonzero(ring) <= cfg.min_ring_pixels:
            ring = ring_base
        if np.count_nonzero(ring) <= cfg.min_ring_pixels:
            continue

        bg_cr = float(np.median(cr_orig[y0:y1, x0:x1][ring]))
        bg_cb = float(np.median(cb_orig[y0:y1, x0:x1][ring]))
        hw = np.clip(1.0 - (dist / cfg.inner_radius), 0.0, 1.0).astype(np.float32)

        cr_sum[y0:y1, x0:x1] += hw * bg_cr
        cb_sum[y0:y1, x0:x1] += hw * bg_cb
        w_sum[y0:y1, x0:x1] += hw
        max_w[y0:y1, x0:x1] = np.maximum(max_w[y0:y1, x0:x1], hw)
        applied += 1
        if progress_bar is not None and (idx - last_reported >= report_interval or idx == total_stars):
            step = idx - last_reported
            last_reported = idx
            progress_bar(
                total_stars,
                step,
                idx,
                False,
                {"desc": f"Applying chroma post-filter ({idx}/{total_stars} stars)..."},
            )

    active = max_w > 0.0
    if not np.any(active):
        if progress_bar is not None:
            remaining = max(0, total_stars - last_reported)
            progress_bar(total_stars, remaining, total_stars, True, {"desc": "Chroma post-filter complete."})
        return pred_f.copy(), PostfilterStats(total_stars, applied, 0.0, time.perf_counter() - t0)

    safe_w = np.maximum(w_sum, 1e-6)
    cr_target = np.where(w_sum > 1e-6, cr_sum / safe_w, cr_orig)
    cb_target = np.where(w_sum > 1e-6, cb_sum / safe_w, cb_orig)

    cr_out = (1.0 - max_w) * cr_orig + max_w * cr_target
    cb_out = (1.0 - max_w) * cb_orig + max_w * cb_target

    yuv_fixed = np.stack([y_orig, cr_out, cb_out], axis=-1).astype(np.float32)
    rgb_fixed = np.clip(cv2.cvtColor(yuv_fixed, cv2.COLOR_YCrCb2RGB), 0.0, 1.0)

    out = np.where(active[:, :, None], rgb_fixed, pred_f)
    if progress_bar is not None:
        remaining = max(0, total_stars - last_reported)
        progress_bar(total_stars, remaining, total_stars, True, {"desc": "Chroma post-filter complete."})
    stats = PostfilterStats(
        detected_stars=total_stars,
        applied_stars=applied,
        touched_fraction=float(np.mean(active)),
        elapsed_seconds=time.perf_counter() - t0,
    )
    return out, stats


# -----------------------------------------------------------------------------
# Tiled Inference Session
# -----------------------------------------------------------------------------


def axis_starts(limit: int, window: int, stride: int) -> List[int]:
    """Calculate tile start coordinates ensuring full coverage of the axis."""
    if limit <= window:
        return [0]
    starts = list(range(0, limit - window + 1, stride))
    if starts[-1] != limit - window:
        starts.append(limit - window)
    return starts


def load_nox_model(model_path: Path, device: torch.device) -> NoxColor:
    """Load NoxColor model weights from a PyTorch checkpoint."""
    if not model_path.is_file():
        raise FileNotFoundError(f"Nox checkpoint not found at: {model_path}")

    try:
        checkpoint = torch.load(model_path, map_location="cpu", weights_only=True)
    except Exception as error:
        raise ValueError(f"Invalid Nox checkpoint at {model_path}: {error}") from error
    if isinstance(checkpoint, dict):
        if "model_state" in checkpoint:
            state_dict = checkpoint["model_state"]
        elif "state_dict" in checkpoint:
            state_dict = checkpoint["state_dict"]
        else:
            state_dict = checkpoint
    else:
        state_dict = checkpoint

    model = NoxColor()
    try:
        model.load_state_dict(state_dict)
    except Exception as error:
        raise ValueError(f"Incompatible Nox checkpoint state dict at {model_path}: {error}") from error
    model = model.to(device)
    model.eval()
    return model


class NoxSession:
    """Manages an active NoxColor PyTorch model session and seamless tiled star removal."""

    def __init__(
        self,
        model_path: Optional[Path] = None,
        *,
        device: Union[str, torch.device] = "auto",
    ):
        self.model_path = (
            Path(model_path)
            if model_path is not None
            else (APPLICATION_DIR / "models" / NOX_MODEL_RELATIVE_PATH)
        )
        if not self.model_path.is_file():
            raise FileNotFoundError(f"Nox star removal model file not found: {self.model_path}")

        self.configured_device = resolve_nox_device(device)
        self.device = self.configured_device
        self.fallback_reason: Optional[str] = None
        self.model_identity = nox_model_identity()

        try:
            self.model = load_nox_model(self.model_path, self.device)
        except Exception as error:
            if not self._can_retry_on_cpu(error):
                raise
            self._activate_cpu_fallback(error)

    @property
    def execution_device(self) -> str:
        """Return the active torch device string used for execution (including CPU fallback)."""
        return str(self.device)

    def _can_retry_on_cpu(self, error: BaseException) -> bool:
        return self.device.type != "cpu" and is_cuda_allocation_failure(error)

    def _activate_cpu_fallback(self, error: BaseException) -> None:
        """Retry the whole image on CPU after a recognized GPU allocation failure."""
        failed_device = self.device
        cpu_device = torch.device("cpu")
        try:
            if hasattr(self, "model") and isinstance(self.model, nn.Module):
                self.model = self.model.to(cpu_device)
                self.model.eval()
            else:
                self.model = load_nox_model(self.model_path, cpu_device)
        except Exception as cpu_error:
            raise RuntimeError(
                f"Nox {failed_device} execution failed ({error}); CPU retry also failed: {cpu_error}"
            ) from cpu_error
        self.device = cpu_device
        self.fallback_reason = f"{failed_device} allocation failure: {error}; retried on cpu."

    def remove_stars(
        self,
        image: np.ndarray,
        *,
        stride: int,
        window_size: int = WINDOW_SIZE,
        batch_size: int = DEFAULT_BATCH_SIZE,
        progress_bar: Optional[Callable[[int, int, int, bool, Optional[dict]], None]] = None,
        should_interrupt: Optional[Callable[[], bool]] = None,
    ) -> np.ndarray:
        """Run tiled star removal on a float32 RGB image in [0.0, 1.0]."""
        validate_image_array(image)
        if window_size < MIN_SPATIAL_SIZE or window_size % SPATIAL_SIZE_MULTIPLE != 0:
            raise ValueError(
                f"window_size must be >= {MIN_SPATIAL_SIZE} and divisible by {SPATIAL_SIZE_MULTIPLE}, got {window_size}"
            )
        validate_separation_stride(stride, window_size=window_size)
        if batch_size <= 0:
            raise ValueError(f"batch_size must be positive, got {batch_size}")

        try:
            return self._remove_stars_with_active_device(
                image,
                stride=stride,
                window_size=window_size,
                batch_size=batch_size,
                progress_bar=progress_bar,
                should_interrupt=should_interrupt,
            )
        except Exception as error:
            if not self._can_retry_on_cpu(error):
                raise
            self._activate_cpu_fallback(error)
            return self._remove_stars_with_active_device(
                image,
                stride=stride,
                window_size=window_size,
                batch_size=batch_size,
                progress_bar=progress_bar,
                should_interrupt=should_interrupt,
            )

    @torch.inference_mode()
    def _remove_stars_with_active_device(
        self,
        img_float: np.ndarray,
        *,
        stride: int,
        window_size: int,
        batch_size: int,
        progress_bar: Optional[Callable[[int, int, int, bool, Optional[dict]], None]],
        should_interrupt: Optional[Callable[[], bool]],
    ) -> np.ndarray:
        if should_interrupt and should_interrupt():
            raise CancelledError("Nox star removal cancelled before starting.")

        h, w, _ = img_float.shape

        # Calculate padding to ensure borders are feathered smoothly and dimensions >= window_size
        pad_top = max((window_size - stride) // 2, max(0, (window_size - h) // 2 + 1))
        pad_bottom = pad_top
        if (h + pad_top + pad_bottom) < window_size:
            pad_bottom += window_size - (h + pad_top + pad_bottom)

        pad_left = max((window_size - stride) // 2, max(0, (window_size - w) // 2 + 1))
        pad_right = pad_left
        if (w + pad_left + pad_right) < window_size:
            pad_right += window_size - (w + pad_left + pad_right)

        pad_mode = "reflect" if (h > 1 and w > 1) else "edge"
        padded_np = np.pad(
            img_float,
            ((pad_top, pad_bottom), (pad_left, pad_right), (0, 0)),
            mode=pad_mode,
        )
        padded = torch.from_numpy(padded_np).permute(2, 0, 1).contiguous()  # (3, Hp, Wp)

        _, hp, wp = padded.shape
        ys = axis_starts(hp, window_size, stride)
        xs = axis_starts(wp, window_size, stride)
        tiles_coords = [(y, x) for y in ys for x in xs]
        total_tiles = len(tiles_coords)

        # Create 2D Hann blending weights
        w_1d = torch.hann_window(window_size, periodic=False, dtype=torch.float32)
        w_2d = torch.outer(w_1d, w_1d).clamp(min=HANN_MIN_WEIGHT)
        w_2d_dev = w_2d.to(self.device)

        out_accum = torch.zeros((3, hp, wp), dtype=torch.float32, device=self.device)
        w_accum = torch.zeros((hp, wp), dtype=torch.float32, device=self.device)
        padded_dev = padded.to(self.device)

        use_fp16_autocast = self.device.type == "cuda"
        completed_tiles = 0
        for i in range(0, total_tiles, batch_size):
            if should_interrupt and should_interrupt():
                raise CancelledError("Nox star removal cancelled during tile execution.")

            chunk = tiles_coords[i : i + batch_size]
            batch_t = torch.stack(
                [padded_dev[:, y : y + window_size, x : x + window_size] for y, x in chunk]
            )
            if use_fp16_autocast:
                with torch.amp.autocast("cuda", dtype=torch.float16):
                    pred = self.model(batch_t)
            else:
                pred = self.model(batch_t)
            pred = pred.float().clamp(0.0, 1.0)

            for k, (y, x) in enumerate(chunk):
                out_accum[:, y : y + window_size, x : x + window_size] += pred[k] * w_2d_dev
                w_accum[y : y + window_size, x : x + window_size] += w_2d_dev

            step_tiles = len(chunk)
            completed_tiles += step_tiles
            if progress_bar is not None:
                is_done = completed_tiles == total_tiles
                progress_bar(
                    total_tiles,
                    step_tiles,
                    completed_tiles,
                    is_done,
                    {"desc": f"Removing stars (tile {completed_tiles}/{total_tiles})..."},
                )

        if should_interrupt and should_interrupt():
            raise CancelledError("Nox star removal cancelled before normalizing output.")

        out_accum /= w_accum.clamp(min=WEIGHT_NORM_EPS).unsqueeze(0)
        starless_crop = out_accum[:, pad_top : pad_top + h, pad_left : pad_left + w].clamp(0.0, 1.0)
        starless_np = starless_crop.permute(1, 2, 0).cpu().numpy().astype(np.float32, copy=False)

        if self.device.type != "cpu":
            free_gpu_memory()

        return starless_np


__all__ = [
    "ARCHITECTURE",
    "CONV_STRIDE",
    "ChannelLayerNorm",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_STRIDE",
    "DecoderBlock",
    "EXPECTED_PARAM_COUNT",
    "EXPECTED_WEIGHT_TENSOR_COUNT",
    "EncoderBlock",
    "FILTERS",
    "HANN_MIN_WEIGHT",
    "IN_CHANNELS",
    "KERNEL_SIZE",
    "LAYER_NORM_EPS",
    "LEAKY_ALPHA",
    "MAX_STRIDE",
    "MIN_SPATIAL_SIZE",
    "MIN_STRIDE",
    "NOX_MODEL_FILENAME",
    "NOX_MODEL_RELATIVE_PATH",
    "NoxColor",
    "NoxSession",
    "OUT_CHANNELS",
    "PADDING",
    "PostfilterStats",
    "RadialChromaConfig",
    "SPATIAL_SIZE_MULTIPLE",
    "WEIGHT_NORM_EPS",
    "WINDOW_SIZE",
    "apply_radial_chroma_postfilter",
    "axis_starts",
    "decoder_channels",
    "detect_removed_star_centroids",
    "encoder_channels",
    "expected_state_dict_shapes",
    "load_nox_model",
    "nox_model_identity",
    "resolve_nox_device",
    "validate_separation_stride",
]
