"""Tests for Finish mode dependency lifecycle, executable setup, runtime policies, and operations."""

from __future__ import annotations

from concurrent.futures import CancelledError
from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest
import onnxruntime as ort
from unittest.mock import MagicMock, patch

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
from startrails.lib.finish.graxpert_runtime import GraXpertSession, resolve_graxpert_runtime_policy
from startrails.lib.finish.nox import NoxSession
from startrails.lib.model_manifest import GRAXPERT_MANIFEST, NOX_MANIFEST
from startrails.lib.project_finish import FinishProject
from startrails.op.finish.graxpert_denoise import GraXpertDenoise
from startrails.op.finish.remove_stars import RemoveStars
from startrails.ui.steps_separate import SeparateStarsSettings
from support import QtTestCase


class TestFinishDependencies(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_nox_session_tiling_hann_blending_and_cancellation(self):
        model_path = self.root / "fake_nox.pt"
        model_path.write_bytes(b"dummy")

        class FakeNoxModel:
            def __call__(self, batch):
                return batch.clone()

        with patch("startrails.lib.finish.nox.load_nox_model", return_value=FakeNoxModel()):
            session = NoxSession(model_path=model_path, device="cpu")
            image = np.full((600, 600, 3), 0.5, dtype=np.float32)
            progress_events = []

            def on_progress(total, step, current, is_done, payload):
                progress_events.append((current, total))

            starless = session.remove_stars(image, stride=256, progress_bar=on_progress)
            self.assertEqual(starless.shape, image.shape)
            self.assertEqual(starless.dtype, np.float32)
            np.testing.assert_allclose(starless, image, atol=1e-5)

            for shape in ((1, 1, 3), (31, 47, 3), (259, 401, 3)):
                with self.subTest(shape=shape):
                    variant = np.random.default_rng(0).uniform(0.1, 0.8, shape).astype(np.float32)
                    result = session.remove_stars(variant, stride=256)
                    np.testing.assert_allclose(result, variant, atol=1e-5)

            self.assertGreater(len(progress_events), 0)
            self.assertEqual(progress_events[-1][0], progress_events[-1][1])

            cancelled_calls = 0

            def should_interrupt():
                nonlocal cancelled_calls
                cancelled_calls += 1
                return cancelled_calls >= 2

            with self.assertRaises(CancelledError):
                session.remove_stars(image, stride=256, should_interrupt=should_interrupt)

    def test_nox_session_retries_recognized_cuda_allocation_failure_on_cpu(self):
        model_path = self.root / "fake_nox.pt"
        model_path.write_bytes(b"dummy")
        image = np.random.default_rng(0).uniform(0.1, 0.8, (256, 256, 3)).astype(np.float32)

        class CudaOomModel:
            def __call__(self, batch):
                raise RuntimeError("CUDA out of memory. Tried to allocate 512.00 MiB")

        class CpuIdentityModel:
            def __call__(self, batch):
                return batch.clone()

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("startrails.lib.finish.nox.load_nox_model", side_effect=[CudaOomModel(), CpuIdentityModel()]) as load,
        ):
            session = NoxSession(model_path=model_path, device="cuda")
            result = session.remove_stars(image, stride=256)

        self.assertEqual(load.call_count, 2)
        self.assertEqual(str(load.call_args_list[0].args[1]), "cuda")
        self.assertEqual(str(load.call_args_list[1].args[1]), "cpu")
        self.assertEqual(str(session.configured_device), "cuda")
        self.assertEqual(session.execution_device, "cpu")
        self.assertIn("out of memory", session.fallback_reason)
        np.testing.assert_allclose(result, image, atol=1e-5)

    def test_nox_session_propagates_non_allocation_execution_errors(self):
        model_path = self.root / "fake_nox.pt"
        model_path.write_bytes(b"dummy")
        image = np.full((256, 256, 3), 0.5, dtype=np.float32)

        class BrokenModel:
            def __call__(self, batch):
                raise RuntimeError("CUDA kernel launch failed: invalid argument")

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("startrails.lib.finish.nox.load_nox_model", return_value=BrokenModel()) as load,
        ):
            session = NoxSession(model_path=model_path, device="cuda")
            with self.assertRaisesRegex(RuntimeError, "invalid argument"):
                session.remove_stars(image, stride=256)

        self.assertEqual(load.call_count, 1)
        self.assertEqual(session.execution_device, "cuda")
        self.assertIsNone(session.fallback_reason)

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

    def test_remove_stars_operation_adapter(self):
        img = np.full((256, 256, 3), 0.4, dtype=np.float32)
        expected = np.full((256, 256, 3), 0.2, dtype=np.float32)
        mock_session = MagicMock()

        def fake_remove(image, *, stride, progress_bar=None, should_interrupt=None):
            if progress_bar is not None:
                progress_bar(2, 1, 1, False, {"desc": "Tile 1/2"})
                progress_bar(2, 1, 2, True, {"desc": "Tile 2/2"})
            return expected

        mock_session.remove_stars.side_effect = fake_remove

        op = RemoveStars()
        progress_records = []
        op.observers.append(lambda total, increment, count, done, data: progress_records.append(data))

        destination = self.root / "unmasked_starless.tif"
        starless, written = op.remove_stars(
            img,
            session=mock_session,
            stride=256,
            bit_depth=16,
            settings=FINISH_DEFAULTS,
            output_path=destination,
        )
        self.assertEqual(written, destination)
        self.assertTrue(destination.is_file())
        np.testing.assert_array_equal(starless, expected)
        self.assertTrue(any((d or {}).get("desc") == "Tile 1/2" for d in progress_records))

    def test_remove_stars_cancellation_preserves_previous_outputs(self):
        img = np.full((256, 256, 3), 0.4, dtype=np.float32)
        destination = self.root / "unmasked_starless.tif"
        destination.write_bytes(b"previous")
        op = RemoveStars()

        mock_session = MagicMock()

        def fake_remove(image, *, stride, progress_bar=None, should_interrupt=None):
            op.requestInterrupt()
            return np.zeros_like(image)

        mock_session.remove_stars.side_effect = fake_remove
        result = op.remove_stars(
            img,
            session=mock_session,
            stride=256,
            bit_depth=16,
            settings=FINISH_DEFAULTS,
            output_path=destination,
        )
        self.assertIsNone(result)
        self.assertEqual(destination.read_bytes(), b"previous")
        self.assertFalse(list(self.root.glob(".artifact-*")))

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

        # Missing Nox model reports unconfigured cleanly without raising
        with patch("startrails.workflow.finish.APPLICATION_DIR", self.root):
            status = wf.get_star_removal_status()
            self.assertFalse(status["configured"])
            self.assertFalse(status["model_ready"])
            self.assertIsNotNone(status["setup_error"])

        # Present Nox model matching pinned size reports configured
        fake_nox = self.root / "models" / NOX_MANIFEST.relative_path
        fake_nox.parent.mkdir(parents=True, exist_ok=True)
        with fake_nox.open("wb") as stream:
            stream.truncate(NOX_MANIFEST.size_bytes)
        with (
            patch("startrails.workflow.finish.APPLICATION_DIR", self.root),
            patch("startrails.workflow.finish.resolve_nox_device", return_value="cpu"),
        ):
            status_ready = wf.get_star_removal_status()
            self.assertTrue(status_ready["configured"])
            self.assertTrue(status_ready["model_ready"])
            self.assertEqual(status_ready["device"], "cpu")
            self.assertEqual(status_ready["version"], NOX_MANIFEST.version)

        # GraXpert status surfaces the resolved provider policy for diagnostics.
        policy = {"provider": "CUDAExecutionProvider", "device": "cuda", "verified": True}
        with patch("startrails.workflow.finish.resolve_graxpert_runtime_policy", return_value=policy):
            gx_status = wf.get_graxpert_status()
        self.assertEqual(gx_status["policy"], policy)
        self.assertEqual(gx_status["provider"], "CUDAExecutionProvider")
        self.assertEqual(gx_status["device"], "cuda")
        self.assertIn("model_ready", gx_status)

    def test_check_finish_models_writes_runtime_policy_and_runs_nox(self):
        from setup.check_finish_models import main as check_models_main

        with (
            patch(
                "setup.check_finish_models.check_graxpert",
                return_value={"selected_policy": {"provider": "CPUExecutionProvider", "device": "cpu"}},
            ),
            patch(
                "setup.check_finish_models.check_nox",
                return_value=(np.zeros((512, 512, 3), dtype=np.float32), {"version": "1.0.0"}),
            ) as mock_check_nox,
            patch(
                "sys.argv",
                [
                    "check_finish_models.py",
                    "--variant",
                    "cpu",
                    "--runtime-policy",
                    str(self.root / "policy.json"),
                ],
            ),
        ):
            check_models_main()

        mock_check_nox.assert_called_once()
        self.assertEqual(json.loads((self.root / "policy.json").read_text())["provider"], "CPUExecutionProvider")

    def test_ui_separate_stars_settings(self):
        from support import qt_app

        qt_app()
        widget = SeparateStarsSettings()
        self.addCleanup(widget.deleteLater)
        widget.show()

        # Unconfigured / missing model state
        widget.refresh_status({"configured": False, "model_ready": False, "setup_error": "Model missing"}, has_prerequisites=True)
        self.assertTrue(widget.unconfigured_box.isVisible())
        self.assertFalse(widget.configured_box.isVisible())
        self.assertFalse(widget.btn_separate.isEnabled())
        self.assertIn("Model missing", widget.lbl_unconf_msg.text())

        # Ready state
        status = {"configured": True, "model_ready": True, "version": "1.0.0", "device": "cpu"}
        widget.refresh_status(status, has_prerequisites=True)
        self.assertFalse(widget.unconfigured_box.isVisible())
        self.assertTrue(widget.configured_box.isVisible())
        self.assertTrue(widget.btn_separate.isEnabled())

        # Chroma postfilter toggle emits signal and updates getter
        toggled = []
        widget.chroma_postfilter_changed.connect(toggled.append)
        self.assertTrue(widget.get_chroma_postfilter())
        widget.check_chroma_postfilter.click()
        self.assertEqual(toggled, [False])
        self.assertFalse(widget.get_chroma_postfilter())
        widget.set_chroma_postfilter(True)
        self.assertTrue(widget.get_chroma_postfilter())
        self.assertEqual(toggled, [False])

        # Prerequisite missing disables separation button
        widget.refresh_status(status, has_prerequisites=False)
        self.assertFalse(widget.btn_separate.isEnabled())
        widget.close()


class TestFinishDependencyUI(QtTestCase):

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

if __name__ == "__main__":
    unittest.main()
