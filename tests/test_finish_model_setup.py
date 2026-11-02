"""Tests for Finish mode model setup, manifests, CLI contracts, and process boundaries."""

from concurrent.futures import CancelledError
import json
import os
from pathlib import Path
import tempfile
import subprocess
import sys
from threading import Event, Timer
import unittest
from unittest.mock import patch
import numpy as np

from startrails.lib.finish.graxpert import (
    compute_graxpert_stats,
    graxpert_model_identity,
    graxpert_tile_postprocess,
    graxpert_tile_preprocess,
    MIN_MAD_EPSILON,
)
from startrails.lib.model_manifest import GRAXPERT_MANIFEST, PlatformNotSupportedError, get_starnet_package_for_platform
from startrails.lib.signatures import verify_file_integrity
from startrails.lib.starnet_setup import (
    detect_platform_target,
    validate_starnet_installation,
    probe_starnet_installation,
    StarNetSetupError,
)
from startrails.lib.finish.starnet import (
    build_starnet_cli_args,
    parse_starnet_machine_info,
    parse_starnet_progress_line,
    run_starnet_process,
    StarNetError,
)


class TestFinishModelSetup(unittest.TestCase):
    def test_detect_platform_target(self):
        self.assertEqual(detect_platform_target("Linux", "x86_64"), "linux-x64")
        self.assertEqual(detect_platform_target("Darwin", "arm64"), "macos-arm64")
        self.assertEqual(detect_platform_target("Windows", "AMD64"), "windows-x64")

        with self.assertRaises(PlatformNotSupportedError):
            detect_platform_target("Darwin", "x86_64")

        with self.assertRaises(PlatformNotSupportedError):
            detect_platform_target("Linux", "armv7l")

        with self.assertRaises(PlatformNotSupportedError):
            detect_platform_target("FreeBSD", "x86_64")

    def test_starnet_packages_manifest(self):
        for pid in ("linux-x64", "macos-arm64", "windows-x64"):
            pkg = get_starnet_package_for_platform(pid)
            self.assertEqual(pkg.platform_id, pid)
            self.assertEqual(pkg.version, "2.6.2")
            self.assertEqual(pkg.build, "0242")
            self.assertTrue(pkg.archive_url.startswith("https://"))
            self.assertEqual(len(pkg.archive_sha256), 64)
            self.assertGreater(pkg.archive_size_bytes, 100_000_000)

        self.assertEqual(GRAXPERT_MANIFEST.version, "3.0.2")
        self.assertEqual(len(GRAXPERT_MANIFEST.sha256), 64)
        self.assertGreater(GRAXPERT_MANIFEST.size_bytes, 400_000_000)

    def make_installation(self, root, platform_id, native):
        package = get_starnet_package_for_platform(platform_id)
        directory = root / "bin" if native else root
        directory.mkdir(parents=True)
        executable = directory / package.executable_relative_path
        executable.write_text("placeholder executable")
        executable.chmod(0o755)
        weights = (root / "lib" / "starnet2" if native else root) / package.weights_relative_path
        if weights.suffix == ".mlpackage":
            weights.mkdir(parents=True)
        else:
            weights.parent.mkdir(parents=True, exist_ok=True)
            weights.write_bytes(b"model")
        return executable, weights

    def test_discovers_portable_and_native_installations_for_each_platform(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for platform_id in ("linux-x64", "windows-x64", "macos-arm64"):
                for native in (False, True):
                    with self.subTest(platform=platform_id, native=native):
                        root = Path(tmpdir) / platform_id / str(native)
                        executable, weights = self.make_installation(root, platform_id, native)
                        for location in (root, executable.parent, executable):
                            found = validate_starnet_installation(location, platform_id)
                            self.assertEqual(found.executable, executable.resolve())
                            self.assertEqual(found.weights, weights.resolve())

    def test_missing_components_and_ambiguous_installations_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            with self.assertRaisesRegex(StarNetSetupError, "Missing StarNet executable"):
                validate_starnet_installation(root, "linux-x64")
            executable, weights = self.make_installation(root / "first", "macos-arm64", False)
            self.assertEqual(validate_starnet_installation(root, "macos-arm64").executable, executable)
            weights.rmdir()
            with self.assertRaisesRegex(StarNetSetupError, "Missing model weights"):
                validate_starnet_installation(root, "macos-arm64")
            weights.mkdir()
            self.make_installation(root / "second", "macos-arm64", False)
            with self.assertRaisesRegex(StarNetSetupError, "Multiple StarNet installations"):
                validate_starnet_installation(root, "macos-arm64")

    def test_setup_probe_requires_pinned_identity_and_cli_contract(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir) / "installation"
            self.make_installation(root, "linux-x64", False)
            installation = validate_starnet_installation(root, "linux-x64")
            info = {
                "product": "starnet2",
                "schema": "starnetastro.cli.machine-info.v1",
                "version": "2.6.2",
                "build": "0242",
                "backend": {"id": "ort"},
                "features": {"highlight_protection": {"supported": True}},
                "options": [
                    {"name": name}
                    for name in (
                        "input",
                        "output",
                        "stride",
                        "machine_progress",
                        "upsample",
                        "disable_highlights_protection",
                    )
                ],
            }
            with patch("startrails.lib.starnet_setup.run_starnet_process", return_value=(0, json.dumps(info), "")):
                self.assertEqual(probe_starnet_installation(installation).build, "0242")
            for changed in (info | {"version": "other"}, info | {"options": []}, info | {"product": "other"}):
                with patch(
                    "startrails.lib.starnet_setup.run_starnet_process", return_value=(0, json.dumps(changed), "")
                ):
                    with self.assertRaises(StarNetSetupError):
                        probe_starnet_installation(installation)

    def test_build_starnet_cli_args(self):
        args = build_starnet_cli_args(
            executable_path="/usr/bin/starnet2",
            input_path="/tmp/in.tif",
            output_path="/tmp/out.tif",
            mask_path="/tmp/mask.tif",
            stride=256,
            disable_highlights=True,
            upsample=False,
            machine_progress=True,
        )
        expected = [
            "/usr/bin/starnet2",
            "-i",
            "/tmp/in.tif",
            "-o",
            "/tmp/out.tif",
            "-s",
            "256",
            "-m",
            "/tmp/mask.tif",
            "-d",
            "--machine-progress",
        ]
        self.assertEqual(args, expected)

        # Invalid stride (odd)
        with self.assertRaises(ValueError):
            build_starnet_cli_args("/usr/bin/starnet2", "/tmp/in.tif", "/tmp/out.tif", stride=255)

        for stride in (600, 256.0, True, "256"):
            with self.subTest(stride=stride), self.assertRaises(ValueError):
                build_starnet_cli_args("/usr/bin/starnet2", "/tmp/in.tif", "/tmp/out.tif", stride=stride)

    def test_parse_starnet_machine_info(self):
        sample_json = json.dumps(
            {
                "executable": "starnet2",
                "version": "2.6.2",
                "build": "0242",
                "backend": {"id": "ort", "display_name": "ONNX Runtime"},
                "features": {
                    "highlight_protection": {"supported": True, "default": True},
                    "linear_mtf": {"supported": True, "default": False},
                },
                "options": [{"name": "stride"}, {"name": "mask"}],
            }
        )
        info = parse_starnet_machine_info(sample_json)
        self.assertEqual(info.version, "2.6.2")
        self.assertEqual(info.build, "0242")
        self.assertEqual(info.backend_id, "ort")
        self.assertTrue(info.highlight_protection_supported)
        self.assertIn("stride", info.options)

        with self.assertRaises(StarNetError):
            parse_starnet_machine_info("Invalid JSON {")

        with self.assertRaises(StarNetError):
            parse_starnet_machine_info("123")

        for malformed in (
            {"backend": None},
            {"features": []},
            {"features": {"highlight_protection": None}},
            {"features": {"linear_mtf": False}},
            {"options": {}},
            {"options": [None]},
            {"options": [{"name": []}]},
        ):
            with self.subTest(malformed=malformed), self.assertRaises(StarNetError):
                parse_starnet_machine_info(json.dumps(malformed))

    def test_parse_starnet_progress_line(self):
        valid_line = (
            '{"schema": "starnetastro.cli.diagnostic.v1", "severity": "info", "code": "progress", "percent": 50}\n'
        )
        parsed = parse_starnet_progress_line(valid_line)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["code"], "progress")
        self.assertEqual(parsed["percent"], 50)

        # Non-JSON lines
        self.assertIsNone(parse_starnet_progress_line("Standard output message"))
        self.assertIsNone(parse_starnet_progress_line("{ malformed json"))

    def run_child(self, program, **kwargs):
        # Bound regressions involving blocking pipes without leaking child processes.
        processes = []
        timed_out = Event()

        def launch(*args, **options):
            child = subprocess.Popen(*args, **options)
            processes.append(child)
            return child

        def expire():
            timed_out.set()
            for child in processes:
                if child.poll() is None:
                    child.kill()

        watchdog = Timer(10, expire)
        watchdog.start()
        try:
            return run_starnet_process([sys.executable, "-c", program], process_runner=launch, **kwargs)
        finally:
            watchdog.cancel()
            watchdog.join()
            for child in processes:
                if child.poll() is None:
                    child.kill()
                child.wait()
                self.assertTrue(child.stdout.closed)
                self.assertTrue(child.stderr.closed)
            self.assertFalse(timed_out.is_set(), "StarNet subprocess handling stalled")

    def test_process_drains_both_streams_and_delivers_final_progress(self):
        events = []
        _, stdout, stderr = self.run_child(
            'import sys; sys.stdout.write("x" * 2000000); sys.stdout.flush(); '
            'sys.stderr.write(\'{"event":"finish"}\\n\'); sys.stderr.flush()',
            progress_callback=events.append,
        )
        self.assertEqual(len(stdout), 2000000)
        self.assertIn('"finish"', stderr)
        self.assertEqual(events, [{"event": "finish"}])

    def test_process_cancels_silent_child(self):
        with self.assertRaises(CancelledError):
            run_starnet_process(["unused"], should_interrupt=lambda: True)
        cancelled = Event()
        timer = Timer(0.2, cancelled.set)
        timer.start()
        try:
            with self.assertRaises(CancelledError):
                self.run_child("import time; time.sleep(30)", should_interrupt=cancelled.is_set)
        finally:
            timer.cancel()
            timer.join()

    @unittest.skipIf(os.name == "nt", "POSIX signal escalation")
    def test_process_escalates_and_reaps_uncooperative_child(self):
        cancelled = Event()
        with patch("startrails.lib.finish.starnet.PROCESS_TERMINATE_TIMEOUT_SECONDS", 0.1):
            with self.assertRaises(CancelledError):
                self.run_child(
                    "import signal, sys, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); "
                    'print(\'{"event":"ready"}\', file=sys.stderr, flush=True); time.sleep(30)',
                    should_interrupt=cancelled.is_set,
                    progress_callback=lambda _: cancelled.set(),
                )

    def test_process_failures_preserve_diagnostics_and_cleanup(self):
        with self.assertRaisesRegex(StarNetError, "bad input"):
            self.run_child('import sys; print("bad input", file=sys.stderr); sys.exit(2)')

        def callback(_):
            raise ValueError("callback failed")

        with self.assertRaisesRegex(ValueError, "callback failed"):
            self.run_child(
                'import sys, time; print(\'{"event":"ready"}\', file=sys.stderr, flush=True); time.sleep(30)',
                progress_callback=callback,
            )

    def test_graxpert_stats_and_dark_channels(self):
        # Normal image
        img = np.random.default_rng(0).uniform(0.1, 0.9, (128, 128, 3)).astype(np.float32)
        median, mad = compute_graxpert_stats(img)
        self.assertEqual(median.shape, (3,))
        self.assertEqual(mad.shape, (3,))
        self.assertTrue(np.all(mad > 0))

        # Dark image (constant zero)
        dark_img = np.zeros((128, 128, 3), dtype=np.float32)
        dark_med, dark_mad = compute_graxpert_stats(dark_img)
        self.assertTrue(np.all(dark_med == 0.0))
        # Ensure MIN_MAD_EPSILON prevents zero division
        self.assertTrue(np.all(dark_mad == MIN_MAD_EPSILON))

        # Check tile preprocess with dark stats does not produce NaNs or Infs
        tile = np.zeros((256, 256, 3), dtype=np.float32)
        preprocessed = graxpert_tile_preprocess(tile, dark_med, dark_mad)
        self.assertTrue(np.all(np.isfinite(preprocessed)))

    def test_graxpert_tile_preserves_highlights_and_reverses_normalization(self):
        original = np.array([[[0.1, 0.5, 0.8]]], dtype=np.float32)
        median = np.full(3, 0.2, dtype=np.float32)
        mad = np.full(3, 0.001, dtype=np.float32)
        np.testing.assert_allclose(
            graxpert_tile_preprocess(original, median, mad),
            [[[-4, 10, 10]]],
        )
        restored = graxpert_tile_postprocess(np.zeros_like(original), original, median, mad)
        np.testing.assert_allclose(restored, [[[0.2, 0.5, 0.8]]])

    def test_graxpert_postprocess_applies_highlight_gate_within_the_adapter(self):
        median = np.array([0.2, 0.2, 0.2], dtype=np.float32)
        mad = np.array([0.001, 0.001, 0.001], dtype=np.float32)
        # With this MAD the highlight gate switches at 0.45.
        original = np.array([[[0.1, 0.5, 0.8]]], dtype=np.float32)
        # The model returns standardized-space samples; -6 restores to 0.05.
        restored = graxpert_tile_postprocess(np.full_like(original, -6.0), original, median, mad)
        np.testing.assert_allclose(restored, [[[0.05, 0.5, 0.8]]], atol=1e-6)

        # Model identity keys endpoints but is independent of the selected provider.
        self.assertEqual(graxpert_model_identity(), graxpert_model_identity())
        self.assertIn("3.0.2", graxpert_model_identity())


if __name__ == "__main__":
    unittest.main()
