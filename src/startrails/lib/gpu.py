from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import psutil
import pynvml
import torch

logger = logging.getLogger(__name__)

# Lazy global detection for CuPy
_CUPY_AVAILABLE: Optional[bool] = None
_CUPY_MODULE: Any = None
_GPU_MEMORY_TARGET_FRACTION = 0.35
_GPU_CHUNK_ROW_MIN = 128
_GPU_CHUNK_ROW_MAX = 512
_DEFAULT_CPU_CHUNK_ROWS = 256
_BYTES_PER_GIB = 1024**3

# GPU allocation failures are the only recognized recoverable execution errors.
# Recovery is an explained CPU retry of the whole image.
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


def resolve_torch_device(
    device: Union[str, torch.device] = "auto",
    *,
    use_gpu: bool = True,
) -> torch.device:
    """Resolve compute device string or torch.device to a concrete torch.device."""
    if not use_gpu:
        return torch.device("cpu")
    if isinstance(device, torch.device):
        device = str(device)
    choice = device.strip().lower()
    if choice == "auto":
        if torch.cuda.is_available():
            return torch.device("cuda")
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")
    if choice in ("gpu", "cuda"):
        if not torch.cuda.is_available():
            raise RuntimeError("CUDA device requested but torch.cuda.is_available() is False.")
        return torch.device("cuda")
    if choice.startswith("cuda:") or choice.startswith("gpu:"):
        idx = choice.split(":")[-1]
        return torch.device(f"cuda:{idx}")
    if choice == "mps":
        if not (hasattr(torch.backends, "mps") and torch.backends.mps.is_available()):
            raise RuntimeError("MPS device requested but torch.backends.mps.is_available() is False.")
        return torch.device("mps")
    if choice == "cpu":
        return torch.device("cpu")
    raise ValueError(f"Unknown device specification: {device}")


def is_cupy_available() -> bool:
    """Check if CuPy is installed and a functional CUDA device is available."""
    global _CUPY_AVAILABLE, _CUPY_MODULE
    if _CUPY_AVAILABLE is not None:
        return _CUPY_AVAILABLE

    try:
        import cupy as cp

        if cp.cuda.is_available():
            _ = cp.zeros((1,), dtype=cp.float32)
            _CUPY_AVAILABLE = True
            _CUPY_MODULE = cp
            logger.debug("CuPy CUDA acceleration is available.")
            return True
    except Exception as e:
        logger.debug(f"CuPy unavailable or failed to initialize CUDA: {e}")

    _CUPY_AVAILABLE = False
    _CUPY_MODULE = None
    return False


def get_array_module(use_gpu: bool = True) -> Tuple[Any, bool]:
    """Return array module (cupy or numpy) and a boolean indicating whether GPU is active."""
    if use_gpu and is_cupy_available():
        global _CUPY_MODULE
        return _CUPY_MODULE, True
    return np, False


def free_gpu_memory() -> None:
    """Release unused memory blocks back to the GPU allocator."""
    if _CUPY_AVAILABLE and _CUPY_MODULE is not None:
        try:
            _CUPY_MODULE.get_default_memory_pool().free_all_blocks()
            _CUPY_MODULE.get_default_pinned_memory_pool().free_all_blocks()
        except Exception:
            pass
    try:
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def to_gb(bytes_val: float | int) -> float:
    """Convert bytes to gigabytes."""
    return bytes_val / _BYTES_PER_GIB


# Backwards compatibility alias for module-level function
toGB = to_gb


