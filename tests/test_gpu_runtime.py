"""Runtime device selection stays independent of vendor-specific APIs."""

from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from src.setup.check_runtime import variant_family
from startrails.lib.gpu import GPUInfo, resolve_torch_device, torch_accelerator_kind


ROOT = Path(__file__).resolve().parents[1]
CHECK_RUNTIME = ROOT / "src/setup/check_runtime.py"


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


class CheckRuntimeTests(unittest.TestCase):
    def test_variant_families_dispatch_by_declared_extra(self):
        supported = {"cpu", "mps", "xpu", "cu12", "rocm7", "rocm9"}
        cases = {
            "cpu": "cpu",
            "mps": "mps",
            "xpu": "xpu",
            "cu12": "cuda",
            "rocm7": "rocm",
            "rocm9": "rocm",
        }
        for variant, family in cases.items():
            with self.subTest(variant=variant):
                self.assertEqual(variant_family(variant, supported), family)
        with self.assertRaisesRegex(ValueError, "Unknown accelerator variant"):
            variant_family("typo", supported)
        with self.assertRaisesRegex(ValueError, "Unsupported accelerator variant"):
            variant_family("vulkan", supported | {"vulkan"})

    def test_unknown_variant_exits_before_native_imports(self):
        for variant in ("typo", "rocm8"):
            with self.subTest(variant=variant):
                result = subprocess.run(
                    [sys.executable, "-S", str(CHECK_RUNTIME), "--variant", variant],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("Traceback", result.stderr)
