"""Finish star separation workflow, cache freshness, and preview behavior."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import MagicMock, patch

import cv2
import jsonpickle
import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox

from startrails.lib.finish.defaults import (
    DEFAULT_STARNET_STRIDE,
    FINISH_EXT,
    ROLE_FINISHED_COMPOSITE,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
    ROLE_UNMASKED_STARLESS,
)
from startrails.lib.image_io import imread, imwrite
from startrails.lib.project_finish import FinishProject
from startrails.op.finish.recombine import Recombine
from startrails.op.finish.separate_stars import SeparateStars
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.views.finish import FinishView
from startrails.workflow.finish import SEPARATION_PROGRESS_TOTAL, FinishWorkflow
from support import QtTestCase

NON_DEFAULT_STRIDE = 128


class TestFinishSeparation(QtTestCase):
    def setUp(self):
        super().setUp()
        self.rng = np.random.default_rng(0)
        self.proj_path = self.root / f"test_separation{FINISH_EXT}"
        self.project = FinishProject(project_file=str(self.proj_path))
        self.app = self.make_app(self.project)
        self.workflow = FinishWorkflow(self.app)
        self.app.workflow = self.workflow
        self.enterContext(
            patch.object(
                self.workflow,
                "get_star_removal_status",
                return_value={"configured": True, "model_ready": True, "version": "1.0.0", "device": "cpu"},
            )
        )

    def create_synthetic_image(
        self,
        name: str,
        bit_depth: int = 16,
        shape: tuple[int, int] = (512, 512),
    ) -> Path:
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        dtype = np.uint8 if bit_depth == 8 else np.uint16
        low, high = (20, 240) if bit_depth == 8 else (5000, 60000)
        pixels = self.rng.integers(low, high, (*shape, 3), dtype=dtype)
        imwrite(target, pixels, convertBGR=False, bit_depth=bit_depth)
        return target

    @staticmethod
    def create_gradient_mask(shape: tuple[int, int] = (512, 512)) -> np.ndarray:
        height, width = shape
        mask = np.zeros((height, width), dtype=np.float32)
        # Top half is sky, a soft band follows, and the bottom half is foreground.
        mask[: height // 2, :] = 1.0
        mask[height // 2 : height // 2 + 10, :] = 0.5
        return mask

    @staticmethod
    def make_fake_nox_session(scale: float = 0.8, *, constant_value: float | None = None, strides: list[int] | None = None):
        session = MagicMock()

        def fake_remove_stars(image, *, stride, progress_bar=None, should_interrupt=None):
            if strides is not None:
                strides.append(stride)
            if progress_bar is not None:
                progress_bar(2, 1, 1, False, {"desc": "Separating stars tile 1/2..."})
                progress_bar(2, 1, 2, True, {"desc": "Separating stars tile 2/2..."})
            if constant_value is not None:
                return np.full_like(image, constant_value, dtype=np.float32)
            return (image * scale).astype(np.float32)

        session.remove_stars.side_effect = fake_remove_stars
        return session

    def test_end_to_end_separation_export_and_reopen(self):
        """Import, mask, separate, composite, export, and reopen persist one result."""
        source_path = self.create_synthetic_image("night_sky.tif")
        self.workflow.do_import_source(source_path)
        self.workflow.save_mask(self.create_gradient_mask())

        session = self.make_fake_nox_session(0.8)
        with patch.object(self.workflow, "_nox_session_for", return_value=session):
            result = self.workflow.do_separate_stars(chroma_postfilter=False)

        self.assertIsNotNone(result)
        starless_out, stars_out = result
        self.assertTrue(Path(starless_out.path).is_file())
        self.assertTrue(Path(stars_out.path).is_file())
        # Separation publishes only Starless and Stars; recombination is deferred until needed.
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))

        operations = [record.operation for record in self.workflow.get_output_file_list()]
        self.assertIn("Starless", operations)
        self.assertIn("Stars", operations)
        self.assertNotIn("Composite", operations)
        self.assertIsNotNone(self.project.separation_signature)
        self.assertFalse(self.project.chroma_postfilter)

        self.assertIsNotNone(self.workflow.do_recombine())
        composite_path = self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        self.assertIsNotNone(composite_path)
        self.assertTrue(composite_path.is_file())

        source = imread(source_path, to_rgb=True, as_float=True)
        composite = imread(composite_path, to_rgb=True, as_float=True)
        foreground = slice(256 + 20, 512)
        # Neutral recombination restores the source, including untouched foreground.
        np.testing.assert_array_equal(composite[foreground], source[foreground])
        self.assertLessEqual(float(np.max(np.abs(composite - source))), 2.0 / 65535.0)

        export_file = self.workflow.do_export_composite()
        self.assertTrue(export_file.is_file())
        exported = cv2.imread(str(export_file), cv2.IMREAD_UNCHANGED)
        self.assertEqual(exported.dtype, np.uint16)

        reopened = jsonpickle.decode(self.proj_path.read_text(encoding="utf-8"))
        self.assertIsInstance(reopened, FinishProject)
        self.assertTrue(reopened.source_is_current())
        self.assertIsNotNone(reopened.current_artifact_path(ROLE_SEPARATED_STARLESS))
        self.assertIsNotNone(reopened.current_artifact_path(ROLE_SEPARATED_STARS))
        self.assertIsNotNone(reopened.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertEqual(reopened.separation_signature, self.project.separation_signature)
        self.assertFalse(reopened.chroma_postfilter)

    def test_cache_reuses_unmasked_plate_across_masks_and_postfilter_but_tracks_stride_and_source(self):
        """Mask edits and chroma postfilter toggles reuse the Nox unmasked plate; stride/source rebuild it."""
        source1 = self.create_synthetic_image("source1.tif")
        self.workflow.do_import_source(source1)
        self.workflow.save_mask(self.create_gradient_mask())

        strides: list[int] = []
        session = self.make_fake_nox_session(0.8, strides=strides)

        with patch.object(self.workflow, "_nox_session_for", return_value=session):
            self.assertIsNotNone(self.workflow.do_separate_stars(chroma_postfilter=True))
            self.assertEqual(strides, [DEFAULT_STARNET_STRIDE])
            sig_with_postfilter = self.project.separation_signature

            # Toggling chroma_postfilter reuses ROLE_UNMASKED_STARLESS and updates signature.
            self.assertIsNotNone(self.workflow.do_separate_stars(chroma_postfilter=False))
            self.assertEqual(strides, [DEFAULT_STARNET_STRIDE])
            self.assertNotEqual(self.project.separation_signature, sig_with_postfilter)
            self.assertFalse(self.project.chroma_postfilter)

            # A new mask invalidates separated layers but keeps the unmasked plate.
            self.workflow.save_mask(np.ones((512, 512), dtype=np.float32))
            self.assertIsNone(self.project.current_artifact_path(ROLE_SEPARATED_STARLESS))
            self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
            self.assertIsNotNone(self.project.current_artifact_path(ROLE_UNMASKED_STARLESS))

            progress = []

            def record(total, increment, count, done, data=None):
                progress.append((total, increment, count))

            self.assertIsNotNone(self.workflow.do_separate_stars(chroma_postfilter=False, progress_bar=record))
            self.assertEqual(strides, [DEFAULT_STARNET_STRIDE])
            self.assertEqual({total for total, _, _ in progress}, {SEPARATION_PROGRESS_TOTAL})
            self.assertEqual(
                sum(increment for _, increment, _ in progress),
                SEPARATION_PROGRESS_TOTAL,
            )
            self.assertEqual(progress[-1][2], SEPARATION_PROGRESS_TOTAL)

            # The project-owned nondefault stride is forwarded and invalidates the unmasked cache.
            self.project.update_settings(replace(self.project.get_settings(), starnet_stride=NON_DEFAULT_STRIDE))
            self.assertIsNotNone(self.workflow.do_separate_stars())
            self.assertEqual(strides, [DEFAULT_STARNET_STRIDE, NON_DEFAULT_STRIDE])

            # Replacing the source also invalidates the unmasked plate.
            source2 = self.create_synthetic_image("source2.tif")
            self.workflow.do_replace_source(source2)
            self.workflow.do_all_sky_mask()
            self.assertIsNotNone(self.workflow.do_separate_stars())
            self.assertEqual(strides, [DEFAULT_STARNET_STRIDE, NON_DEFAULT_STRIDE, NON_DEFAULT_STRIDE])

    def test_arbitrary_dimensions_supported_by_nox_tiling(self):
        small_source = self.create_synthetic_image("small.tif", shape=(400, 400))
        self.workflow.do_import_source(small_source)
        self.workflow.do_all_sky_mask()

        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)):
            self.assertIsNotNone(self.workflow.do_separate_stars())

    def test_feathering_changes_separation_and_survives_reopening(self):
        source_path = self.root / "feather_source.tif"
        imwrite(source_path, np.full((512, 512, 3), 40000, dtype=np.uint16), bit_depth=16)
        self.workflow.do_import_source(source_path)
        mask = np.zeros((512, 512), dtype=np.float32)
        mask[:256] = 1.0
        mask_path = self.workflow.save_mask(mask)
        canonical_bytes = mask_path.read_bytes()

        session = self.make_fake_nox_session(constant_value=20000.0 / 65535.0)
        with (
            patch.object(self.workflow, "_nox_session_for", return_value=session),
            patch.object(FinishWorkflow, "get_star_removal_status", return_value={"configured": True, "model_ready": True}),
        ):
            self.assertIsNotNone(self.workflow.do_separate_stars(chroma_postfilter=False))
            original_signature = self.project.separation_signature
            self.project.update_settings(replace(self.project.get_settings(), mask_feather_radius_px=2.5))
            self.assertIsNotNone(self.workflow.do_separate_stars(chroma_postfilter=False))
            self.assertEqual(session.remove_stars.call_count, 1)

            feathered = imread(self.project.current_artifact_path(ROLE_SEPARATED_STARLESS), as_float=False)
            self.assertTrue(np.all(feathered[:250] == 20000))
            self.assertTrue(np.all(feathered[260:] == 40000))
            self.assertTrue(np.all((feathered[255:257] > 20000) & (feathered[255:257] < 40000)))
            self.assertNotEqual(self.project.separation_signature, original_signature)
            self.assertEqual(mask_path.read_bytes(), canonical_bytes)
            np.testing.assert_array_equal(self.workflow.get_current_mask(), mask)

            reopened = jsonpickle.decode(self.proj_path.read_text(encoding="utf-8"))
            self.app.project = reopened
            workflow = FinishWorkflow(self.app)
            self.assertEqual(reopened.mask_feather_radius_px, 2.5)
            self.assertFalse(workflow.invalidate_if_separation_changed())
            np.testing.assert_array_equal(
                imread(reopened.current_artifact_path(ROLE_SEPARATED_STARLESS), as_float=False), feathered
            )
            # Revalidation checks the effective setting even if a caller bypasses update_settings.
            reopened.mask_feather_radius_px = 0.0
            self.assertTrue(workflow.invalidate_if_separation_changed())
            self.assertIsNone(reopened.current_artifact_path(ROLE_SEPARATED_STARLESS))

    def test_cancelled_or_stale_separation_does_not_replace_published_results(self):
        source_path = self.create_synthetic_image("cancel_test.tif")
        self.workflow.do_import_source(source_path)
        self.workflow.do_all_sky_mask()

        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)):
            self.assertIsNotNone(self.workflow.do_separate_stars())

        published = {}
        published_paths = {}
        roles = (ROLE_SEPARATED_STARLESS, ROLE_SEPARATED_STARS)
        for role in roles:
            path = self.project.current_artifact_path(role)
            self.assertIsNotNone(path)
            published_paths[role] = path
            published[role] = path.read_bytes()

        cancellation_requested = []
        original_new_operation = FinishWorkflow._new_operation

        def new_operation(workflow, operation_type, *args, **kwargs):
            operation = original_new_operation(workflow, operation_type, *args, **kwargs)
            if operation_type is SeparateStars:

                def interrupt_after_starless_stage(total, increment, count, done, data=None):
                    if isinstance(data, dict) and data.get("desc") == "Starless image staged.":
                        cancellation_requested.append(True)
                        operation.requestInterrupt()

                operation.addObserver(interrupt_after_starless_stage)
            return operation

        with patch.object(FinishWorkflow, "_new_operation", new=new_operation):
            self.assertIsNone(self.workflow.do_separate_stars())

        self.assertEqual(cancellation_requested, [True])
        for role, content in published.items():
            self.assertIsNotNone(self.project.current_artifact_path(role))
            self.assertEqual(published_paths[role].read_bytes(), content)

        original_separate = SeparateStars.separate

        def separate_then_edit_mask(operation, source, model, mask, **kwargs):
            result = original_separate(operation, source, model, mask, **kwargs)
            # A mask save lands after the staged layer commit but before publication.
            self.workflow.save_mask(np.zeros(mask.shape, dtype=np.float32))
            return result

        with patch.object(SeparateStars, "separate", new=separate_then_edit_mask):
            self.assertIsNone(self.workflow.do_separate_stars())

        for role in roles:
            self.assertIsNone(self.project.current_artifact_path(role))
            # Invalidation clears records, but the previously published bytes stay intact.
            self.assertEqual(published_paths[role].read_bytes(), published[role])

    def test_separation_skips_recombine(self):
        source_path = self.create_synthetic_image("skip_recombine.tif")
        self.workflow.do_import_source(source_path)
        self.workflow.do_all_sky_mask()

        with (
            patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)),
            patch.object(Recombine, "recombine", side_effect=AssertionError("Recombine should not run during separation")),
        ):
            result = self.workflow.do_separate_stars(chroma_postfilter=False)

        self.assertIsNotNone(result)
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))

    def test_progress_reports_all_phases_on_shared_scale(self):
        source_path = self.create_synthetic_image("progress.tif")
        self.workflow.do_import_source(source_path)
        self.workflow.do_all_sky_mask()
        events = []

        def record(total, increment, count, done, data=None):
            desc = data.get("desc") if isinstance(data, dict) else None
            events.append((total, increment, count, desc))

        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)):
            result = self.workflow.do_separate_stars(chroma_postfilter=True, progress_bar=record)

        self.assertIsNotNone(result)
        self.assertEqual({total for total, _, _, _ in events}, {SEPARATION_PROGRESS_TOTAL})
        self.assertEqual(sum(increment for _, increment, _, _ in events), SEPARATION_PROGRESS_TOTAL)
        counts = [count for _, _, count, _ in events]
        self.assertEqual(counts, sorted(counts))
        self.assertEqual(counts[-1], SEPARATION_PROGRESS_TOTAL)
        descs = [desc for _, _, _, desc in events if desc]
        self.assertTrue(any("Loading source image" in d for d in descs))
        self.assertTrue(any("Removing stars" in d for d in descs))
        self.assertTrue(any("chroma post-filter" in d.lower() for d in descs))
        self.assertTrue(any("Calculating starless image" in d for d in descs))
        self.assertTrue(any("Calculating stars image" in d for d in descs))

        # Cached unmasked starless with chroma postfilter disabled also reaches total=100 cleanly.
        cached_events = []
        self.workflow.do_all_sky_mask()
        with patch.object(self.workflow, "_nox_session_for", side_effect=AssertionError("Should use cache")):
            result = self.workflow.do_separate_stars(
                chroma_postfilter=False,
                progress_bar=lambda total, inc, count, done, data=None: cached_events.append((total, inc, count)),
            )
        self.assertIsNotNone(result)
        self.assertEqual(sum(inc for _, inc, _ in cached_events), SEPARATION_PROGRESS_TOTAL)
        self.assertEqual(cached_events[-1][2], SEPARATION_PROGRESS_TOTAL)

    def test_ui_file_sections_selection_and_view_preservation(self):
        source_path = self.create_synthetic_image("ui_test.tif")
        self.workflow.do_import_source(source_path)
        self.workflow.do_all_sky_mask()

        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)):
            self.assertIsNotNone(self.workflow.do_separate_stars(chroma_postfilter=False))

        canvas = CanvasLabel()
        canvas.resize(600, 600)
        self.addCleanup(canvas.deleteLater)

        class Shell(QObject):
            def __init__(self):
                super().__init__()
                self.canvas_main = canvas
                self.progressBar = None
                self.label_progressBar = None

            def enqueue_task(self, task_id, title, total, desc, work):
                work()
                return True

            def doCreateNewFinishProject(self):
                pass

            def doOpenFinishProject(self):
                pass

        shell = Shell()
        self.addCleanup(shell.deleteLater)
        view = FinishView(self.app, shell)
        self.addCleanup(view.teardown)
        sidebar = view.build_sidebar(None)
        view.bind()
        view.resetProjectView()

        inputs = sidebar.inputFiles
        outputs = sidebar.outputFiles
        sep_settings = sidebar.separateSettings
        self.assertTrue(sep_settings.btn_separate.isEnabled())
        self.assertEqual(len(inputs.model.files), 1)
        self.assertEqual(Path(inputs.model.files[0].path), Path(source_path).resolve())
        operations = [f.operation for f in outputs.model.files]
        self.assertIn("Starless", operations)
        self.assertIn("Stars", operations)
        self.assertNotIn("Composite", operations)
        self.assertNotIn("Original", operations)

        def select(section, file):
            index = section.model.index_for_file(file)
            self.assertTrue(index.isValid())
            section.focus_file(file)
            section.ui.files.clicked.emit(index)

        canvas.zoom_factor = 2.5
        canvas.posX = 50
        canvas.posY = -30

        source_entry = inputs.model.files[0]
        starless_entry = next(f for f in outputs.model.files if f.operation == "Starless")
        stars_entry = next(f for f in outputs.model.files if f.operation == "Stars")

        select(inputs, source_entry)
        self.assertEqual(Path(canvas.file.path), Path(source_path).resolve())
        self.assertAlmostEqual(canvas.zoom_factor, 2.5)
        self.assertEqual((canvas.posX, canvas.posY), (50, -30))

        select(outputs, starless_entry)
        self.assertEqual(Path(canvas.file.path), Path(starless_entry.path))
        self.assertAlmostEqual(canvas.zoom_factor, 2.5)
        self.assertEqual((canvas.posX, canvas.posY), (50, -30))

        select(outputs, stars_entry)
        self.assertEqual(Path(canvas.file.path), Path(stars_entry.path))
        self.assertAlmostEqual(canvas.zoom_factor, 2.5)
        self.assertEqual((canvas.posX, canvas.posY), (50, -30))

        select(outputs, starless_entry)
        self.assertEqual(Path(canvas.file.path), Path(starless_entry.path))

        # Default zoom is the state a project reset would clear; keep a panned transform.
        canvas.zoom_factor = 1.0
        canvas.posX = 50
        canvas.posY = -30

        # Toggling chroma postfilter in UI updates the project setting, and re-running
        # from the Starless selection preserves the view transform.
        self.assertFalse(sep_settings.get_chroma_postfilter())
        sep_settings.check_chroma_postfilter.click()
        self.assertTrue(self.project.chroma_postfilter)
        previous_display_file = canvas.file
        with patch.object(self.workflow, "_nox_session_for", return_value=self.make_fake_nox_session(0.8)):
            sep_settings.btn_separate.click()
            self.qt.processEvents()

        refreshed_starless = self.project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        self.assertIsNotNone(refreshed_starless)
        self.assertIsNot(canvas.file, previous_display_file)
        self.assertEqual(Path(canvas.file.path), Path(refreshed_starless))
        self.assertAlmostEqual(canvas.zoom_factor, 1.0)
        self.assertEqual((canvas.posX, canvas.posY), (50, -30))

        retained = {
            "source": Path(source_path),
            "mask": Path(self.project.artifact_path(ROLE_SKY_MASK)),
            "starless": Path(self.project.artifact_path(ROLE_SEPARATED_STARLESS)),
            "stars": Path(self.project.artifact_path(ROLE_SEPARATED_STARS)),
        }
        self.assertTrue(all(path.is_file() for path in retained.values()))
        retained_bytes = {name: path.read_bytes() for name, path in retained.items()}

        current_source = inputs.model.files[0]
        with patch(
            "startrails.ui.views.finish.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ):
            inputs.removeFile.emit(current_source)

        self.assertIsNone(self.project.source_file)
        self.assertIsNone(self.project.current_artifact_path(ROLE_SKY_MASK))
        self.assertIsNone(self.project.current_artifact_path(ROLE_SEPARATED_STARLESS))
        self.assertIsNone(self.project.current_artifact_path(ROLE_SEPARATED_STARS))
        self.assertIsNone(self.project.current_artifact_path(ROLE_FINISHED_COMPOSITE))
        self.assertEqual(inputs.model.files, [])
        self.assertEqual(outputs.model.files, [])
        self.assertIsNone(canvas.file)
        for name, path in retained.items():
            self.assertTrue(path.is_file(), name)
            self.assertEqual(path.read_bytes(), retained_bytes[name], name)

        # Add then replace through the shared input section keeps exactly one input.
        replacement = self.create_synthetic_image("ui_replacement.tif")
        with patch(
            "startrails.ui.views.finish.QFileDialog.getOpenFileName",
            return_value=(str(source_path), ""),
        ):
            inputs.addRequested.emit()
        self.assertEqual(len(inputs.model.files), 1)
        self.assertEqual(Path(inputs.model.files[0].path), Path(source_path).resolve())
        self.assertEqual(outputs.model.files, [])
        self.assertEqual(Path(canvas.file.path), Path(source_path).resolve())

        with patch(
            "startrails.ui.views.finish.QFileDialog.getOpenFileName",
            return_value=(str(replacement), ""),
        ):
            inputs.addRequested.emit()
        self.assertEqual(len(inputs.model.files), 1)
        self.assertEqual(Path(inputs.model.files[0].path), Path(replacement).resolve())
        self.assertEqual(Path(self.project.source_file.path), Path(replacement).resolve())
        self.assertEqual(outputs.model.files, [])
        self.assertEqual(Path(canvas.file.path), Path(replacement).resolve())