class GPUInfo:
    """Hardware detector and telemetry provider for GPU resources."""

    def __init__(self):
        try:
            self.cudaAvailable = torch.cuda.is_available()
        except Exception:
            self.cudaAvailable = False

        try:
            self.mpsAvailable = torch.backends.mps.is_available()
        except Exception:
            self.mpsAvailable = False

        try:
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count > 0:
                self.useNVML = True
                self.nvmlHandle = pynvml.nvmlDeviceGetHandleByIndex(0)
            else:
                self.useNVML = False
                self.nvmlHandle = None
        except Exception:
            self.useNVML = False
            self.nvmlHandle = None

    def get_gpu_names(self) -> List[List[str]]:
        try:
            if self.mpsAvailable:
                return [["mps", "Apple Silicon GPU (MPS)"]]
            if self.cudaAvailable:
                return [
                    [f"cuda:{i}", torch.cuda.get_device_name(i)]
                    for i in range(torch.cuda.device_count())
                ]
            if is_cupy_available():
                import cupy as cp

                device = cp.cuda.Device()
                props = cp.cuda.runtime.getDeviceProperties(device.id)
                name = props["name"].decode("utf-8", errors="ignore")
                return [[f"cuda:{device.id}", name]]
        except Exception:
            pass
        return []

    def get_gpu_present(self) -> bool:
        return self.cudaAvailable or self.mpsAvailable or is_cupy_available()

    def get_gpu_memory_bytes(self) -> Optional[Tuple[int, int]]:
        """Return (total_bytes, free_bytes) from PyTorch, MPS, or CuPy."""
        try:
            if self.cudaAvailable:
                free_bytes, total_bytes = torch.cuda.mem_get_info()
                return int(total_bytes), int(free_bytes)
            if self.mpsAvailable:
                vm = psutil.virtual_memory()
                return int(vm.total), int(vm.available)
        except Exception:
            pass

        if is_cupy_available():
            try:
                import cupy as cp

                device = cp.cuda.Device()
                free_bytes, total_bytes = device.mem_info
                return int(total_bytes), int(free_bytes)
            except Exception:
                pass
        return None

    def get_gpu_memory(self) -> Optional[Tuple[float, float]]:  # Return (total GB, available GB)
        mem = self.get_gpu_memory_bytes()
        if mem:
            total_bytes, free_bytes = mem
            return float(to_gb(total_bytes)), float(to_gb(free_bytes))
        return None

    def get_gpu_memory_total(self) -> Optional[float]:
        mem = self.get_gpu_memory_bytes()
        if mem:
            return float(to_gb(mem[0]))
        return None

    def get_gpu_memory_available(self) -> Optional[float]:
        mem = self.get_gpu_memory_bytes()
        if mem:
            return float(to_gb(mem[1]))
        return None

    def get_gpu_utilization(self) -> Optional[float]:
        try:
            if self.mpsAvailable:
                return None
            if self.cudaAvailable and self.nvmlHandle:
                gpu_utilization = pynvml.nvmlDeviceGetUtilizationRates(self.nvmlHandle).gpu / 100.0
                return gpu_utilization
        except Exception:
            pass
        return None

    def get_info(self) -> Optional[Dict[str, Any]]:
        """Return standardized device metadata and memory statistics dict."""
        mem = self.get_gpu_memory_bytes()
        if not mem:
            return None
        total_bytes, free_bytes = mem

        names = self.get_gpu_names()
        device_name = names[0][1] if names else "GPU"

        dev_id = 0
        try:
            if self.cudaAvailable:
                dev_id = torch.cuda.current_device()
            elif is_cupy_available():
                import cupy as cp

                dev_id = cp.cuda.Device().id
        except Exception:
            pass

        return {
            "id": dev_id,
            "name": device_name,
            "total_bytes": total_bytes,
            "free_bytes": free_bytes,
            "total_gb": total_bytes / _BYTES_PER_GIB,
            "free_gb": free_bytes / _BYTES_PER_GIB,
        }

    @staticmethod
    def free_memory() -> None:
        """Release unused memory blocks back to the GPU allocator."""
        free_gpu_memory()


_DEFAULT_GPU_INFO: Optional[GPUInfo] = None


def get_gpu_info() -> Optional[Dict[str, Any]]:
    """Return GPU device name and memory statistics dict if available."""
    global _DEFAULT_GPU_INFO
    if _DEFAULT_GPU_INFO is None:
        _DEFAULT_GPU_INFO = GPUInfo()
    return _DEFAULT_GPU_INFO.get_info()


def get_optimal_chunk_rows(
    height: int,
    width: int,
    num_frames: int,
    channels: int = 3,
    use_gpu: bool = True,
    default_cpu_rows: int = _DEFAULT_CPU_CHUNK_ROWS,
) -> int:
    """Calculate the optimal vertical chunk slice size based on available VRAM or RAM."""
    if not use_gpu or not is_cupy_available():
        return min(height, default_cpu_rows)

    info = get_gpu_info()
    if info is None:
        return min(height, default_cpu_rows)

    bytes_per_row = num_frames * width * channels * 4 * 6
    if bytes_per_row <= 0:
        return min(height, default_cpu_rows)

    target_vram = info["free_bytes"] * _GPU_MEMORY_TARGET_FRACTION
    chunk_rows = int(target_vram // bytes_per_row)
    chunk_rows = max(_GPU_CHUNK_ROW_MIN, min(height, _GPU_CHUNK_ROW_MAX, chunk_rows))
    return chunk_rows
