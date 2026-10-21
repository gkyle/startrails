"""Real image reductions, sidecar persistence, and source lookup without ML models."""

import json
from pathlib import Path
from support import IsolatedTestCase
from unittest.mock import patch
from types import SimpleNamespace

import cv2
import jsonpickle
import numpy as np

from startrails.app import App
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.util import Observable
from startrails.lib.source_map import locate_sources, output_sidecar, source_dtype, SourceMapError
from startrails.lib.source_map import _LookupImageCache
from startrails.op.stackImages import StackImages
from startrails.ui.project import Project


class SourceMapTests(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        self.folder = self.root
        self.files = []
        cache = patch("startrails.lib.source_map._lookup_images", _LookupImageCache())
        cache.start()
        self.addCleanup(cache.stop)

    def input(self, pixels, name=None):
        path = self.folder / (name or f"input-{len(self.files)}.tif")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.assertTrue(cv2.imwrite(str(path), pixels))
        file = InputFile(path.name, str(path))
        self.files.append(file)
        return file

    def stack(self, batch=2, **kwargs):
        output = OutputFile("stack.tif", str(self.folder / "stack.tif"), "Stacked")
        StackImages(False).stack(self.files, output, batchSize=batch, **kwargs)
        manifest = output_sidecar(output, "sourceMap")
        data = json.loads(manifest.read_text())
        owners = np.load(manifest.parent / data["array"], allow_pickle=False)
        return output, owners, data

    def app(self):
        app = App.__new__(App)
        app.project = Project(list(self.files), [], str(self.folder / "test.project.json"))
        app.stateFile = str(self.folder / "app.json")
        app.state = {}
        app.activeOperation = None
        app.gpuInfo = SimpleNamespace(get_gpu_present=lambda: False, getGpuPresent=lambda: False)
        return app

    def test_channel_winners_equal_stack_and_are_batch_order_independent(self):
        rng = np.random.default_rng(17)
        images = [rng.integers(0, 65535, (18, 24, 3), dtype=np.uint16) for _ in range(7)]
        # Explicit ties and no-contribution pixels.
        for image in images:
            image[0, 0] = 400
            image[0, 1] = 0
            self.input(image)
        expected = np.max(images, axis=0)
        ids = np.argmax(images, axis=0).astype(np.uint16)
        ids[expected == 0] = 65535
        for batch in (1, 3, 20):
            with (
                self.subTest(batch=batch),
                patch("startrails.op.stackImages.as_completed", side_effect=lambda futures: reversed(list(futures))),
            ):
                output, owners, _ = self.stack(batch=batch)
            np.testing.assert_array_equal(cv2.imread(output.path, -1), expected)
            np.testing.assert_array_equal(owners, ids)

    def test_masks_fade_and_black_pixels_match_preprocessed_inputs(self):
        first = self.input(np.full((12, 12, 3), 200, np.uint8))
        self.input(np.full((12, 12, 3), 70, np.uint8))
        first.streaksManualMasks = [np.array([[0, 0], [5, 0], [5, 5], [0, 5]])]
        output, owners, data = self.stack(applyMasks=True, fade=True, fadeGradient=[0.5, 1])
        self.assertEqual(owners[2, 2].tolist(), [1, 1, 1])
        self.assertEqual(owners[8, 8].tolist(), [0, 0, 0])
        self.assertEqual(cv2.imread(output.path)[8, 8].tolist(), [100, 100, 100])
        self.assertEqual(data["settings"]["fade_gradient"], [0.5, 1])
        # Future corrections do not rewrite the old stack's attribution.
        first.streaksManualMasks.clear()
        first.excludeFromStack = True
        self.assertIs(locate_sources(output, self.files[::-1], 8, 8).candidates[0], first)

    def test_project_reopens_without_decoding_any_input_for_lookup(self):
        self.input(np.zeros((16, 16, 3), np.uint8))
        pixels = np.zeros((16, 16, 3), np.uint8)
        pixels[8, :, :] = 200
        winner = self.input(pixels)
        app = self.app()
        output = app.doStack(False, lambda *args: None, useGPU=False)
        self.assertIsNotNone(output.sourceMap)
        app.toggleExcludeFromStack(winner)
        restored = self.app()
        restored.loadProject(app.project.projectFile)
        basis = restored.project.outputFiles[0]
        read = cv2.imread
        calls = []

        def record(path, *args, **kwargs):
            calls.append(path)
            return read(path, *args, **kwargs)

        with patch("startrails.lib.source_map.cv2.imread", side_effect=record):
            result = restored.locateSources(6, 8, basis)
        self.assertEqual(result.candidates[0].sourceId, winner.sourceId)
        self.assertTrue(result.candidates[0].excludeFromStack)
        self.assertEqual(calls, [str(Path(output.path).resolve())])

    def test_distinct_paths_and_ids_for_duplicate_basenames(self):
        self.input(np.full((4, 4, 3), 10, np.uint8), "one/image.tif")
        second = self.input(np.full((4, 4, 3), 200, np.uint8), "two/image.tif")
        output, _, _ = self.stack()
        self.assertIs(locate_sources(output, self.files, 1, 1).candidates[0], second)
        self.assertNotEqual(self.files[0].sourceId, second.sourceId)

    def test_repeated_lookup_reuses_image_and_still_checks_sources(self):
        first = self.input(np.full((16, 16, 3), 200, np.uint16))
        output, _, _ = self.stack()
        with patch("startrails.lib.source_map.cv2.imread", wraps=cv2.imread) as read:
            for x, y in ((1, 1), (8, 8), (15, 15)):
                self.assertEqual(locate_sources(output, self.files, x, y).candidates, [first])
            Path(first.path).unlink()
            self.assertFalse(locate_sources(output, self.files, 8, 8).candidates)
        self.assertEqual(read.call_count, 1)

    def test_cached_gap_mask_is_refreshed_when_replaced(self):
        self.input(np.full((16, 16, 3), 200, np.uint8))
        output, _, _ = self.stack()
        output.operation = "FillGaps"
        output.gapMask = "mask.tif"
        mask_path = self.folder / output.gapMask
        cv2.imwrite(str(mask_path), np.zeros((16, 16), np.uint8))
        with patch("startrails.lib.source_map.cv2.imread", wraps=cv2.imread) as read:
            for _ in range(2):
                result = locate_sources(output, self.files, 8, 8)
                self.assertEqual(result.candidates, self.files)
                self.assertNotIn("generated", result.message)
            self.assertEqual(read.call_count, 2)
            # Changing dimensions/channel count also guarantees a new file size.
            cv2.imwrite(str(mask_path), np.full((16, 16, 3), 255, np.uint16))
            result = locate_sources(output, self.files, 8, 8)
            self.assertFalse(result.candidates)
            self.assertIn("generated", result.message)
            self.assertEqual(read.call_count, 3)
            mask_path.unlink()
            with self.assertRaisesRegex(SourceMapError, "gap-fill mask"):
                locate_sources(output, self.files, 8, 8)

    def test_decoded_cache_evicts_images_to_stay_within_memory_budget(self):
        first = self.input(np.full((6, 6, 3), 20, np.uint8))
        second = self.input(np.full((6, 6, 3), 40, np.uint8))
        cache = _LookupImageCache(max_bytes=6 * 6 * 3)
        with patch("startrails.lib.source_map._lookup_images", cache):
            output, _, _ = self.stack()
            self.assertEqual(locate_sources(output, self.files, 2, 2).candidates, [second])
            # A different stack evicts the first; revisiting must safely reload it.
            other = OutputFile("other.tif", str(self.folder / "other.tif"), "Stacked")
            StackImages(False).stack([first], other)
            self.assertEqual(locate_sources(other, self.files, 2, 2).candidates, [first])
            with patch("startrails.lib.source_map.cv2.imread", wraps=cv2.imread) as read:
                self.assertEqual(locate_sources(output, self.files, 2, 2).candidates, [second])
                self.assertEqual(read.call_count, 1)

    def test_grayscale_and_no_source(self):
        self.input(np.zeros((6, 6), np.uint16))
        output, owners, _ = self.stack()
        self.assertTrue(np.all(owners == 65535))
        self.assertFalse(locate_sources(output, self.files, 2, 2).candidates)
        self.assertEqual(source_dtype(65535), np.uint16)
        self.assertEqual(source_dtype(65536), np.uint32)

    def test_invalid_clicks_and_legacy_output(self):
        self.input(np.full((6, 6, 3), 200, np.uint8))
        output, _, _ = self.stack()
        for point in ((-1, 0), (6, 0), (0, 6)):
            self.assertFalse(locate_sources(output, self.files, *point).candidates)
        output.sourceMap = None
        with self.assertRaisesRegex(SourceMapError, "Build a new stack"):
            locate_sources(output, self.files, 2, 2)
        # Old project records initialize the newly added attributes on load.
        del output.sourceMap
        restored = jsonpickle.decode(jsonpickle.encode(output))
        self.assertIsNone(restored.sourceMap)

    def test_cancelled_and_failed_stack_dont_publish_a_map(self):
        for i in range(8):
            self.input(np.full((6, 6, 3), i, np.uint8))
        output = OutputFile("cancel.tif", str(self.folder / "cancel.tif"), "Stacked")
        operation = StackImages(False)
        operation.addObserver(lambda total, increment, *args: operation.requestInterrupt() if increment else None)
        operation.stack(self.files, output, batchSize=2)
        self.assertIsNone(output.sourceMap)
        self.assertFalse(list(self.folder.glob("*.sources.*")))
        with patch("startrails.op.stackImages.cv2.imwrite", return_value=False):
            with self.assertRaises(OSError):
                StackImages(False).stack(self.files, output)
        self.assertIsNone(output.sourceMap)
        self.assertFalse(list(self.folder.glob("*.sources.*")))

    def test_missing_changed_sources_and_changed_stack(self):
        first = self.input(np.full((6, 6, 3), 200, np.uint8))
        output, _, _ = self.stack()
        result = locate_sources(output, [], 2, 2)
        self.assertFalse(result.candidates)
        self.assertIn("no longer in this project", result.message)
        Path(first.path).unlink()
        self.assertFalse(locate_sources(output, self.files, 2, 2).candidates)
        Path(output.path).write_bytes(b"replaced")
        with self.assertRaisesRegex(SourceMapError, "stacked image has changed"):
            locate_sources(output, self.files, 2, 2)

    def test_missing_or_corrupt_sidecar_is_actionable(self):
        self.input(np.full((6, 6, 3), 200, np.uint8))
        output, _, data = self.stack()
        array = output_sidecar(output, "sourceMap").parent / data["array"]
        array.write_bytes(b"not a numpy array")
        with self.assertRaisesRegex(SourceMapError, "sidecar"):
            locate_sources(output, self.files, 2, 2)
        array.unlink()
        with self.assertRaises(SourceMapError):
            locate_sources(output, self.files, 2, 2)

    def test_fill_output_links_original_map_and_excludes_generated_pixels(self):
        self.input(np.full((16, 16, 3), 90, np.uint8))
        app = self.app()
        basis = app.doStack(False, lambda *args: None, useGPU=False)
        mask = np.zeros((16, 16, 3), np.uint8)
        mask[7:10, 7:10] = 255

        class FakeFill(Observable):
            @staticmethod
            def suggestOutFileName(file, directory):
                return str(Path(directory) / "filled.tif"), str(Path(directory) / "gapmask.tif")

            def fillGaps(self, file, filled, output_mask):
                cv2.imwrite(filled.path, cv2.imread(file.path))
                cv2.imwrite(output_mask.path, mask)

            def shouldInterrupt(self):
                return False

        import startrails.app as app_module

        original = app_module.fgm
        try:
            app_module.fgm = SimpleNamespace(FillGaps=FakeFill)
            filled = app.doFillGaps(basis, lambda *args: None)
        finally:
            app_module.fgm = original
        self.assertEqual(output_sidecar(filled, "sourceMap"), output_sidecar(basis, "sourceMap"))
        result = app.locateSources(8, 8, filled)
        self.assertIn("generated by gap filling", result.message)
        self.assertEqual(result.candidates, self.files)
        restored = jsonpickle.decode(jsonpickle.encode(filled))
        self.assertEqual(locate_sources(restored, self.files, 2, 2).candidates, self.files)

    def test_repeated_stacks_do_not_overwrite_previous_maps(self):
        self.input(np.full((6, 6, 3), 200, np.uint8))
        app = self.app()
        first = app.doStack(False, lambda *args: None, useGPU=False)
        second = app.doStack(False, lambda *args: None, useGPU=False)
        self.assertNotEqual(first.path, second.path)
        self.assertNotEqual(first.sourceMap, second.sourceMap)
        self.assertEqual(app.locateSources(2, 2, first).candidates, self.files)
        self.assertEqual(app.locateSources(2, 2, second).candidates, self.files)
