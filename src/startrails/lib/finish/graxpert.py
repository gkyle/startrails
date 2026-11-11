"""GraXpert AI Denoise PyTorch model (CascadedGaze), checkpoint loader, and tile normalization."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from startrails.lib.finish.defaults import (
    GRAXPERT_MODEL_FILENAME,
    GRAXPERT_MODEL_RELATIVE_PATH,
)

CHANNELS = 3
WINDOW_SIZE = 256
DEFAULT_STRIDE = 128
DEFAULT_BATCH_SIZE = 4
MODEL_SCALE_FACTOR = 0.04
MODEL_THRESHOLD = 10.0
MIN_MAD_EPSILON = 1e-6
STATS_SAMPLE_STRIDE = 4

LAYER_NORM_EPS = 1e-6
EXPECTED_PARAM_COUNT = 119_223_063
EXPECTED_WEIGHT_TENSOR_COUNT = 656
CHECKPOINT_FORMAT_FP16 = "graxpert_pytorch_fp16"
CHECKPOINT_FORMAT_MIXED_INT4_INT8 = "graxpert_pytorch_mixed_int4_int8"


def graxpert_model_identity() -> str:
    """Return the identity of the bundled GraXpert weights used in cache keys.

    Device selection is deliberately excluded: CPU and GPU lanes run the same
    numerical pipeline, so switching an accelerator does not invalidate endpoints.
    """
    return f"graxpert:{GRAXPERT_MODEL_RELATIVE_PATH}"


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
    """Standardize a (256, 256, 3) image tile for GraXpert model input.

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


class SimpleGate(nn.Module):
    """Elementwise multiplication of split feature channels."""

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x1, x2 = x.chunk(2, dim=1)
        return x1 * x2


class DepthwiseSeparableConv(nn.Module):
    """Depthwise separable convolution."""

    def __init__(
        self,
        nin: int,
        nout: int,
        kernel_size: int = 3,
        padding: int = 0,
        stride: int = 1,
        bias: bool = False,
    ) -> None:
        super().__init__()
        self.pointwise = nn.Conv2d(nin, nout, kernel_size=1, bias=bias)
        self.depthwise = nn.Conv2d(
            nin,
            nin,
            kernel_size=kernel_size,
            stride=stride,
            padding=padding,
            groups=nin,
            bias=bias,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.depthwise(x)
        x = self.pointwise(x)
        return x


class LayerNorm2d(nn.Module):
    """2D Layer Normalization operating across the channel dimension."""

    def __init__(self, channels: int, eps: float = LAYER_NORM_EPS) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.ones(channels))
        self.bias = nn.Parameter(torch.zeros(channels))
        self.eps = eps

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        mu = x.mean(1, keepdim=True)
        var = (x - mu).pow(2).mean(1, keepdim=True)
        y = (x - mu) / (var + self.eps).sqrt()
        return self.weight.view(1, -1, 1, 1) * y + self.bias.view(1, -1, 1, 1)


class GlobalContextExtractor(nn.Module):
    """Cascaded Global Context Extractor using multiscale depthwise separable convolutions."""

    def __init__(
        self,
        c: int,
        kernel_sizes: Sequence[int] = (3, 3, 5),
        strides: Sequence[int] = (2, 3, 4),
        padding: int = 0,
        bias: bool = False,
    ) -> None:
        super().__init__()
        self.depthwise_separable_convs = nn.ModuleList(
            [
                DepthwiseSeparableConv(c, c, kernel_size, padding, stride, bias)
                for kernel_size, stride in zip(kernel_sizes, strides)
            ]
        )

    def forward(self, x: torch.Tensor) -> List[torch.Tensor]:
        outputs: List[torch.Tensor] = []
        for conv in self.depthwise_separable_convs:
            x = F.gelu(conv(x))
            outputs.append(x)
        return outputs


