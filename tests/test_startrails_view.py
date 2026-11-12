"""StarTrails workflow output naming, overwrite semantics, and step preview behavior."""

from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from PySide6.QtWidgets import QLabel, QWidget

from support import IsolatedTestCase, QtTestCase
from startrails.lib.file import (
    OP_FILL_GAPS,
    OP_FILL_GAPS_MASK,
    OP_STACKED_KEEP,
    OP_STACKED_REMOVE,
    InputFile,
    OutputFile,
    preferred_stacked_output,
)
from startrails.lib.util import Observable
from startrails.op.fillGaps import FillGaps
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.views.startrails import StarTrailsView


def _write_solid_image(path: Path, value: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = np.full((12, 12, 3), value, dtype=np.uint8)
    assert cv2.imwrite(str(path), image)
    return path


class StarTrailsArtifactTests(IsolatedTestCase):
    def test_stack_and_fill_gaps_use_fixed_names_and_overwrite_on_rerun(self):
        app = self.make_app()
        for idx, value in enumerate((60, 120)):
            p = _write_solid_image(self.root / f"frame-{idx}.jpg", value)
            app.project.rawInputFiles.append(InputFile(p.name, str(p)))

        kept = app.doStack(False, lambda *args: None, useGPU=False)
        self.assertEqual(kept.basename, "startrails-stacked-keep.jpg")
        self.assertEqual(kept.operation, OP_STACKED_KEEP)
        self.assertIs(preferred_stacked_output(app.getOutputFileList()), kept)

        removed = app.doStack(True, lambda *args: None, useGPU=False)
        self.assertEqual(removed.basename, "startrails-stacked.jpg")
        self.assertEqual(removed.operation, OP_STACKED_REMOVE)
        self.assertIs(preferred_stacked_output(app.getOutputFileList()), removed)
        self.assertEqual(len(app.getOutputFileList()), 2)

        restacked = app.doStack(False, lambda *args: None, useGPU=False)
        self.assertIs(restacked, kept)
        self.assertEqual(len(app.getOutputFileList()), 2)

        class FakeFill(Observable):
            suggestOutFileName = staticmethod(FillGaps.suggestOutFileName)

            def fillGaps(self, file, filled, output_mask):
                cv2.imwrite(filled.path, cv2.imread(file.path))
                cv2.imwrite(output_mask.path, np.zeros((12, 12, 3), dtype=np.uint8))

            def shouldInterrupt(self):
                return False

        import startrails.app as app_module

        original_fgm = app_module.fgm
        try:
            app_module.fgm = SimpleNamespace(FillGaps=FakeFill)
            filled = app.doFillGaps(removed, lambda *args: None)
            self.assertEqual(filled.basename, "startrails-final.jpg")
            self.assertEqual(filled.operation, OP_FILL_GAPS)
            mask = next(f for f in app.getOutputFileList() if f.operation == OP_FILL_GAPS_MASK)
            self.assertEqual(mask.basename, "startrails-final-mask.jpg")
            self.assertEqual(len(app.getOutputFileList()), 4)

            refilled = app.doFillGaps(removed, lambda *args: None)
            self.assertIs(refilled, filled)
            self.assertEqual(len(app.getOutputFileList()), 4)
        finally:
            app_module.fgm = original_fgm


class StarTrailsViewPreviewTests(QtTestCase):
    def _build_view(self):
        app = self.make_app()
        in1_path = _write_solid_image(self.root / "in1.tif", 30)
        in2_path = _write_solid_image(self.root / "in2.tif", 60)
        keep_path = _write_solid_image(self.root / "out" / "startrails-stacked-keep.tif", 110)
        rem_path = _write_solid_image(self.root / "out" / "startrails-stacked.tif", 170)
        final_path = _write_solid_image(self.root / "out" / "startrails-final.tif", 220)
        mask_path = _write_solid_image(self.root / "out" / "startrails-final-mask.tif", 255)

        in1 = InputFile(in1_path.name, str(in1_path))
        in2 = InputFile(in2_path.name, str(in2_path))
        keep = OutputFile(keep_path.name, str(keep_path), OP_STACKED_KEEP)
        removed = OutputFile(rem_path.name, str(rem_path), OP_STACKED_REMOVE)
        final = OutputFile(final_path.name, str(final_path), OP_FILL_GAPS)
        mask = OutputFile(mask_path.name, str(mask_path), OP_FILL_GAPS_MASK)

        app.project.rawInputFiles.extend([in1, in2])
        app.project.outputFiles.extend([keep, removed, final, mask])

        host = QWidget()
        canvas = CanvasLabel()
        label = QLabel()
        self.addCleanup(host.deleteLater)
        self.addCleanup(canvas.deleteLater)
        self.addCleanup(label.deleteLater)

        shell = SimpleNamespace(canvas_main=canvas, label_imageName=label, currentFile=None)
        view = StarTrailsView(app, shell)
        sidebar = view.build_sidebar(host)
        view.bind()
        view.resetProjectView()
        self.addCleanup(view.teardown)

        return SimpleNamespace(
            app=app,
            view=view,
            sidebar=sidebar,
            canvas=canvas,
            shell=shell,
            in1=in1,
            in2=in2,
            keep=keep,
            removed=removed,
            final=final,
        )

    def test_step_card_previews_and_fill_before_after_toggle(self):
        ctx = self._build_view()
        sidebar = ctx.sidebar
        shell = ctx.shell
        canvas = ctx.canvas

        # resetProjectView restores initial Detect Streaks step expansion and keeps file lists collapsed.
        self.assertTrue(sidebar.detectCard.is_expanded)
        self.assertFalse(sidebar.stackCard.is_expanded)
        self.assertFalse(sidebar.reviewCard.is_expanded)
        self.assertFalse(sidebar.fillCard.is_expanded)
        self.assertFalse(sidebar.inputs.is_expanded)
        self.assertFalse(sidebar.outputs.is_expanded)
        self.assertIs(shell.currentFile, ctx.in1)

        # Detect Streaks keeps an already-displayed InputFile, otherwise selects first input.
        ctx.view.showFile(ctx.in2)
        sidebar.detectCard.setExpanded(True)
        self.assertIs(shell.currentFile, ctx.in2)

        # Stack Images shows preferred stacked output (removed > keep) with no before/after toggle.
        sidebar.stackCard.setExpanded(True)
        self.assertIs(shell.currentFile, ctx.removed)
        self.assertFalse(sidebar.stackCard._before_after_enabled)
        self.assertFalse(sidebar.outputs.is_expanded)

        # Detect Streaks switches back to first input when an output is currently displayed.
        sidebar.detectCard.setExpanded(True)
        self.assertIs(shell.currentFile, ctx.in1)

        # Review and Correct shows preferred stacked output.
        sidebar.reviewCard.setExpanded(True)
        self.assertIs(shell.currentFile, ctx.removed)
        self.assertFalse(sidebar.outputs.is_expanded)

        # Fill Gaps targets preferred stacked output automatically, starts on after, and toggles cleanly.
        self.assertTrue(ctx.view.pushButton_fillGaps.isEnabled())
        self.assertEqual(sidebar.fill.ui.target.text(), "startrails-stacked.tif")
        sidebar.fillCard.setExpanded(True)
        self.assertIs(shell.currentFile, ctx.final)
        self.assertTrue(sidebar.fillCard.ui.previewToggle.isVisibleTo(sidebar) or sidebar.fillCard.ui.previewToggle.isVisible())

        canvas.zoom_factor = 3.0
        canvas.posX, canvas.posY = 4, 5
        sidebar.fillCard.ui.previewToggle.click()
        self.assertIs(shell.currentFile, ctx.removed)
        self.assertEqual((canvas.zoom_factor, canvas.posX, canvas.posY), (3.0, 4, 5))
        self.assertFalse(sidebar.outputs.is_expanded)

        sidebar.fillCard.ui.previewToggle.click()
        self.assertIs(shell.currentFile, ctx.final)
        self.assertEqual((canvas.zoom_factor, canvas.posX, canvas.posY), (3.0, 4, 5))
        self.assertFalse(sidebar.outputs.is_expanded)

        # Collapsing resets before/after back to after.
        sidebar.fillCard.ui.previewToggle.click()
        self.assertIs(shell.currentFile, ctx.removed)
        sidebar.fillCard.setExpanded(False)
        self.assertFalse(sidebar.fillCard.is_showing_before())
        self.assertIs(shell.currentFile, ctx.final)

        # Fallback to startrails-stacked-keep when startrails-stacked is absent.
        ctx.app.removeOutputFile(ctx.removed)
        ctx.view.slotRefreshOutputs()
        self.assertEqual(sidebar.fill.ui.target.text(), "startrails-stacked-keep.tif")
        sidebar.reviewCard.setExpanded(True)
        self.assertIs(shell.currentFile, ctx.keep)

        # When all stacked outputs are removed from metadata, comparison is disabled and subtitle clarifies.
        sidebar.fillCard.setExpanded(True)
        self.assertTrue(sidebar.fillCard._before_after_enabled)
        ctx.app.removeOutputFile(ctx.keep)
        ctx.view.slotRefreshOutputs()
        self.assertEqual(sidebar.fill.ui.target.text(), "Stack images first to fill gaps.")
        self.assertFalse(ctx.view.pushButton_fillGaps.isEnabled())
        self.assertFalse(sidebar.fillCard._before_after_enabled)
        self.assertFalse(sidebar.fillCard.ui.previewToggle.isVisible())
        self.assertEqual(sidebar.fillCard.ui.subtitle.text(), "Gaps filled · stack unavailable")
        self.assertEqual(sidebar.fillCard.status, "done")
        ctx.view._on_fill_before_after(True)
        self.assertIs(shell.currentFile, ctx.final)
        self.assertFalse(sidebar.fillCard.is_showing_before())

        # Physical disk deletion without metadata removal also disables comparison safely,
        # covering the race where base is deleted on disk then clicked without prior slotRefreshOutputs.
        keep_path = _write_solid_image(self.root / "out" / "startrails-stacked-keep-disk.tif", 110)
        keep_disk = OutputFile(keep_path.name, str(keep_path), OP_STACKED_KEEP)
        ctx.app.project.outputFiles.append(keep_disk)
        ctx.view.slotRefreshOutputs()
        self.assertTrue(sidebar.fillCard._before_after_enabled)
        keep_path.unlink()
        # Direct click in the race window without calling slotRefreshOutputs.
        sidebar.fillCard.ui.previewToggle.click()
        self.assertFalse(sidebar.fillCard._before_after_enabled)
        self.assertFalse(sidebar.fillCard.ui.previewToggle.isVisible())
        self.assertEqual(sidebar.fillCard.ui.subtitle.text(), "Gaps filled · stack unavailable")
        self.assertIs(shell.currentFile, ctx.final)
        self.assertFalse(sidebar.fillCard.is_showing_before())

        # When After (final) is missing, comparison is also not claimed when only stack remains.
        keep_path = _write_solid_image(self.root / "out" / "startrails-stacked-keep-disk.tif", 110)
        Path(ctx.final.path).unlink()
        ctx.view.slotRefreshOutputs()
        self.assertFalse(sidebar.fillCard._before_after_enabled)
        self.assertFalse(sidebar.fillCard.ui.previewToggle.isVisible())
        self.assertEqual(sidebar.fillCard.status, "ready")
        self.assertEqual(sidebar.fillCard.ui.subtitle.text(), "Ready to fill gaps")

        # resetProjectView from an advanced step restores Detect step expansion and keeps file sections collapsed.
        sidebar.fillCard.setExpanded(True)
        self.assertTrue(sidebar.fillCard.is_expanded)
        ctx.view.resetProjectView()
        self.assertTrue(sidebar.detectCard.is_expanded)
        self.assertFalse(sidebar.fillCard.is_expanded)
        self.assertFalse(sidebar.inputs.is_expanded)
        self.assertFalse(sidebar.outputs.is_expanded)
        self.assertIs(shell.currentFile, ctx.in1)

    def test_corrections_change_stack_status_to_ready_and_track_applied_vs_new(self):
        ctx = self._build_view()
        sidebar = ctx.sidebar

        # 1. Pre-stack state: before any stack exists, detection is optional and no applied claim
        ctx.app.project.outputFiles.clear()
        sidebar.update_operations_progress()
        self.assertEqual(sidebar.stackCard.status, "ready")
        self.assertEqual(sidebar.stackCard.ui.subtitle.text(), "Ready · detection is optional")
        self.assertEqual(sidebar.reviewCard.status, "ready")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "0 corrections")
        self.assertTrue(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

        # Adding a manual correction pre-stack displays count without applied claim or regenerate notice
        ctx.in1.streaksManualMasks.append([[1, 1], [2, 2], [3, 3]])
        ctx.view.slotFileIndicators(ctx.in1)
        self.assertEqual(sidebar.stackCard.status, "ready")
        self.assertEqual(sidebar.stackCard.ui.subtitle.text(), "Ready · detection is optional")
        self.assertEqual(sidebar.reviewCard.status, "ready")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "1 correction")
        self.assertTrue(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

        # 2. Running stack with Remove applies corrections and marks steps done
        ctx.app.doStack(True, lambda *args: None, useGPU=False)
        ctx.view.slotRefreshOutputs()
        self.assertEqual(sidebar.stackCard.status, "done")
        self.assertEqual(sidebar.reviewCard.status, "done")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "1 applied")
        self.assertTrue(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

        # 3. Same-count vertex move marks corrections changed and shows notice
        ctx.in1.streaksManualMasks[0][0] = [10, 10]
        ctx.view.slotFileIndicators(ctx.in1)
        self.assertEqual(sidebar.stackCard.status, "ready")
        self.assertEqual(sidebar.stackCard.ui.subtitle.text(), "Ready · corrections updated")
        self.assertEqual(sidebar.reviewCard.status, "ready")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "1 applied · corrections changed")
        self.assertFalse(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

        # 4. Stacking in Keep mode does NOT clear pending notice or mark corrections applied
        ctx.app.doStack(False, lambda *args: None, useGPU=False)
        ctx.view.slotRefreshOutputs()
        self.assertEqual(sidebar.stackCard.status, "ready")
        self.assertEqual(sidebar.stackCard.ui.subtitle.text(), "Ready · corrections updated")
        self.assertEqual(sidebar.reviewCard.status, "ready")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "1 applied · corrections changed")
        self.assertFalse(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

        # 5. Successful Remove stack clears pending notice
        ctx.app.doStack(True, lambda *args: None, useGPU=False)
        ctx.view.slotRefreshOutputs()
        self.assertEqual(sidebar.stackCard.status, "done")
        self.assertEqual(sidebar.reviewCard.status, "done")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "1 applied")
        self.assertTrue(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

        # 6. Removal of all corrections marks corrections changed and shows notice
        ctx.in1.streaksManualMasks.clear()
        ctx.view.slotFileIndicators(ctx.in1)
        self.assertEqual(sidebar.stackCard.status, "ready")
        self.assertEqual(sidebar.stackCard.ui.subtitle.text(), "Ready · corrections updated")
        self.assertEqual(sidebar.reviewCard.status, "ready")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "1 applied · corrections changed")
        self.assertFalse(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

        # Successful Remove stack clears snapshot to 0 corrections
        ctx.app.doStack(True, lambda *args: None, useGPU=False)
        ctx.view.slotRefreshOutputs()
        self.assertEqual(sidebar.stackCard.status, "done")
        self.assertEqual(sidebar.reviewCard.status, "done")
        self.assertEqual(sidebar.reviewCard.ui.subtitle.text(), "0 corrections")
        self.assertTrue(sidebar.review.ui.pendingCorrectionsNotice.isHidden())

    def test_stack_settings_persist_to_project_file(self):
        from unittest.mock import MagicMock

        ctx = self._build_view()
        stack = ctx.sidebar.stack

        # Simulate masks present so streaks choice can be non-default False
        ctx.in1.streaksMasks.append([[0, 0], [10, 10]])
        ctx.view.slotDetectStreaksFinished()

        # Set non-default ALL settings including False
        stack.ui.fade.setCurrentIndex(1)  # Fade start
        stack.ui.fadeAmount.setValue(45)
        stack.ui.batchSize.setValue(3)
        stack.ui.useGPU.setChecked(False)
        stack.ui.streaks.setCurrentIndex(0)  # Keep

        # Check in project
        proj = ctx.app.project
        self.assertEqual(proj.fadeMode, 1)
        self.assertEqual(proj.fadeAmount, 45)
        self.assertEqual(proj.batchSize, 3)
        self.assertFalse(proj.useGPU)
        self.assertFalse(proj.streaksRemoved)

        # Values reflect these settings
        vals = stack.values()
        self.assertEqual(vals["fade"], True)
        self.assertEqual(vals["fadeAmount"], (0.45, 0.0))
        self.assertEqual(vals["batchSize"], 3)
        self.assertFalse(vals["useGPU"])
        self.assertFalse(vals["streaksRemoved"])

        # Resetting view restores settings from project without overwriting on-disk or saving during hydration
        ctx.app.saveProject = MagicMock()
        ctx.view.resetProjectView()
        ctx.app.saveProject.assert_not_called()

        self.assertEqual(proj.fadeMode, 1)
        self.assertEqual(proj.fadeAmount, 45)
        self.assertEqual(proj.batchSize, 3)
        self.assertFalse(proj.useGPU)
        self.assertFalse(proj.streaksRemoved)

        self.assertEqual(stack.ui.fade.currentIndex(), 1)
        self.assertEqual(stack.ui.fadeAmount.value(), 45)
        self.assertEqual(stack.ui.batchSize.value(), 3)
        self.assertFalse(stack.ui.useGPU.isChecked())
        self.assertEqual(stack.ui.streaks.currentIndex(), 0)

    def test_completing_detect_streaks_defaults_stack_streaks_to_remove(self):
        ctx = self._build_view()
        stack = ctx.sidebar.stack

        # Initially no masks exist for in1 or in2
        self.assertEqual(stack.ui.streaks.currentIndex(), 0)
        self.assertFalse(stack.ui.streaks.model().item(1).isEnabled())

        # Simulate streak detection completing and finding a mask on in1
        ctx.in1.streaksMasks.append([[0, 0], [10, 10]])
        ctx.view.slotDetectStreaksFinished()

        # Stack Images streaks setting defaults to Remove (index 1)
        self.assertTrue(stack.ui.streaks.model().item(1).isEnabled())
        self.assertEqual(stack.ui.streaks.currentIndex(), 1)
        self.assertTrue(stack.values()["streaksRemoved"])
        self.assertTrue(ctx.app.project.streaksRemoved)

        # If user switches to Keep, but then runs and completes Detect Streaks again, it defaults back to Remove
        stack.ui.streaks.setCurrentIndex(0)
        self.assertEqual(stack.ui.streaks.currentIndex(), 0)
        self.assertFalse(stack.values()["streaksRemoved"])
        ctx.view.slotDetectStreaksFinished()
        self.assertEqual(stack.ui.streaks.currentIndex(), 1)
        self.assertTrue(stack.values()["streaksRemoved"])
