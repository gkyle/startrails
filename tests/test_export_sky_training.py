"""Tests for sky mask training data export, downscaling, and contribution pipeline."""

from pathlib import Path
import tempfile
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox, QWidget

from support import QtTestCase, qt_app
from startrails.lib.file import DenoiseInputFile
from startrails.lib.project_denoise import DenoiseProject
from startrails.op.denoise.export_sky_training import ExportSkyTraining
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.sidebar_denoise import SidebarDenoise
from startrails.ui.views.denoise import DenoiseView


class ExportSkyTrainingTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()

    def test_export_downscales_dimensions_by_half_and_converts_to_8bit(self):
        """Verify image and mask are halved in dimensions and converted to 8-bit."""
        # Create a test 16-bit TIFF image (400x300)
        h, w = 300, 400
        img_16 = np.full((h, w, 3), 32768, dtype=np.uint16)
        # Add contrast patterns
        img_16[:150, :, :] = 60000
        img_path = self.dir_path / "ref_16bit.tif"
        cv2.imwrite(str(img_path), img_16)

        # Create float32 mask (1.0 = sky top half, 0.0 = ground bottom half)
        mask = np.zeros((h, w), dtype=np.float32)
        mask[:150, :] = 1.0

        out_dir = self.dir_path / "exported"
        exporter = ExportSkyTraining()
        img_out, mask_out = exporter.export(img_path, mask, out_dir)

        self.assertTrue(img_out.exists())
        self.assertTrue(mask_out.exists())
        self.assertEqual(img_out.name, "image.jpg")
        self.assertEqual(mask_out.name, "mask.png")

        # Verify downscaled image dimensions and uint8 depth
        exported_img = cv2.imread(str(img_out))
        self.assertEqual(exported_img.dtype, np.uint8)
        self.assertEqual(exported_img.shape, (150, 200, 3))

        # Verify downscaled mask dimensions and binary {0, 255} uint8 values
        exported_mask = cv2.imread(str(mask_out), cv2.IMREAD_GRAYSCALE)
        self.assertEqual(exported_mask.dtype, np.uint8)
        self.assertEqual(exported_mask.shape, (150, 200))
        unique_vals = set(np.unique(exported_mask))
        self.assertTrue(unique_vals.issubset({0, 255}))
        # Top quarter should be sky (255), bottom quarter should be ground (0)
        self.assertEqual(exported_mask[30, 100], 255)
        self.assertEqual(exported_mask[120, 100], 0)

    def test_export_odd_dimensions(self):
        """Verify odd dimensions downscale identically for image and mask."""
        h, w = 301, 501
        img_8 = np.full((h, w, 3), 128, dtype=np.uint8)
        img_path = self.dir_path / "odd.jpg"
        cv2.imwrite(str(img_path), img_8)

        mask = np.ones((h, w), dtype=np.uint8) * 255
        out_dir = self.dir_path / "odd_out"
        exporter = ExportSkyTraining()
        img_out, mask_out = exporter.export(img_path, mask, out_dir)

        exported_img = cv2.imread(str(img_out))
        exported_mask = cv2.imread(str(mask_out), cv2.IMREAD_GRAYSCALE)

        expected_shape = (h // 2, w // 2)
        self.assertEqual(exported_img.shape[:2], expected_shape)
        self.assertEqual(exported_mask.shape, expected_shape)

    def test_workflow_do_export_and_contribute_training_sky(self):
        """Verify DenoiseWorkflow export and contribution packaging with sky_segmentation."""
        h, w = 200, 200
        ref_path = self.dir_path / "ref.jpg"
        cv2.imwrite(str(ref_path), np.full((h, w, 3), 100, dtype=np.uint8))

        mask = np.zeros((h, w), dtype=np.float32)
        mask[:100, :] = 1.0

        project = DenoiseProject(str(self.dir_path / "test.proj_denoise"))
        ref_file = DenoiseInputFile(basename=ref_path.name, path=str(ref_path))
        project.reference_file = ref_file
        project.star_files = [ref_file]
        app = self.make_app(project)

        # Test export
        export_target = self.dir_path / "workflow_export"
        img_out, mask_out = app.workflow.doExportTrainingSky(
            str(export_target),
            mask=mask,
        )
        self.assertTrue(img_out.exists())
        self.assertTrue(mask_out.exists())

        # Test contribute
        mock_client = MagicMock()
        mock_client.submit_bundle.return_value = {
            "status": "accepted",
            "submission_id": "test-sky-id-123",
            "file_count": 2,
            "size_bytes": 1024,
        }

        receipt = app.workflow.doContributeTrainingSky(
            user_email="sky@example.com",
            user_comments="Mountain horizon correction",
            client=mock_client,
            mask=mask,
        )
        self.assertEqual(receipt["submission_id"], "test-sky-id-123")
        mock_client.submit_bundle.assert_called_once()
        _, kwargs = mock_client.submit_bundle.call_args
        self.assertEqual(kwargs["training_set"], "sky_segmentation")
        self.assertEqual(kwargs["user_email"], "sky@example.com")
        self.assertEqual(kwargs["user_comments"], "Mountain horizon correction")


class DenoiseViewTrainingUITests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.project = DenoiseProject(str(self.root / "denoise_test.proj_denoise"))
        self.app = self.make_app(self.project)
        self.shell = QObject()
        self.shell.canvas_main = CanvasLabel()
        self.shell.enqueue_task = lambda task_id, title, total, desc, run: run()
        self.addCleanup(self.shell.deleteLater)
        self.view = DenoiseView(self.app, self.shell)
        self.sidebar = SidebarDenoise(app=self.app)
        self.addCleanup(self.sidebar.deleteLater)
        self.view.sidebar = self.sidebar
        self.view.bind()
        self.addCleanup(self.view.teardown)

    def test_corrections_buttons_enable_only_after_manual_brush_edits(self):
        """Verify buttons are disabled until user paints with brush, and disabled again on auto-detect."""
        sky_ui = self.sidebar.skySettings.ui

        # Initially disabled
        self.assertFalse(self.view.has_manual_sky_corrections)
        self.assertFalse(sky_ui.contribute.isEnabled())
        self.assertFalse(sky_ui.training.isEnabled())

        # Emitting canvas mask_brush_edited enables buttons
        self.shell.canvas_main.mask_brush_edited.emit()
        qt_app().processEvents()

        self.assertTrue(self.view.has_manual_sky_corrections)
        self.assertTrue(sky_ui.contribute.isEnabled())
        self.assertTrue(sky_ui.training.isEnabled())

        # Running auto-detect resets manual corrections to False
        dummy_mask = np.ones((100, 100), dtype=np.float32)
        self.view._on_detection_finished(dummy_mask)
        qt_app().processEvents()

        self.assertFalse(self.view.has_manual_sky_corrections)
        self.assertFalse(sky_ui.contribute.isEnabled())
        self.assertFalse(sky_ui.training.isEnabled())

    def test_do_export_training_sky_triggers_workflow(self):
        """Verify do_export_training_sky enqueues task and invokes doExportTrainingSky."""
        h, w = 100, 100
        ref_path = self.root / "ref_export.jpg"
        cv2.imwrite(str(ref_path), np.full((h, w, 3), 120, dtype=np.uint8))
        ref_file = DenoiseInputFile(basename=ref_path.name, path=str(ref_path))
        self.project.reference_file = ref_file
        self.project.star_files = [ref_file]

        self.shell.canvas_main._mask_array = np.full((h, w), 255, dtype=np.uint8)

        export_dir = str(self.root / "out_disk")
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory", return_value=export_dir):
                with patch.object(self.app.workflow, "doExportTrainingSky") as mock_export:
                    self.view.do_export_training_sky()
                    qt_app().processEvents()
                    mock_export.assert_called_once()
                    self.assertEqual(mock_export.call_args[0][0], export_dir)

    def test_do_contribute_training_sky_triggers_submission(self):
        """Verify do_contribute_training_sky collects user input and dispatches submission."""
        h, w = 100, 100
        ref_path = self.root / "ref_contrib.jpg"
        cv2.imwrite(str(ref_path), np.full((h, w, 3), 120, dtype=np.uint8))
        ref_file = DenoiseInputFile(basename=ref_path.name, path=str(ref_path))
        self.project.reference_file = ref_file
        self.project.star_files = [ref_file]

        self.shell.canvas_main._mask_array = np.full((h, w), 255, dtype=np.uint8)

        from startrails.ui.contribute_dialog import ContributeCorrectionsDialog

        with patch.object(ContributeCorrectionsDialog, "exec", return_value=ContributeCorrectionsDialog.DialogCode.Accepted):
            with patch.object(ContributeCorrectionsDialog, "values", return_value=("sky@test.com", "Test sky notes")):
                with patch.object(self.app.workflow, "doContributeTrainingSky", return_value={"submission_id": "sub-123", "file_count": 2, "size_bytes": 500}):
                    with patch.object(self.view, "_notify_contribution_result") as mock_notify:
                        self.view.do_contribute_training_sky()
                        qt_app().processEvents()
                        mock_notify.assert_called_once()
                        receipt, err = mock_notify.call_args[0]
                        self.assertIsNone(err)
                        self.assertEqual(receipt["submission_id"], "sub-123")