class CascadedGazeBlock(nn.Module):
    """CascadedGaze encoder block with Global Context Extractor and Simplified Channel Attention."""

    def __init__(
        self,
        c: int,
        gce_conv: int = 2,
        dw_expand: int = 2,
        ffn_expand: int = 2,
    ) -> None:
        super().__init__()
        self.dw_channel = c * dw_expand
        self.GCE_Conv = gce_conv

        self.conv1 = nn.Conv2d(
            in_channels=c,
            out_channels=self.dw_channel,
            kernel_size=1,
            padding=0,
            stride=1,
            groups=1,
            bias=True,
        )
        self.conv2 = nn.Conv2d(
            in_channels=self.dw_channel,
            out_channels=self.dw_channel,
            kernel_size=3,
            padding=1,
            stride=1,
            groups=self.dw_channel,
            bias=True,
        )

        if self.GCE_Conv == 3:
            self.GCE = GlobalContextExtractor(c=c, kernel_sizes=(3, 3, 5), strides=(2, 3, 4))
            self.project_out = nn.Conv2d(int(self.dw_channel * 2.5), c, kernel_size=1)
            self.sca = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Conv2d(
                    in_channels=int(self.dw_channel * 2.5),
                    out_channels=int(self.dw_channel * 2.5),
                    kernel_size=1,
                    padding=0,
                    stride=1,
                    groups=1,
                    bias=True,
                ),
            )
        else:
            self.GCE = GlobalContextExtractor(c=c, kernel_sizes=(3, 3), strides=(2, 3))
            self.project_out = nn.Conv2d(self.dw_channel * 2, c, kernel_size=1)
            self.sca = nn.Sequential(
                nn.AdaptiveAvgPool2d(1),
                nn.Conv2d(
                    in_channels=self.dw_channel * 2,
                    out_channels=self.dw_channel * 2,
                    kernel_size=1,
                    padding=0,
                    stride=1,
                    groups=1,
                    bias=True,
                ),
            )

        self.sg = SimpleGate()
        ffn_channel = ffn_expand * c
        self.conv4 = nn.Conv2d(
            in_channels=c,
            out_channels=ffn_channel,
            kernel_size=1,
            padding=0,
            stride=1,
            groups=1,
            bias=True,
        )
        self.conv5 = nn.Conv2d(
            in_channels=ffn_channel // 2,
            out_channels=c,
            kernel_size=1,
            padding=0,
            stride=1,
            groups=1,
            bias=True,
        )

        self.norm1 = LayerNorm2d(c)
        self.norm2 = LayerNorm2d(c)

        self.beta = nn.Parameter(torch.zeros((1, c, 1, 1)))
        self.gamma = nn.Parameter(torch.zeros((1, c, 1, 1)))

    def forward(self, inp: torch.Tensor) -> torch.Tensor:
        _, _, h, w = inp.shape

        x = self.norm1(inp)
        x = self.conv1(x)
        x = self.conv2(x)
        x = F.gelu(x)

        x_1, x_2 = x.chunk(2, dim=1)
        gce_outs = self.GCE(x_1 + x_2)
        up_outs = [F.interpolate(g, size=(h, w), mode="nearest") for g in gce_outs]
        fused = torch.cat([x] + up_outs, dim=1)
        fused = self.sca(fused) * fused
        x = self.project_out(fused)

        y = inp + x * self.beta

        x = self.conv4(self.norm2(y))
        x = self.sg(x)
        x = self.conv5(x)

        return y + x * self.gamma


class NAFBlock0(nn.Module):
    """NAFNet block used in middle bottleneck and decoders."""

    def __init__(
        self,
        c: int,
        dw_expand: int = 2,
        ffn_expand: int = 2,
    ) -> None:
        super().__init__()
        dw_channel = c * dw_expand
        self.conv1 = nn.Conv2d(
            in_channels=c,
            out_channels=dw_channel,
            kernel_size=1,
            padding=0,
            stride=1,
            groups=1,
            bias=True,
        )
        self.conv2 = nn.Conv2d(
            in_channels=dw_channel,
            out_channels=dw_channel,
            kernel_size=3,
            padding=1,
            stride=1,
            groups=dw_channel,
            bias=True,
        )
        self.conv3 = nn.Conv2d(
            in_channels=dw_channel // 2,
            out_channels=c,
            kernel_size=1,
            padding=0,
            stride=1,
            groups=1,
            bias=True,
        )

        self.sca = nn.Sequential(
            nn.AdaptiveAvgPool2d(1),
            nn.Conv2d(
                in_channels=dw_channel // 2,
                out_channels=dw_channel // 2,
                kernel_size=1,
                padding=0,
                stride=1,
                groups=1,
                bias=True,
            ),
        )

        self.sg = SimpleGate()

        ffn_channel = ffn_expand * c
        self.conv4 = nn.Conv2d(
            in_channels=c,
            out_channels=ffn_channel,
            kernel_size=1,
            padding=0,
            stride=1,
            groups=1,
            bias=True,
        )
        self.conv5 = nn.Conv2d(
            in_channels=ffn_channel // 2,
            out_channels=c,
            kernel_size=1,
            padding=0,
            stride=1,
            groups=1,
            bias=True,
        )

        self.norm1 = LayerNorm2d(c)
        self.norm2 = LayerNorm2d(c)

        self.beta = nn.Parameter(torch.zeros((1, c, 1, 1)))
        self.gamma = nn.Parameter(torch.zeros((1, c, 1, 1)))

    def forward(self, inp: torch.Tensor) -> torch.Tensor:
        x = self.norm1(inp)
        x = self.conv1(x)
        x = self.conv2(x)
        x = self.sg(x)
        x = x * self.sca(x)
        x = self.conv3(x)

        y = inp + x * self.beta

        x = self.conv4(self.norm2(y))
        x = self.sg(x)
        x = self.conv5(x)

        return y + x * self.gamma


