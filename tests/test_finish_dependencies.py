"""Tests for Finish mode dependency lifecycle, executable setup, runtime policies, and operations."""

from __future__ import annotations

from concurrent.futures import CancelledError
from dataclasses import replace
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
import time
from threading import Event
import stat
import onnxruntime as ort
from unittest.mock import MagicMock, patch
import zipfile

import numpy as np

from startrails.lib.finish.composition import compute_denoise_endpoint_signature
from startrails.lib.finish.defaults import (
    FINISH_DEFAULTS,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    SCOPE_WHOLE_IMAGE,
)
from startrails.lib.finish.graxpert import INPUT_TENSOR_NAME, graxpert_model_identity
from startrails.lib.project_finish import FinishProject
from support import QtTestCase
from startrails.lib.finish.graxpert_runtime import GraXpertSession, resolve_graxpert_runtime_policy
from startrails.lib.model_manifest import (
    GRAXPERT_MANIFEST,
    StarNetPlatformPackage,
    get_starnet_package_for_platform,
)
from startrails.lib.starnet_setup import (
    STARNET_TERMS_REVISION,
    STARNET_TERMS_SHA256,
    starnet_terms_accepted,
    StarNetInstallation,
    StarNetSetupError,
    download_starnet_package,
    extract_starnet_package,
    get_active_starnet_installation,
    install_starnet_managed,
    record_starnet_installation,
    repair_starnet_installation,
)
from startrails.op.finish.graxpert_denoise import GraXpertDenoise
from startrails.op.finish.run_starnet import RunStarNet
from startrails.ui.steps_separate import SeparateStarsSettings


