"""Runtime device selection stays independent of vendor-specific APIs."""

import unittest
from unittest.mock import patch

from startrails.lib.gpu import GPUInfo, resolve_torch_device, torch_accelerator_kind


class GpuRuntimeTests(unittest.TestCase):
    def test_xpu_is_selected_and_reported_when_other_accelerators_are_absent(self):
        with (
            patch("startrails.lib.gpu.torch.cuda.is_available", return_value=False),
            patch("startrails.lib.gpu.torch.backends.mps.is_available", return_value=False),
            patch("startrails.lib.gpu.torch.xpu.is_available", return_value=True),
            patch("startrails.lib.gpu.torch.xpu.device_count", return_value=1),
            patch("startrails.lib.gpu.torch.xpu.get_device_name", return_value="Intel GPU"),
            patch("startrails.lib.gpu.torch.xpu.mem_get_info", return_value=(3, 8)),
        ):
            self.assertEqual(str(resolve_torch_device()), "xpu")
            self.assertEqual(str(resolve_torch_device(use_gpu=False)), "cpu")
            self.assertEqual(torch_accelerator_kind(), "xpu")
            info = GPUInfo()
            self.assertEqual(info.get_gpu_names(), [["xpu:0", "Intel GPU"]])
            self.assertEqual(info.get_gpu_memory_bytes(), (8, 3))

    def test_rocm_uses_torch_cuda_without_nvidia_telemetry(self):
        with (
            patch("startrails.lib.gpu.torch.cuda.is_available", return_value=True),
            patch("startrails.lib.gpu.torch.version.hip", "7.2"),
            patch("startrails.lib.gpu.pynvml.nvmlInit") as nvml_init,
        ):
            self.assertEqual(str(resolve_torch_device()), "cuda")
            self.assertEqual(torch_accelerator_kind(), "rocm")
            self.assertEqual(GPUInfo().kind, "rocm")
            nvml_init.assert_not_called()