class CascadedGaze(nn.Module):
    """Full CascadedGaze Network (CGNet) matching GraXpert 3.0.2."""

    def __init__(
        self,
        img_channel: int = CHANNELS,
        width: int = 60,
        middle_blk_num: int = 10,
        enc_blk_nums: Sequence[int] = (2, 2, 4, 6),
        dec_blk_nums: Sequence[int] = (2, 2, 2, 2),
        gce_convs_nums: Sequence[int] = (3, 3, 2, 2),
    ) -> None:
        super().__init__()
        self.intro = nn.Conv2d(
            in_channels=img_channel,
            out_channels=width,
            kernel_size=3,
            padding=1,
            stride=1,
            groups=1,
            bias=True,
        )
        self.ending = nn.Conv2d(
            in_channels=width,
            out_channels=img_channel,
            kernel_size=3,
            padding=1,
            stride=1,
            groups=1,
            bias=True,
        )

        self.encoders = nn.ModuleList()
        self.decoders = nn.ModuleList()
        self.middle_blks = nn.ModuleList()
        self.ups = nn.ModuleList()
        self.downs = nn.ModuleList()

        chan = width
        for i in range(len(enc_blk_nums)):
            num = enc_blk_nums[i]
            gce_convs = gce_convs_nums[i]
            self.encoders.append(
                nn.Sequential(*[CascadedGazeBlock(chan, gce_conv=gce_convs) for _ in range(num)])
            )
            self.downs.append(nn.Conv2d(chan, 2 * chan, 2, 2))
            chan = chan * 2

        self.middle_blks = nn.Sequential(*[NAFBlock0(chan) for _ in range(middle_blk_num)])

        for i in range(len(dec_blk_nums)):
            num = dec_blk_nums[i]
            self.ups.append(
                nn.Sequential(
                    nn.Conv2d(chan, chan * 2, 1, bias=False),
                    nn.PixelShuffle(2),
                )
            )
            chan = chan // 2
            self.decoders.append(nn.Sequential(*[NAFBlock0(chan) for _ in range(num)]))

        self.padder_size = 2 ** len(self.encoders)

    def forward(self, inp: torch.Tensor) -> torch.Tensor:
        """Run CascadedGaze inference on an NHWC [B, H, W, 3] or NCHW [B, 3, H, W] tensor."""
        is_nhwc = inp.ndim == 4 and inp.shape[-1] == CHANNELS
        if is_nhwc:
            inp = inp.permute(0, 3, 1, 2)

        _, _, h, w = inp.shape
        mod_pad_h = (self.padder_size - h % self.padder_size) % self.padder_size
        mod_pad_w = (self.padder_size - w % self.padder_size) % self.padder_size
        padded_inp = F.pad(inp, (0, mod_pad_w, 0, mod_pad_h))
        x = padded_inp

        x = self.intro(x)
        encs: List[torch.Tensor] = []
        for encoder, down in zip(self.encoders, self.downs):
            x = encoder(x)
            encs.append(x)
            x = down(x)

        x = self.middle_blks(x)

        for decoder, up, enc_skip in zip(self.decoders, self.ups, reversed(encs)):
            x = up(x)
            x = x + enc_skip
            x = decoder(x)

        x = self.ending(x)
        x = x + padded_inp
        out = x[:, :, :h, :w]

        if is_nhwc:
            out = out.permute(0, 2, 3, 1)
        return out


def build_graxpert_model() -> CascadedGaze:
    """Build a CascadedGaze model matching GraXpert 3.0.2 topology."""
    return CascadedGaze(
        img_channel=CHANNELS,
        width=60,
        middle_blk_num=10,
        enc_blk_nums=(2, 2, 4, 6),
        dec_blk_nums=(2, 2, 2, 2),
        gce_convs_nums=(3, 3, 2, 2),
    )