class TestFinishDependencies(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        # Synthetic CLI fixtures below model the pinned Linux package on any host.
        self.enterContext(patch("startrails.lib.starnet_setup.detect_platform_target", return_value="linux-x64"))

    def tearDown(self):
        self.tmp_dir.cleanup()

    def make_fake_package(self, content: bytes = b"dummy zip archive content") -> tuple[StarNetPlatformPackage, str]:
        import hashlib

        sha = hashlib.sha256(content).hexdigest()
        pkg = StarNetPlatformPackage(
            platform_id="linux-x64",
            version="2.6.2",
            build="0242",
            backend_id="ort",
            archive_url="https://example.com/starnet.zip",
            archive_name="starnet.zip",
            archive_sha256=sha,
            archive_size_bytes=len(content),
            executable_relative_path="starnet2",
            weights_relative_path="StarNet2_weights.onnx",
        )
        return pkg, sha

    def test_download_starnet_package_validates_hash_and_size(self):
        data = b"correct payload bytes"
        pkg, sha = self.make_fake_package(data)
        dest = self.root / "downloaded.zip"

        class FakeResponse:
            def __init__(self, content):
                self._stream = io.BytesIO(content)
                self.headers = {"Content-Length": str(len(content))}

            def read(self, chunk_size=65536):
                return self._stream.read(chunk_size)

            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_val, exc_tb):
                pass

        with patch("urllib.request.urlopen", return_value=FakeResponse(data)):
            download_starnet_package(pkg, dest)
            self.assertTrue(dest.is_file())
            self.assertEqual(dest.read_bytes(), data)

        dest.unlink()
        with patch("urllib.request.urlopen", return_value=FakeResponse(b"short")):
            with self.assertRaises(StarNetSetupError):
                download_starnet_package(pkg, dest)
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())

    def test_download_starnet_package_cancellation(self):
        data = b"x" * 100000
        pkg, sha = self.make_fake_package(data)
        dest = self.root / "cancelled.zip"

        calls = 0

        def cancel_check():
            nonlocal calls
            calls += 1
            return calls >= 2

        class ChunkedResponse:
            def __init__(self):
                self._stream = io.BytesIO(data)
                self.headers = {"Content-Length": str(len(data))}

            def read(self, chunk_size=1024):
                return self._stream.read(1024)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        with patch("urllib.request.urlopen", return_value=ChunkedResponse()):
            with self.assertRaises(CancelledError):
                download_starnet_package(pkg, dest, cancel_check=cancel_check, chunk_size=1024)
            self.assertFalse(dest.exists())
            self.assertFalse(dest.with_suffix(dest.suffix + ".part").exists())

    def test_extract_starnet_package_zip_slip_prevention(self):
        dest = self.root / "extracted"

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("../../escape.txt", b"malicious content")
        zip_buf.seek(0)
        archive_path = self.root / "evil.zip"
        archive_path.write_bytes(zip_buf.getvalue())

        with self.assertRaisesRegex(StarNetSetupError, "Archive entry escapes"):
            extract_starnet_package(archive_path, dest)

    def test_extract_starnet_package_safe_extraction_and_permissions(self):
        dest = self.root / "safe_extracted"
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("starnet2", b"binary")
            zf.writestr("StarNet2_weights.onnx", b"weights")
        zip_buf.seek(0)
        archive_path = self.root / "safe.zip"
        archive_path.write_bytes(zip_buf.getvalue())

        extract_starnet_package(archive_path, dest)
        exec_file = dest / "starnet2"
        self.assertTrue(exec_file.is_file())
        if not os.name == "nt":
            self.assertTrue(os.access(exec_file, os.X_OK))

    def test_install_starnet_managed_atomic_publication_and_rollback(self):
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w") as zf:
            zf.writestr("starnet2", b"fake binary")
            zf.writestr("StarNet2_weights.onnx", b"fake weights")
        zip_bytes = zip_buf.getvalue()
        pkg, sha = self.make_fake_package(zip_bytes)

        storage = self.root / "storage"
        version_tag = f"starnet2-{pkg.version}-{pkg.build}"
        target_dir = storage / version_tag
        target_dir.mkdir(parents=True)
        (target_dir / "old_marker.txt").write_text("prior working version")

        archive_dest = storage / pkg.archive_name
        archive_dest.write_bytes(zip_bytes)

        # Probe failure restores prior target_dir
        with (
            patch("startrails.lib.starnet_setup.download_starnet_package"),
            patch(
                "startrails.lib.starnet_setup.probe_starnet_installation", side_effect=StarNetSetupError("Probe failed")
            ),
        ):
            with self.assertRaises(StarNetSetupError):
                install_starnet_managed(pkg, storage_dir=storage)
            self.assertTrue(target_dir.is_dir())
            self.assertTrue((target_dir / "old_marker.txt").is_file())
            self.assertFalse((storage / f".prev_{version_tag}").exists())

        # Probe success atomically replaces target_dir
        fake_probe_info = MagicMock()
        with (
            patch("startrails.lib.starnet_setup.download_starnet_package"),
            patch("startrails.lib.starnet_setup.probe_starnet_installation", return_value=fake_probe_info),
            patch("startrails.lib.starnet_setup.smoke_test_starnet_installation"),
        ):
            inst = install_starnet_managed(pkg, storage_dir=storage)
            self.assertEqual(inst.executable.name, "starnet2")
            self.assertFalse((target_dir / "old_marker.txt").exists())
            self.assertTrue((storage / f".prev_{version_tag}" / "old_marker.txt").is_file())

        # A failure after the new directory was published must restore the working install.
        marker = target_dir / "working.txt"
        marker.write_text("working")
        with (
            patch("startrails.lib.starnet_setup.smoke_test_starnet_installation"),
            patch(
                "startrails.lib.starnet_setup.probe_starnet_installation",
                side_effect=[fake_probe_info, StarNetSetupError("Published probe failed")],
            ),
        ):
            with self.assertRaisesRegex(StarNetSetupError, "Published probe failed"):
                install_starnet_managed(pkg, storage_dir=storage)
        self.assertEqual(marker.read_text(), "working")
        self.assertFalse(list(storage.glob(".staging_*")))

    def test_archive_rejects_sibling_prefix_escape_and_links(self):
        for filename, symlink in (("../extracted-sibling/payload", False), ("link", True)):
            with self.subTest(filename=filename):
                archive = self.root / "unsafe.zip"
                with zipfile.ZipFile(archive, "w") as stream:
                    info = zipfile.ZipInfo(filename)
                    if symlink:
                        info.create_system = 3
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    stream.writestr(info, "../outside")
                with self.assertRaises(StarNetSetupError):
                    extract_starnet_package(archive, self.root / "extracted")
                self.assertFalse((self.root / "extracted-sibling").exists())

    def test_repair_requires_current_full_terms_acceptance(self):
        state = {"starnet": {"terms_accepted": True, "terms_revision": "2.6.2"}}
        self.assertFalse(starnet_terms_accepted(state))
        with self.assertRaisesRegex(StarNetSetupError, "Accept the current"):
            repair_starnet_installation(state)
        state["starnet"].update(terms_revision=STARNET_TERMS_REVISION, terms_sha256=STARNET_TERMS_SHA256)
        self.assertTrue(starnet_terms_accepted(state))

    def test_record_and_get_active_starnet_installation(self):
        state = {}
        fake_exec = self.root / "bin" / "starnet2"
        fake_exec.parent.mkdir(parents=True)
        fake_exec.write_text("exec")
        fake_exec.chmod(0o755)
        fake_weights = self.root / "bin" / "StarNet2_weights.onnx"
        fake_weights.write_text("weights")

        inst = StarNetInstallation(
            executable=fake_exec,
            weights=fake_weights,
            package=get_starnet_package_for_platform("linux-x64"),
        )
        record_starnet_installation(state, inst, managed=True, terms_accepted=True)

        self.assertIn("starnet", state)
        self.assertEqual(state["starnet"]["terms_revision"], STARNET_TERMS_REVISION)
        self.assertTrue(state["starnet"]["terms_accepted"])

        retrieved = get_active_starnet_installation(state)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.executable, fake_exec.resolve())

        # When executable deleted, returns None
        fake_exec.unlink()
        self.assertIsNone(get_active_starnet_installation(state))

    def test_repair_starnet_installation(self):
        fake_exec = self.root / "bin" / "starnet2"
        fake_exec.parent.mkdir(parents=True)
        fake_exec.write_text("exec")
        fake_exec.chmod(0o755)
        fake_weights = self.root / "bin" / "StarNet2_weights.onnx"
        fake_weights.write_text("weights")

        inst = StarNetInstallation(
            executable=fake_exec,
            weights=fake_weights,
            package=get_starnet_package_for_platform("linux-x64"),
        )
        state = {}
        record_starnet_installation(state, inst, managed=False, terms_accepted=True)

        with (
            patch("startrails.lib.starnet_setup.probe_starnet_installation") as mock_probe,
            patch("startrails.lib.starnet_setup.smoke_test_starnet_installation"),
        ):
            repaired = repair_starnet_installation(state)
            self.assertEqual(repaired.executable, fake_exec.resolve())
            mock_probe.assert_called_once()

    def test_runtime_policy_is_loaded_without_probing_and_rejects_stale_state(self):
        policy = {
            "provider": "CPUExecutionProvider",
            "device": "cpu",
            "verified": True,
            "ort_version": ort.__version__,
            "model_sha256": GRAXPERT_MANIFEST.sha256,
        }
        path = self.root / "policy.json"
        with patch("onnxruntime.InferenceSession") as create_session:
            with self.assertRaisesRegex(RuntimeError, "setup or repair"):
                resolve_graxpert_runtime_policy(path)
            path.write_text(json.dumps(policy))
            self.assertEqual(resolve_graxpert_runtime_policy(path), policy)
            policy["ort_version"] = "old"
            path.write_text(json.dumps(policy))
            with self.assertRaisesRegex(RuntimeError, "stale or invalid"):
                resolve_graxpert_runtime_policy(path)
            create_session.assert_not_called()

    def test_setup_verifies_real_inference_and_detects_gpu_fallback(self):
        from setup.check_finish_models import check_graxpert

        sample = np.full((256, 256, 3), 0.5, np.float32)
        session = MagicMock()
        session.get_providers.return_value = ["CPUExecutionProvider"]
        session.run.return_value = [np.zeros((1, 256, 256, 3), np.float32)]
        with (
            patch("setup.check_finish_models.verify_file_integrity", return_value=True),
            patch("setup.check_finish_models.ort.InferenceSession", return_value=session),
        ):
            report = check_graxpert(self.root / "model.onnx", sample, variant="cu133")
            policy = report["selected_policy"]
            self.assertEqual(policy["provider"], "CPUExecutionProvider")
            self.assertIn("fell back to CPU", policy["gpu_error"])
            self.assertTrue(policy["verified"])
            session.run.side_effect = RuntimeError("CPU inference failed")
            with self.assertRaisesRegex(RuntimeError, "CPU inference failed"):
                check_graxpert(self.root / "model.onnx", sample, variant="cpu")

    def test_gpu_policy_requires_cuda_kernel_execution(self):
        from setup.check_finish_models import check_graxpert

        sample = np.full((256, 256, 3), 0.5, np.float32)
        profile = self.root / "profile.json"

        def create_session(path, *, sess_options, providers):
            session = MagicMock()
            session.get_providers.return_value = providers
            session.run.return_value = [np.zeros((1, 256, 256, 3), np.float32)]
            session.end_profiling.return_value = str(profile)
            return session

        with (
            patch("setup.check_finish_models.verify_file_integrity", return_value=True),
            patch("setup.check_finish_models.ort.InferenceSession", side_effect=create_session),
        ):
            for executed_provider in ("CPUExecutionProvider", "CUDAExecutionProvider"):
                with self.subTest(executed_provider=executed_provider):
                    profile.write_text(json.dumps([{"args": {"provider": executed_provider}}]))
                    policy = check_graxpert(self.root / "model.onnx", sample, variant="cu133")["selected_policy"]
                    self.assertEqual(policy["provider"], executed_provider)
                    self.assertEqual(policy["gpu_error"] is None, executed_provider == "CUDAExecutionProvider")

    def test_missing_model_setup_does_not_block_other_modes(self):
        from setup.check_runtime import main

        policy_path = self.root / "runtime.json"
        with (
            patch("startrails.paths.APPLICATION_DIR", self.root),
            patch("startrails.lib.finish.graxpert_runtime.GRAXPERT_RUNTIME_POLICY_PATH", policy_path),
            patch("sys.argv", ["check_runtime.py", "--variant", "cpu"]),
        ):
            main()
        policy = json.loads(policy_path.read_text())
        self.assertFalse(policy["verified"])
        with self.assertRaisesRegex(RuntimeError, "model is missing"):
            resolve_graxpert_runtime_policy(policy_path)

    def test_graxpert_session_tiling_hann_blending_and_cancellation(self):
        model_path = self.root / "fake_model.onnx"
        model_path.write_bytes(b"dummy")

        with patch("onnxruntime.InferenceSession") as mock_ort:
            mock_sess = MagicMock()
            mock_sess.get_providers.return_value = ["CPUExecutionProvider"]
            mock_sess.run.side_effect = lambda names, feeds: [feeds["gen_input_image"].copy()]
            mock_ort.return_value = mock_sess

            session = GraXpertSession(model_path=model_path, provider="CPUExecutionProvider")

            image = np.full((512, 512, 3), 0.5, dtype=np.float32)
            progress_events = []

            def on_progress(total, step, current, is_done, payload):
                progress_events.append((current, total))

            denoised = session.denoise_full_strength(image, progress_bar=on_progress)
            self.assertEqual(denoised.shape, image.shape)
            np.testing.assert_allclose(denoised, image, atol=1e-6)
            for shape in ((1, 1, 3), (31, 47, 3), (259, 401, 3)):
                with self.subTest(shape=shape):
                    image_variant = np.random.default_rng(0).uniform(0.1, 0.8, shape).astype(np.float32)
                    result = session.denoise_full_strength(image_variant)
                    np.testing.assert_allclose(result, image_variant, atol=1e-6)
            self.assertGreater(len(progress_events), 0)
            self.assertEqual(progress_events[-1][0], progress_events[-1][1])

            cancelled_calls = 0

            def should_interrupt():
                nonlocal cancelled_calls
                cancelled_calls += 1
                return cancelled_calls >= 2

            with self.assertRaises(CancelledError):
                session.denoise_full_strength(image, should_interrupt=should_interrupt)

    def test_graxpert_session_retries_recognized_cuda_allocation_failure_on_cpu(self):
        model_path = self.root / "fake_model.onnx"
        model_path.write_bytes(b"dummy")
        image = np.random.default_rng(0).uniform(0.1, 0.8, (256, 256, 3)).astype(np.float32)

        gpu_session = MagicMock()
        gpu_session.get_providers.return_value = ["CUDAExecutionProvider"]
        gpu_session.run.side_effect = RuntimeError("CUDA failure 2: out of memory")
        cpu_session = MagicMock()
        cpu_session.get_providers.return_value = ["CPUExecutionProvider"]
        cpu_session.run.side_effect = lambda names, feeds: [feeds[INPUT_TENSOR_NAME].copy()]

        with patch("onnxruntime.InferenceSession", side_effect=[gpu_session, cpu_session]) as create_session:
            session = GraXpertSession(model_path=model_path, provider="CUDAExecutionProvider")
            result = session.denoise_full_strength(image)

        self.assertEqual(create_session.call_count, 2)
        self.assertEqual(create_session.call_args_list[0].kwargs["providers"], ["CUDAExecutionProvider"])
        self.assertEqual(create_session.call_args_list[1].kwargs["providers"], ["CPUExecutionProvider"])
        self.assertEqual(session.configured_provider, "CUDAExecutionProvider")
        self.assertEqual(session.execution_provider, "CPUExecutionProvider")
        self.assertIn("out of memory", session.fallback_reason)
        np.testing.assert_allclose(result, image, atol=1e-6)

    def test_graxpert_session_propagates_non_allocation_execution_errors(self):
        model_path = self.root / "fake_model.onnx"
        model_path.write_bytes(b"dummy")
        image = np.full((256, 256, 3), 0.5, dtype=np.float32)

        gpu_session = MagicMock()
        gpu_session.get_providers.return_value = ["CUDAExecutionProvider"]
        gpu_session.run.side_effect = RuntimeError("CUDA kernel launch failed: invalid argument")

        with patch("onnxruntime.InferenceSession", return_value=gpu_session) as create_session:
            session = GraXpertSession(model_path=model_path, provider="CUDAExecutionProvider")
            with self.assertRaisesRegex(RuntimeError, "invalid argument"):
                session.denoise_full_strength(image)

        self.assertEqual(create_session.call_count, 1)
        self.assertEqual(session.execution_provider, "CUDAExecutionProvider")
        self.assertIsNone(session.fallback_reason)

    def test_run_starnet_operation_adapter(self):
        exec_file = self.root / "starnet2"
        exec_file.write_text("echo fake")
        src_img = self.root / "in.tif"
        src_img.write_text("in")
        out_starless = self.root / "starless.tif"
        out_stars = self.root / "stars.tif"

        op = RunStarNet()
        progress_records = []
        op.observers.append(lambda total, increment, count, done, data: progress_records.append(data))

        def fake_run(cmd, cwd=None, progress_callback=None, should_interrupt=None):
            if progress_callback:
                progress_callback({"percent": 50})
                progress_callback({"percent": 100})
            Path(cmd[cmd.index("-o") + 1]).write_text("starless output")
            Path(cmd[cmd.index("-m") + 1]).write_text("stars output")

        with patch("startrails.op.finish.run_starnet.run_starnet_process", side_effect=fake_run):
            res = op.run(
                exec_file,
                src_img,
                out_starless,
                output_stars_path=out_stars,
                stride=256,
                disable_highlights=False,
                upsample=False,
            )
            self.assertIsNotNone(res)
            self.assertEqual(res, (out_starless, out_stars))
            self.assertTrue(
                any("Separating stars: 50%" in (d.get("desc") if isinstance(d, dict) else "") for d in progress_records)
            )

    def test_starnet_cancellation_preserves_previous_outputs(self):
        executable = self.root / "starnet2"
        executable.write_bytes(b"helper")
        source = self.root / "source.tif"
        source.write_bytes(b"input")
        output = self.root / "starless.tif"
        output.write_bytes(b"previous")
        operation = RunStarNet()

        def run(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"partial output")
            operation.requestInterrupt()

        with patch("startrails.op.finish.run_starnet.run_starnet_process", side_effect=run):
            result = operation.run(executable, source, output, stride=256, disable_highlights=False, upsample=False)
        self.assertIsNone(result)
        self.assertEqual(output.read_bytes(), b"previous")
        self.assertFalse(list(self.root.glob(".starnet-*")))

    def test_graxpert_denoise_operation_computes_full_strength_endpoint(self):
        img = np.full((256, 256, 3), 0.4, dtype=np.float32)
        expected = np.full((256, 256, 3), 0.1, dtype=np.float32)
        mock_session = MagicMock()
        mock_session.denoise_full_strength.return_value = expected

        op = GraXpertDenoise()
        denoised, written = op.denoise(
            img,
            session=mock_session,
            bit_depth=16,
            settings=FINISH_DEFAULTS,
        )
        self.assertIsNone(written)
        np.testing.assert_array_equal(denoised, expected)
        args, kwargs = mock_session.denoise_full_strength.call_args
        np.testing.assert_array_equal(args[0], img)
        self.assertNotIn("strength", kwargs)

        destination = self.root / "endpoint.tif"
        denoised, written = op.denoise(
            img,
            session=mock_session,
            bit_depth=16,
            settings=FINISH_DEFAULTS,
            output_path=destination,
        )
        self.assertEqual(written, destination)
        self.assertTrue(destination.is_file())

    def test_workflow_lifecycle_methods(self):
        from startrails.workflow.finish import FinishWorkflow

        mock_app = MagicMock()
        mock_app.state = {}
        mock_app.project = MagicMock()

        wf = FinishWorkflow(mock_app)

        # Initially unconfigured
        status = wf.get_starnet_status()
        self.assertFalse(status["configured"])
        self.assertFalse(status["terms_accepted"])

        # Accept terms
        wf.accept_starnet_terms()
        self.assertTrue(mock_app.state["starnet"]["terms_accepted"])
        self.assertEqual(mock_app.state["starnet"]["terms_revision"], STARNET_TERMS_REVISION)

        # Record installation
        fake_exec = self.root / "starnet2"
        fake_exec.write_text("bin")
        fake_exec.chmod(0o755)
        fake_weights = self.root / "StarNet2_weights.onnx"
        fake_weights.write_text("weights")
        inst = StarNetInstallation(fake_exec, fake_weights, get_starnet_package_for_platform("linux-x64"))
        wf.set_starnet_installation(inst, managed=True, terms_accepted=True)

        status_after = wf.get_starnet_status()
        self.assertTrue(status_after["configured"])
        self.assertTrue(status_after["managed"])
        self.assertEqual(status_after["executable"], str(fake_exec.resolve()))

        # GraXpert status surfaces the resolved provider policy for diagnostics.
        policy = {"provider": "CUDAExecutionProvider", "device": "cuda", "verified": True}
        with patch("startrails.workflow.finish.resolve_graxpert_runtime_policy", return_value=policy):
            gx_status = wf.get_graxpert_status()
        self.assertEqual(gx_status["policy"], policy)
        self.assertEqual(gx_status["provider"], "CUDAExecutionProvider")
        self.assertEqual(gx_status["device"], "cuda")
        self.assertIn("model_ready", gx_status)

    def test_check_finish_models_persist_state(self):
        from setup.check_finish_models import main as check_models_main

        state_file = self.root / "app_state.json"
        fake_exec = self.root / "starnet2"
        fake_exec.write_text("bin")
        fake_exec.chmod(0o755)
        fake_weights = self.root / "StarNet2_weights.onnx"
        fake_weights.write_text("weights")

        with (
            patch(
                "setup.check_finish_models.check_graxpert",
                return_value={"selected_policy": {"provider": "CPUExecutionProvider", "device": "cpu"}},
            ),
            patch(
                "setup.check_finish_models.check_starnet",
                return_value=(np.zeros((512, 512, 3)), {"identity": "2.6.2-0242/ort"}),
            ),
            patch(
                "sys.argv",
                [
                    "check_finish_models.py",
                    "--variant",
                    "cpu",
                    "--accept-starnet-terms",
                    "--starnet",
                    str(fake_exec),
                    "--runtime-policy",
                    str(self.root / "policy.json"),
                    "--persist-state",
                    str(state_file),
                ],
            ),
        ):
            check_models_main()

        self.assertTrue(state_file.is_file())
        saved = json.loads(state_file.read_text())
        self.assertNotIn("graxpert_runtime", saved)
        self.assertEqual(json.loads((self.root / "policy.json").read_text())["provider"], "CPUExecutionProvider")
        self.assertIn("starnet", saved)
        self.assertEqual(saved["starnet"]["executable"], str(fake_exec.resolve()))
        self.assertTrue(saved["starnet"]["terms_accepted"])

    def test_ui_separate_stars_settings(self):
        from support import qt_app

        qt_app()
        widget = SeparateStarsSettings()
        self.addCleanup(widget.deleteLater)
        widget.show()

        # Unconfigured state
        widget.refresh_status({"configured": False}, has_prerequisites=True)
        self.assertTrue(widget.unconfigured_box.isVisible())
        self.assertFalse(widget.configured_box.isVisible())
        self.assertFalse(widget.btn_separate.isEnabled())

        # Configured state
        status = {
            "configured": True,
            "version": "2.6.2",
            "build": "0242",
            "backend_id": "ort",
            "managed": True,
        }
        widget.refresh_status(status, has_prerequisites=True)
        self.assertFalse(widget.unconfigured_box.isVisible())
        self.assertTrue(widget.configured_box.isVisible())
        self.assertTrue(widget.btn_separate.isEnabled())
        self.assertIn("StarNet2 v2.6.2-0242 (ort) • Managed", widget.lbl_starnet_info.text())

        # Prerequisite missing disables separation button
        widget.refresh_status(status, has_prerequisites=False)
        self.assertFalse(widget.btn_separate.isEnabled())
        widget.close()


