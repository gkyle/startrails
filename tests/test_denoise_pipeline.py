"""Real image staging, shared calibration, cancellation, and export contracts."""

from concurrent.futures import CancelledError
from unittest.mock import patch

import numpy as np
from PIL import Image

from support import IsolatedTestCase
from startrails.lib.artifacts import ArtifactTransaction
from startrails.lib.denoise.calibration.dark import DarkCalibrator
from startrails.lib.denoise.mask import MaskHandler
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_denoise import DenoiseProject
from startrails.op.denoise.align_stars import AlignStars
from startrails.op.denoise.compose_horizon import ComposeHorizon
from startrails.op.denoise.pipeline import DenoisePipeline
from startrails.op.denoise.stack_denoise import StackDenoise


class DenoisePipelineTests(IsolatedTestCase):
    def test_colliding_project_outputs_preserve_existing_intermediates(self):
        frame = np.full((12, 15, 3), 0.25, np.float32)
        mask = np.ones(frame.shape[:2], np.float32)
        for name in ("sky_stack", "ground_stack", "base_composite"):
            with self.subTest(project=name):
                project = DenoiseProject(str(self.root / f"{name}.proj_denoise"), use_gpu=False)
                config = project.to_denoise_config()
                output_dir = config.output_path.parent
                output_dir.mkdir()
                previous = {}
                for artifact in ("sky_stack.tif", "ground_stack.tif", "base_composite.tif"):
                    destination = output_dir / artifact
                    previous[destination] = artifact.encode("ascii")
                    destination.write_bytes(previous[destination])
                with self.assertRaisesRegex(ValueError, "paths must be distinct"):
                    StackDenoise().stack(config, [frame], [mask], [frame], mask)
                for destination, contents in previous.items():
                    self.assertEqual(destination.read_bytes(), contents)
                self.assertFalse(list(output_dir.glob(".artifact-*")))

    def test_streamed_pipeline_calibrates_once_preserves_fractions_and_completes_after_publication(self):
        shape = (12, 15, 3)
        paths = [
            imwrite(self.root / f"light{i}.tif", np.full(shape, value, np.uint16))
            for i, value in enumerate((3000, 5000))
        ]
        darks = [
            imwrite(self.root / f"dark{i}.tif", np.full(shape, value, np.uint16))
            for i, value in enumerate((1000, 1001))
        ]
        config = DenoiseProject(
            star_images=paths,
            base_image=paths[0],
            noise_images=darks,
            output_path=self.root / "out.tif",
            homographies={paths[1]: np.eye(2, 3, dtype=np.float32)},
            mask_array=np.ones(shape[:2]),
            taper_mask_edges=False,
            use_gpu=False,
            stack_method="mean",
            enable_horizon_corrections=False,
        )
        pipeline = DenoisePipeline(config)
        progress = []

        def report(total, increment, count, done, data):
            progress.append(count)
            if done:
                self.assertTrue(config.output_path.is_file())
                self.assertTrue((self.root / "base_composite.tif").is_file())

        pipeline.addObserver(report)
        with (
            patch.object(AlignStars, "prepare_calibrator", wraps=AlignStars.prepare_calibrator) as prepare,
            patch.object(
                DarkCalibrator, "compute_master_dark_from_paths", wraps=DarkCalibrator.compute_master_dark_from_paths
            ) as integrate,
        ):
            output = pipeline.run()
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(integrate.call_count, 1)
        expected = (4000 - 1000.5) / 65535
        np.testing.assert_allclose(pipeline.last_compositor.ground_stack, expected, atol=1e-7, rtol=0)
        np.testing.assert_allclose(imread(output, as_float=True), expected, atol=0.5 / 65535 + 1e-7, rtol=0)
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 100)
        self.assertFalse(list(self.root.rglob("*.raw")))

    def test_streaming_excludes_failed_alignment_from_sky_but_keeps_ground(self):
        shape = (12, 15, 3)
        paths = [
            imwrite(self.root / f"light{i}.tif", np.full(shape, value, np.uint16))
            for i, value in enumerate((1000, 5000))
        ]
        config = DenoiseProject(
            star_images=paths,
            base_image=paths[0],
            output_path=self.root / "out.tif",
            mask_array=np.ones(shape[:2]),
            taper_mask_edges=False,
            use_gpu=False,
            stack_method="mean",
        )
        with self.assertLogs("startrails.op.denoise.align_stars", level="WARNING"):
            compositor, _ = DenoisePipeline(config).stack_base_frames()
        np.testing.assert_allclose(compositor.sky_stack, 1000 / 65535, atol=1e-7, rtol=0)
        np.testing.assert_allclose(compositor.ground_stack, 3000 / 65535, atol=1e-7, rtol=0)

    def test_cancel_before_composition_preserves_previous_files_and_cleans_staging(self):
        image = imwrite(self.root / "source.tif", np.full((12, 15, 3), 0.25, np.float32))
        destination = self.root / "out.tif"
        destination.write_bytes(b"previous final")
        sky = self.root / "sky_stack.tif"
        sky.write_bytes(b"previous sky")
        config = DenoiseProject(star_images=[image], output_path=destination, sky_stack_path=sky, use_gpu=False)
        pipeline = DenoisePipeline(config)
        pipeline.addObserver(lambda total, inc, count, done, data: pipeline.requestInterrupt() if count >= 90 else None)
        with self.assertRaises(CancelledError):
            pipeline.run()
        self.assertEqual(destination.read_bytes(), b"previous final")
        self.assertEqual(sky.read_bytes(), b"previous sky")
        self.assertFalse((self.root / "base_composite.tif").exists())
        self.assertFalse(list(self.root.rglob("*.raw")))
        self.assertFalse(list(self.root.rglob(".artifact-*")))

    def test_base_and_tuned_exports_are_independent_and_gradient_uses_compositor_mask(self):
        sky = np.full((12, 15, 3), [0.7, 0.5, 0.3], np.float32)
        ground = np.full_like(sky, [0.1, 0.2, 0.3])
        mask = np.ones(sky.shape[:2], np.float32)
        coverages = [mask.copy(), mask.copy()]
        coverages[1][:, :5] = 0
        for suffix, compressed, format_name in ((".tif", True, "TIFF"), (".jpg", False, "JPEG")):
            with self.subTest(suffix=suffix):
                folder = self.root / format_name
                folder.mkdir()
                config = DenoiseProject(
                    output_path=folder / ("out" + suffix),
                    use_gpu=False,
                    mask_array=np.zeros_like(mask),
                    compress_intermediate_tiffs=compressed,
                    horizon_blend_percent=100,
                    denoise_horizon_band=False,
                    horizon_blur_radius=0,
                )
                with ArtifactTransaction() as transaction:
                    compositor = StackDenoise().stack(
                        config,
                        [sky.copy(), sky.copy()],
                        [c.copy() for c in coverages],
                        [ground.copy(), ground.copy()],
                        mask,
                        artifacts=transaction,
                    )
                    expected_base = compositor.base_composite.copy()
                    tuned, output = ComposeHorizon().compose(
                        compositor, config, write_output=True, artifacts=transaction
                    )
                    self.assertGreater(float(np.max(np.abs(tuned - expected_base))), 0.05)
                    transaction.commit()
                np.testing.assert_allclose(
                    imread(folder / "base_composite.tif", to_rgb=True, as_float=True),
                    expected_base,
                    atol=0.5 / 65535 + 1e-7,
                    rtol=0,
                )
                with Image.open(output) as image:
                    self.assertEqual(image.format, format_name)
                # PNG mask uses truncating 8-bit quantization.
                np.testing.assert_allclose(
                    MaskHandler.load_mask(config.gradient_mask_path), compositor.gradient_mask, atol=1 / 255, rtol=0
                )