def unpack_int4_tensor(packed: torch.Tensor, original_shape: torch.Size) -> torch.Tensor:
    """Unpack uint8 bytes back into signed int8 [-7, 7] tensor."""
    low = (packed & 0x0F).to(torch.int8) - 7
    high = ((packed >> 4) & 0x0F).to(torch.int8) - 7
    interleaved = torch.empty(packed.numel() * 2, dtype=torch.int8)
    interleaved[0::2] = low
    interleaved[1::2] = high
    numel = original_shape.numel()
    return interleaved[:numel].view(original_shape)


def load_graxpert_model(
    model_path: Union[str, Path],
    device: Union[str, torch.device] = "cpu",
    dtype: Optional[torch.dtype] = None,
) -> CascadedGaze:
    """Load a CascadedGaze model from a PyTorch mixed INT4/INT8 or FP16 checkpoint."""
    checkpoint_path = Path(model_path)
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"GraXpert checkpoint not found at: {checkpoint_path}")

    target_device = torch.device(device)
    target_dtype = dtype if dtype is not None else (torch.float16 if target_device.type == "cuda" else torch.float32)

    try:
        ckpt = torch.load(checkpoint_path, map_location="cpu", weights_only=True)
    except Exception as error:
        raise ValueError(f"Invalid GraXpert checkpoint at {checkpoint_path}: {error}") from error

    if not isinstance(ckpt, dict):
        raise ValueError(f"Invalid GraXpert checkpoint structure at {checkpoint_path}: expected dict")

    model = build_graxpert_model()
    fmt = ckpt.get("format", "")

    try:
        if fmt == CHECKPOINT_FORMAT_FP16:
            state_dict = {k: v.to(target_dtype) for k, v in ckpt["state_dict"].items()}
            model.load_state_dict(state_dict)
        elif fmt == CHECKPOINT_FORMAT_MIXED_INT4_INT8:
            packed = ckpt["packed_dict"]
            state_dict: Dict[str, torch.Tensor] = {}
            for k in list(model.state_dict().keys()):
                if f"{k}.packed" in packed:
                    p_data = packed[f"{k}.packed"]
                    shape = torch.Size(packed[f"{k}.shape"])
                    scale = packed[f"{k}.scale"]
                    q = unpack_int4_tensor(p_data, shape)
                    scale_exp = scale.view(-1, *([1] * (q.ndim - 1)))
                    state_dict[k] = (q.float() * scale_exp.float()).to(target_dtype)
                elif f"{k}.q" in packed:
                    q = packed[f"{k}.q"]
                    scale = packed[f"{k}.scale"]
                    scale_exp = scale.view(-1, *([1] * (q.ndim - 1)))
                    state_dict[k] = (q.float() * scale_exp.float()).to(target_dtype)
                elif k in packed:
                    state_dict[k] = packed[k].to(target_dtype)
                else:
                    raise KeyError(f"Missing key in packed checkpoint: {k}")
            model.load_state_dict(state_dict)
        else:
            raw_state = ckpt.get("state_dict", ckpt)
            state_dict = {k: v.to(target_dtype) for k, v in raw_state.items()}
            model.load_state_dict(state_dict)
    except Exception as error:
        raise ValueError(f"Incompatible GraXpert checkpoint state dict at {checkpoint_path}: {error}") from error

    model = model.to(device=target_device, dtype=target_dtype)
    model.eval()
    return model


__all__ = [
    "CHANNELS",
    "CHECKPOINT_FORMAT_FP16",
    "CHECKPOINT_FORMAT_MIXED_INT4_INT8",
    "CascadedGaze",
    "CascadedGazeBlock",
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_STRIDE",
    "DepthwiseSeparableConv",
    "EXPECTED_PARAM_COUNT",
    "EXPECTED_WEIGHT_TENSOR_COUNT",
    "GRAXPERT_MODEL_FILENAME",
    "GRAXPERT_MODEL_RELATIVE_PATH",
    "GlobalContextExtractor",
    "LAYER_NORM_EPS",
    "LayerNorm2d",
    "MIN_MAD_EPSILON",
    "MODEL_SCALE_FACTOR",
    "MODEL_THRESHOLD",
    "NAFBlock0",
    "STATS_SAMPLE_STRIDE",
    "SimpleGate",
    "WINDOW_SIZE",
    "build_graxpert_model",
    "compute_graxpert_stats",
    "graxpert_model_identity",
    "graxpert_tile_postprocess",
    "graxpert_tile_preprocess",
    "load_graxpert_model",
    "unpack_int4_tensor",
]