class TestFinishDependencyUI(QtTestCase):
    def test_closing_setup_keeps_worker_owned_until_it_stops(self):
        from startrails.ui.starnet_dialog import StarNetSetupDialog
        from PySide6.QtTest import QSignalSpy

        entered, release = Event(), Event()

        def install(*, progress_callback, cancel_check):
            entered.set()
            release.wait(5)
            raise CancelledError()

        dialog = StarNetSetupDialog(operation=install)
        self.addCleanup(dialog.deleteLater)
        finished = QSignalSpy(dialog.finished)
        dialog.show()
        dialog.start()
        try:
            self.assertTrue(entered.wait(2))
            dialog.close()
            self.assertTrue(dialog.worker.isRunning())
            self.assertTrue(dialog.isVisible())
            self.assertEqual(finished.count(), 0)
            release.set()
            deadline = time.monotonic() + 5
            while finished.count() == 0 and time.monotonic() < deadline:
                self.qt.processEvents()
                time.sleep(0.01)
            self.assertEqual(finished.count(), 1)
            self.assertFalse(dialog.worker.isRunning())
        finally:
            release.set()
            self.assertTrue(dialog.worker.wait(5000))

    def prepare_separated_project(self, name: str, *, source, starless, stars, mask):
        """Publish a small current separation and canonical mask without model work."""
        from startrails.lib.denoise.mask import MaskHandler
        from startrails.lib.image_io import imwrite

        project = FinishProject(project_file=str(self.root / f"{name}.proj_finish"))
        source_path = imwrite(self.root / f"{name}_source.tif", source, bit_depth=16)
        project.set_source_image(source_path)
        starless_path = project.artifact_path(ROLE_SEPARATED_STARLESS, for_write=True)
        stars_path = project.artifact_path(ROLE_SEPARATED_STARS, for_write=True)
        imwrite(starless_path, starless, bit_depth=16)
        imwrite(stars_path, stars, bit_depth=16)
        self.assertTrue(
            project.publish_separation(
                starless_path,
                stars_path,
                signature="separation-a",
                model_identity="starnet-model",
                expected_revision=project.processing_revision,
            )
        )
        mask_path = project.artifact_path(ROLE_SKY_MASK, for_write=True)
        MaskHandler.save_mask(mask, mask_path)
        project.record_artifact(ROLE_SKY_MASK, mask_path)
        return project

    def make_denoise_app(self, project):
        from startrails.workflow.finish import FinishWorkflow

        app = self.make_app(project)
        return app, FinishWorkflow(app)

    def test_workflow_zero_strength_publishes_without_a_model(self):
        from startrails.lib.image_io import imread

        image = np.full((16, 24, 3), 0.4, np.float32)
        starless = np.full((16, 24, 3), 0.3, np.float32)
        project = self.prepare_separated_project(
            "zero_strength",
            source=image,
            starless=starless,
            stars=np.zeros_like(starless),
            mask=np.ones((16, 24), np.float32),
        )
        project.update_settings(replace(project.get_settings(), denoise_strength=0.0))
        app, workflow = self.make_denoise_app(project)

        with (
            patch("startrails.workflow.finish.resolve_graxpert_runtime_policy") as resolve_policy,
            patch("startrails.workflow.finish.GraXpertSession") as init_session,
        ):
            result = workflow.do_denoise_starless()
            resolve_policy.assert_not_called()
            init_session.assert_not_called()
        self.assertEqual(result.operation, "Finished Starless")
        finished = project.current_artifact_path(ROLE_FINISHED_STARLESS)
        self.assertIsNotNone(finished)
        np.testing.assert_allclose(imread(finished, to_rgb=True, as_float=True), starless, atol=0.5 / 65535)
        self.assertIsNone(app.activeOperation)

        with workflow.operation_session():
            session_operation = app.activeOperation
            session_operation.requestInterrupt()
            self.assertIsNone(workflow.do_denoise_starless())
            self.assertIs(app.activeOperation, session_operation)

    def test_workflow_reuses_full_strength_endpoint_across_strength_and_scope(self):
        from startrails.lib.finish.composition import blend_denoise
        from startrails.lib.image_io import imread

        source = np.full((16, 24, 3), 0.4, np.float32)
        starless = np.full((16, 24, 3), 0.3, np.float32)
        mask = np.zeros((16, 24), np.float32)
        mask[:, :12] = 1.0
        project = self.prepare_separated_project(
            "endpoint_cache",
            source=source,
            starless=starless,
            stars=np.zeros_like(starless),
            mask=mask,
        )
        project.update_settings(replace(project.get_settings(), denoise_strength=50.0, denoise_scope="sky_only"))
        app, workflow = self.make_denoise_app(project)
        denoised = np.full_like(starless, 0.1)
        policy = {"provider": "CPUExecutionProvider", "device": "cpu", "verified": True}

        with (
            patch("startrails.workflow.finish.resolve_graxpert_runtime_policy", return_value=policy),
            patch("startrails.workflow.finish.GraXpertSession") as init_session,
        ):
            init_session.return_value.denoise_full_strength.return_value = denoised
            app.activeOperation = None
            workflow.do_denoise_starless()

            endpoint_signature = compute_denoise_endpoint_signature("separation-a", graxpert_model_identity())
            endpoint = project.current_artifact_path(
                ROLE_DENOISE_ENDPOINT,
                options={"separation_signature": "separation-a", "denoise_signature": endpoint_signature},
            )
            self.assertIsNotNone(endpoint)
            self.assertEqual(project.denoise_signature, endpoint_signature)
            endpoint_bytes = endpoint.read_bytes()
            np.testing.assert_allclose(
                imread(project.current_artifact_path(ROLE_FINISHED_STARLESS), to_rgb=True, as_float=True),
                blend_denoise(starless, denoised, mask, 50.0, "sky_only"),
                atol=0.5 / 65535,
            )

            project.update_settings(
                replace(project.get_settings(), denoise_strength=100.0, denoise_scope=SCOPE_WHOLE_IMAGE)
            )
            workflow.do_denoise_starless()
            self.assertEqual(init_session.call_count, 1)
            self.assertEqual(endpoint.read_bytes(), endpoint_bytes)
            np.testing.assert_allclose(
                imread(project.current_artifact_path(ROLE_FINISHED_STARLESS), to_rgb=True, as_float=True),
                blend_denoise(starless, denoised, None, 100.0, SCOPE_WHOLE_IMAGE),
                atol=0.5 / 65535,
            )

        self.assertFalse(workflow.invalidate_if_graxpert_changed())
        project.denoise_model_identity = "previous-graxpert-model"
        self.assertTrue(workflow.invalidate_if_graxpert_changed())
        self.assertIsNone(project.current_artifact_path(ROLE_DENOISE_ENDPOINT))
        self.assertIsNone(project.current_artifact_path(ROLE_DENOISED_STARLESS))
        self.assertIsNone(project.current_artifact_path(ROLE_FINISHED_STARLESS))

    def test_workflow_reports_execution_provider_and_fallback_reason(self):
        source = np.full((16, 24, 3), 0.4, np.float32)
        starless = np.full((16, 24, 3), 0.3, np.float32)
        project = self.prepare_separated_project(
            "fallback_status",
            source=source,
            starless=starless,
            stars=np.zeros_like(starless),
            mask=np.ones((16, 24), np.float32),
        )
        project.update_settings(replace(project.get_settings(), denoise_strength=50.0, denoise_scope=SCOPE_WHOLE_IMAGE))
        app, workflow = self.make_denoise_app(project)
        policy = {"provider": "CUDAExecutionProvider", "device": "cuda", "verified": True}
        fake_session = MagicMock()
        fake_session.configured_provider = "CUDAExecutionProvider"
        fake_session.execution_provider = "CPUExecutionProvider"
        fake_session.fallback_reason = (
            "CUDAExecutionProvider allocation failure: CUDA failure 2: out of memory; retried on CPUExecutionProvider."
        )
        fake_session.denoise_full_strength.return_value = np.full_like(starless, 0.1)

        with (
            patch("startrails.workflow.finish.resolve_graxpert_runtime_policy", return_value=policy),
            patch("startrails.workflow.finish.GraXpertSession", return_value=fake_session),
        ):
            workflow.do_denoise_starless()
            status = workflow.get_graxpert_status()

        # Configured provider remains the setup-owned policy value.
        self.assertEqual(status["provider"], "CUDAExecutionProvider")
        self.assertEqual(status["execution_provider"], "CPUExecutionProvider")
        self.assertIn("out of memory", status["fallback_reason"])

        # A session from a previous provider lane must not report stale execution state.
        with patch(
            "startrails.workflow.finish.resolve_graxpert_runtime_policy",
            return_value={"provider": "CPUExecutionProvider", "device": "cpu", "verified": True},
        ):
            stale_status = workflow.get_graxpert_status()
        self.assertEqual(stale_status["provider"], "CPUExecutionProvider")
        self.assertIsNone(stale_status["execution_provider"])
        self.assertIsNone(stale_status["fallback_reason"])

    def test_workflow_recombine_uses_finished_plate_with_separated_negative_correction(self):
        from startrails.lib.image_io import imread

        source = np.full((16, 24, 3), 0.2, np.float32)
        starless = np.full((16, 24, 3), 0.4, np.float32)
        stars = np.full((16, 24, 3), 0.1, np.float32)
        project = self.prepare_separated_project(
            "finished_recombine",
            source=source,
            starless=starless,
            stars=stars,
            mask=np.ones((16, 24), np.float32),
        )
        project.update_settings(
            replace(project.get_settings(), denoise_strength=100.0, denoise_scope=SCOPE_WHOLE_IMAGE)
        )
        app, workflow = self.make_denoise_app(project)
        policy = {"provider": "CPUExecutionProvider", "device": "cpu", "verified": True}
        denoised = np.full_like(starless, 0.5)

        with (
            patch("startrails.workflow.finish.resolve_graxpert_runtime_policy", return_value=policy),
            patch("startrails.workflow.finish.GraXpertSession") as init_session,
        ):
            init_session.return_value.denoise_full_strength.return_value = denoised
            workflow.do_denoise_starless()
            result = workflow.do_recombine()

        self.assertIsNotNone(result)
        # F = 0.5, S = 0.1, and N = min(0.2 - 0.4, 0) = -0.2 from the separated plate.
        np.testing.assert_allclose(
            imread(project.current_artifact_path(ROLE_FINISHED_COMPOSITE), to_rgb=True, as_float=True),
            0.4,
            atol=1.5 / 65535,
        )

    def test_workflow_cancelled_inference_preserves_previous_finished_plate(self):
        from concurrent.futures import CancelledError
        from startrails.lib.image_io import imread

        source = np.full((16, 24, 3), 0.4, np.float32)
        starless = np.full((16, 24, 3), 0.3, np.float32)
        project = self.prepare_separated_project(
            "stale_denoise",
            source=source,
            starless=starless,
            stars=np.zeros_like(starless),
            mask=np.ones((16, 24), np.float32),
        )
        project.update_settings(replace(project.get_settings(), denoise_strength=0.0))
        app, workflow = self.make_denoise_app(project)
        workflow.do_denoise_starless()
        finished = project.current_artifact_path(ROLE_FINISHED_STARLESS)
        previous_bytes = finished.read_bytes()
        previous_pixels = imread(finished, to_rgb=True, as_float=True)
        endpoint = project.artifact_path(ROLE_DENOISE_ENDPOINT, for_write=True)
        self.assertFalse(endpoint.exists())

        project.update_settings(replace(project.get_settings(), denoise_strength=75.0, denoise_scope=SCOPE_WHOLE_IMAGE))
        policy = {"provider": "CPUExecutionProvider", "device": "cpu", "verified": True}
        with (
            patch("startrails.workflow.finish.resolve_graxpert_runtime_policy", return_value=policy),
            patch("startrails.workflow.finish.GraXpertSession") as init_session,
        ):
            init_session.return_value.denoise_full_strength.side_effect = CancelledError()
            self.assertIsNone(workflow.do_denoise_starless())

        self.assertEqual(finished.read_bytes(), previous_bytes)
        np.testing.assert_array_equal(imread(finished, to_rgb=True, as_float=True), previous_pixels)
        self.assertFalse(endpoint.exists())
        self.assertFalse(list(finished.parent.glob(".artifact-*")))

    def test_workflow_starnet_adapter_restores_operation_and_publishes(self):
        from startrails.workflow.finish import FinishWorkflow

        project = FinishProject(project_file=str(self.root / "adapter.proj_finish"))
        app = self.make_app(project)
        workflow = FinishWorkflow(app)
        executable, weights, source, output = (
            self.root / name for name in ("starnet2", "StarNet2_weights.onnx", "input.tif", "output.tif")
        )
        for file in (executable, weights, source):
            file.write_bytes(b"fixture")
        executable.chmod(0o755)
        installation = StarNetInstallation(executable, weights, get_starnet_package_for_platform("linux-x64"))

        def run(cmd, **kwargs):
            Path(cmd[cmd.index("-o") + 1]).write_bytes(b"output")

        with (
            patch("startrails.lib.starnet_setup.detect_platform_target", return_value="linux-x64"),
            patch("startrails.op.finish.run_starnet.run_starnet_process", side_effect=run),
        ):
            workflow.set_starnet_installation(installation, managed=False, terms_accepted=True)
            with workflow.operation_session():
                session = app.activeOperation
                self.assertEqual(workflow.do_run_starnet(source, output, stride=project.starnet_stride), (output, None))
                self.assertIs(app.activeOperation, session)
                session.requestInterrupt()
                self.assertIsNone(workflow.do_run_starnet(source, output, stride=project.starnet_stride))
            self.assertEqual(output.read_bytes(), b"output")
            self.assertIsNone(app.activeOperation)


if __name__ == "__main__":
    unittest.main()
