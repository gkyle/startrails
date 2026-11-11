"""Contracts for translating uv's installation report into locked extras."""

import json
import io
from contextlib import redirect_stderr
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
import unittest

from src.setup.probeGPU import run_uv, select_extra, supported_backends, torch_version_from_report


ROOT = Path(__file__).resolve().parents[1]


class GpuProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with (ROOT / "pyproject.toml").open("rb") as stream:
            cls.supported = supported_backends(tomllib.load(stream))

    def test_selects_highest_compatible_locked_backend(self):
        cases = {
            "2.15.0+cpu": "cpu",
            "2.15.0+cu118": "cu11",
            "2.15.0+cu128": "cu12",
            "2.15.0+cu132": "cu13",
            "2.15.0+rocm7.2": "rocm7",
            "2.15.0+xpu": "xpu",
        }
        for version, extra in cases.items():
            with self.subTest(version=version):
                self.assertEqual(select_extra(version, self.supported), extra)

    def test_higher_cuda_major_falls_back_to_highest_configured_cuda_extra(self):
        with redirect_stderr(io.StringIO()):
            self.assertEqual(select_extra("2.15.0+cu140", self.supported), "cu13")

    def test_unsupported_backend_uses_cpu_without_crossing_families(self):
        for version in ("2.15.0+cu121", "2.15.0+rocm6.4", "2.15.0+rocm8.0"):
            with self.subTest(version=version), redirect_stderr(io.StringIO()):
                self.assertEqual(select_extra(version, self.supported), "cpu")
        with self.assertRaisesRegex(ValueError, "unrecognized PyTorch version"):
            select_extra("2.15.0+unexpected", self.supported)

    def test_requires_one_torch_install_in_preview_dry_run(self):
        report = {
            "schema": {"version": "preview"},
            "changes": [{"name": "torch", "version": "2.15.0+cu132", "action": "installed"}],
            "dry_run": True,
        }
        self.assertEqual(torch_version_from_report(json.dumps(report)), "2.15.0+cu132")
        for change in ([], [{"name": "torch", "version": "2.15.0+cu132", "action": "reinstalled"}]):
            with self.subTest(changes=change), self.assertRaisesRegex(ValueError, "one planned Torch"):
                torch_version_from_report(json.dumps({**report, "changes": change}))
        with self.assertRaisesRegex(ValueError, "Unexpected uv JSON schema"):
            torch_version_from_report(json.dumps({**report, "schema": {"version": "future"}}))


class GpuProbeProcessTests(unittest.TestCase):
    def test_run_uv_reports_launch_failure_with_command(self):
        with TemporaryDirectory() as directory:
            executable = Path(directory) / "missing-uv"
            with self.assertRaises(RuntimeError) as context:
                run_uv([str(executable), "venv"])
        self.assertIn("Could not run", str(context.exception))
        self.assertIn(str(executable), str(context.exception))

    def test_run_uv_replaces_undecodable_diagnostics(self):
        with self.assertRaises(RuntimeError) as context:
            run_uv([
                sys.executable,
                "-c",
                "import sys; sys.stderr.buffer.write(b'\\x81'); sys.exit(1)",
            ])
        self.assertIn("uv GPU probe failed", str(context.exception))
        self.assertIn(sys.executable, str(context.exception))

    def test_cli_reports_invalid_project_config_as_usage_error(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            script = root / "src/setup/probeGPU.py"
            script.parent.mkdir(parents=True)
            shutil.copyfile(ROOT / "src/setup/probeGPU.py", script)
            (root / "pyproject.toml").write_text("not = [valid", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(script), "--uv", sys.executable],
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
