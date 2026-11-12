"""Settings edits, validation, and fade semantics survive UI refresh."""

from types import SimpleNamespace
from unittest.mock import patch
import torch
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from support import QtTestCase
from startrails.lib.file import InputFile
from startrails.lib.project_denoise import DenoiseProject
from startrails.ui.steps import (
    PREVIEW_LONG_PRESS_MS,
    DetectSettings,
    FillSettings,
    StackSettings,
    StepCard,
    AdditionalToolsSettings,
)
from startrails.ui.steps_denoise import (
    DenoiseAlignSettings,
    DenoiseSkySettings,
    DenoiseStackSettings,
    DenoiseTuneSettings,
    DenoiseExportSettings,
)


class SettingsTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.files = []
        self.suggestions = []

        def suggest(file, gpu):
            self.suggestions.append((file, gpu))
            return 12, 1024**3, False

        self.app = SimpleNamespace(getInputFileList=lambda: self.files, stackSuggestBatchSize=suggest)

    def test_refresh_keeps_edits_and_cpu_fallback(self):
        self.files.append(InputFile("image", "image"))
        stack = StackSettings(self.app)
        self.assertEqual(stack.values()["batchSize"], 12)
        self.assertFalse(stack.values()["useGPU"])
        stack.ui.batchSize.setValue(7)
        stack.refresh_inputs()
        self.assertEqual(stack.values()["batchSize"], 7)
        stack.set_has_masks(True)
        self.assertTrue(stack.values()["streaksRemoved"])
        stack.ui.streaks.setCurrentIndex(0)
        stack.set_has_masks(True)
        self.assertFalse(stack.values()["streaksRemoved"])

    def test_stack_streaks_defaults_to_remove_when_masks_available_with_project(self):
        from startrails.lib.project import Project
        self.app.project = Project()
        stack = StackSettings(self.app)
        self.assertIsNone(self.app.project.streaksRemoved)
        stack.ui.batchSize.setValue(5)
        self.assertIsNone(self.app.project.streaksRemoved)
        stack.set_has_masks(True)
        self.assertEqual(stack.ui.streaks.currentIndex(), 1)
        self.assertTrue(stack.values()["streaksRemoved"])
        self.assertTrue(self.app.project.streaksRemoved)

    def test_collapse_and_fade_mapping(self):
        stack = StackSettings(self.app)
        card = StepCard("Stack Images", stack, 2)
        stack.ui.fadeAmount.setValue(35)
        for mode, expected in enumerate(((0, 0), (0.35, 0), (0, 0.35), (0.35, 0.35))):
            stack.ui.fade.setCurrentIndex(mode)
            card.setExpanded(True)
            card.setExpanded(False)
            self.assertEqual(stack.values()["fadeAmount"], expected)
        self.assertTrue(stack.ui.fadeAmount.isEnabled())

    def test_stack_and_detect_settings_default_to_startrails_defaults(self):
        from startrails.lib.project import Project
        from startrails.lib.startrails.defaults import (
            DEFAULT_MERGE_METHOD_INDEX,
            STARTRAILS_DEFAULTS,
        )
        detect = DetectSettings(self.app)
        self.assertEqual(detect.ui.confidence.value(), STARTRAILS_DEFAULTS.conf_threshold)
        self.assertEqual(detect.ui.mergeThreshold.value(), STARTRAILS_DEFAULTS.merge_threshold)
        self.assertEqual(detect.ui.mergeMethod.currentIndex(), DEFAULT_MERGE_METHOD_INDEX)
        self.assertEqual(detect.values()["mergeMethod"], STARTRAILS_DEFAULTS.merge_method)

        # Standalone StackSettings with no files has default fade and batch settings
        stack = StackSettings(self.app)
        self.assertEqual(stack.ui.fade.currentIndex(), STARTRAILS_DEFAULTS.fade_mode)
        self.assertEqual(stack.ui.fadeAmount.value(), STARTRAILS_DEFAULTS.fade_amount)
        self.assertEqual(stack.ui.batchSize.value(), STARTRAILS_DEFAULTS.batch_size)

        # Associated Project defaults match STARTRAILS_DEFAULTS
        proj = Project()
        self.assertEqual(proj.fadeMode, STARTRAILS_DEFAULTS.fade_mode)
        self.assertEqual(proj.fadeAmount, STARTRAILS_DEFAULTS.fade_amount)
        self.assertEqual(proj.batchSize, STARTRAILS_DEFAULTS.batch_size)
        self.assertEqual(proj.useGPU, STARTRAILS_DEFAULTS.use_gpu)

    def test_invalid_text_does_not_produce_settings(self):
        detect = DetectSettings(self.app)
        detect.ui.confidence.lineEdit().setText("")
        self.assertIsNone(detect.values())
        self.assertTrue(detect.ui.error.text())

    def test_gpu_controls_follow_device_availability(self):
        self.files.append(InputFile("image", "image"))
        self.app.gpuInfo = SimpleNamespace(get_gpu_present=lambda: False)
        project = DenoiseProject(str(self.root / "gpu.proj_denoise"), use_gpu=True)
        denoise_app = self.make_app(project)
        settings = (
            DetectSettings(self.app),
            StackSettings(self.app),
            DenoiseAlignSettings(denoise_app),
            DenoiseStackSettings(denoise_app),
        )
        for setting in settings:
            with self.subTest(setting=type(setting).__name__):
                checkbox = setting.ui.useGPU
                self.assertFalse(checkbox.isEnabled())
                self.assertFalse(checkbox.isChecked())
                checkbox.click()
                self.assertFalse(checkbox.isChecked())

        self.app.gpuInfo = SimpleNamespace(get_gpu_present=lambda: True)
        denoise_app.gpuInfo = self.app.gpuInfo
        for setting in settings:
            if isinstance(setting, (DenoiseAlignSettings, DenoiseStackSettings)):
                setting.refresh_inputs(ready=True)
            else:
                setting.refresh_inputs()
            self.assertTrue(setting.ui.useGPU.isEnabled())

    def test_detector_accelerator_available_when_stacking_gpu_unavailable(self):
        self.files.append(InputFile("image", "image"))
        self.app.gpuInfo = SimpleNamespace(get_gpu_present=lambda: True)

        with patch(
            "startrails.ui.steps.resolve_torch_device",
            side_effect=lambda *, use_gpu: torch.device("mps" if use_gpu else "cpu"),
        ):
            detect = DetectSettings(self.app)
            stack = StackSettings(self.app)

            # Detector auto-selects available Torch inference accelerator.
            self.assertTrue(detect.ui.useGPU.isEnabled())
            self.assertTrue(detect.ui.useGPU.isChecked())
            self.assertTrue(detect.values()["useGPU"])

            # Stacking remains CPU because CuPy is unavailable.
            self.assertTrue(stack.ui.useGPU.isEnabled())
            self.assertFalse(stack.ui.useGPU.isChecked())
            self.assertFalse(stack.values()["useGPU"])
            self.assertIn("CPU", stack.ui.memory.text())

            # Manual unchecking of detector is honored and survives refresh.
            detect.ui.useGPU.click()
            self.assertFalse(detect.ui.useGPU.isChecked())
            self.assertFalse(detect.values()["useGPU"])
            detect.refresh_inputs()
            self.assertFalse(detect.ui.useGPU.isChecked())
            self.assertFalse(detect.values()["useGPU"])

            # Manual checking of detector is honored and forwards useGPU=True.
            detect.ui.useGPU.click()
            self.assertTrue(detect.ui.useGPU.isChecked())
            self.assertTrue(detect.values()["useGPU"])

            # Stacking remains CPU.
            self.assertFalse(stack.values()["useGPU"])

    def test_align_controls_support_keyboard_navigation_and_activation(self):
        align = DenoiseAlignSettings()
        align.ui.run.setEnabled(True)
        align.ui.useGPU.setEnabled(True)
        align.show()
        align.activateWindow()
        self.qt.processEvents()

        align.ui.run.setFocus()
        self.qt.processEvents()
        self.assertTrue(align.ui.run.hasFocus())
        clicks = []
        align.ui.run.clicked.connect(lambda: clicks.append(True))
        QTest.keyClick(align.ui.run, Qt.Key.Key_Space)
        self.assertEqual(clicks, [True])
        QTest.keyClick(align.ui.run, Qt.Key.Key_Tab)
        self.assertTrue(align.ui.advancedToggle.hasFocus())
        QTest.keyClick(align.ui.advancedToggle, Qt.Key.Key_Space)
        self.assertTrue(align.ui.advancedToggle.isChecked())

        QTest.keyClick(align.ui.advancedToggle, Qt.Key.Key_Tab)
        self.assertTrue(align.ui.useGPU.hasFocus())
        before = align.ui.useGPU.isChecked()
        QTest.keyClick(align.ui.useGPU, Qt.Key.Key_Space)
        self.assertNotEqual(align.ui.useGPU.isChecked(), before)

    def test_other_step_controls_accept_keyboard_focus(self):
        forms = (
            (DetectSettings(self.app), ("run", "advancedToggle", "useGPU")),
            (StackSettings(self.app), ("run", "advancedToggle", "useGPU")),
            (FillSettings(), ("run",)),
            (DenoiseSkySettings(), ("clearMask", "fullFrameMask", "refineMask")),
            (DenoiseStackSettings(), ("run", "advancedToggle", "useGPU", "compressIntermediateTiffs")),
            (DenoiseTuneSettings(), ("enableCorrections", "showGradientMask")),
            (AdditionalToolsSettings(), ("masks", "contribute", "training")),
            (DenoiseExportSettings(), ("contribute", "training")),
        )
        for form, names in forms:
            if hasattr(form.ui, "advancedToggle"):
                form.ui.advancedToggle.setChecked(True)
            form.show()
            form.activateWindow()
            self.qt.processEvents()
            for name in names:
                with self.subTest(form=type(form).__name__, control=name):
                    control = getattr(form.ui, name)
                    control.setEnabled(True)
                    self.assertTrue(control.focusPolicy() & Qt.FocusPolicy.TabFocus)
                    control.setFocus()
                    self.qt.processEvents()
                    self.assertTrue(control.hasFocus())

        card = StepCard("Step", FillSettings(), 1)
        card.show()
        card.activateWindow()
        self.qt.processEvents()
        self.assertTrue(card.ui.toggle.focusPolicy() & Qt.FocusPolicy.TabFocus)
        card.ui.toggle.setFocus()
        self.qt.processEvents()
        self.assertTrue(card.ui.toggle.hasFocus())

    def test_step_card_alert_for_unnumbered_card(self):
        card = StepCard("Contribute and Export", FillSettings())
        self.assertFalse(card.has_number)
        self.assertFalse(card.alert)
        self.assertEqual(card.ui.number.text(), "")
        self.assertEqual(card.ui.number.property("stepStatus"), "neutral")
        self.assertFalse(card.ui.statusBadge.isVisible())
        self.assertEqual(card.step_number, 0)

        card.set_alert(True)
        self.assertTrue(card.alert)
        self.assertEqual(card.ui.number.text(), "!")
        self.assertEqual(card.ui.number.property("stepStatus"), "ready")
        self.assertFalse(card.ui.statusBadge.isVisible())
        self.assertEqual(card.step_number, 0)

        card.set_alert(False)
        self.assertFalse(card.alert)
        self.assertEqual(card.ui.number.text(), "")
        self.assertEqual(card.ui.number.property("stepStatus"), "neutral")
        self.assertFalse(card.ui.statusBadge.isVisible())
        self.assertEqual(card.step_number, 0)

        card.alert = True
        self.assertTrue(card.alert)
        self.assertEqual(card.ui.number.text(), "!")
        self.assertEqual(card.ui.number.property("stepStatus"), "ready")

    def test_step_card_before_after_toggle(self):
        # Control elapsed time at the clock boundary; no wall-clock sleeps or
        # dependence on how quickly the machine delivers mouse events.
        class ManualTimer:
            now_ms = 0
            started_ms = None

            def start(self):
                self.started_ms = self.now_ms

            restart = start

            def isValid(self):
                return self.started_ms is not None

            def elapsed(self):
                return self.now_ms - self.started_ms

        timer = ManualTimer()
        self.enterContext(patch("startrails.ui.steps.QElapsedTimer", return_value=timer))
        card = StepCard("Finish Starless", FillSettings(), 3, expanded=False)
        card.show()
        self.qt.processEvents()

        # Eye chip is placed to the left of the status badge.
        header_layout = card.ui.headerLayout
        self.assertLess(header_layout.indexOf(card.ui.previewToggle), header_layout.indexOf(card.ui.statusBadge))

        # Unconfigured card never displays the chip, even when expanded and done.
        card.setStatus("done")
        card.setExpanded(True)
        self.assertFalse(card.ui.previewToggle.isVisible())

        # Configured card only displays the chip when expanded AND status == "done".
        card.setExpanded(False)
        card.set_before_after_enabled(True)
        self.assertFalse(card.ui.previewToggle.isVisible())

        card.setExpanded(True)
        self.assertTrue(card.ui.previewToggle.isVisible())
        self.assertFalse(card.ui.previewToggle.isChecked())
        self.assertFalse(card.is_showing_before())

        for non_done in ("ready", "running", "locked"):
            card.setStatus(non_done)
            self.assertFalse(card.ui.previewToggle.isVisible())

        card.setStatus("done")
        card.setExpanded(True)
        self.assertTrue(card.ui.previewToggle.isVisible())

        events = []
        card.before_after_toggled.connect(events.append)

        # Pressing down immediately triggers showing "before" without collapsing the card.
        self.assertFalse(card.ui.previewToggle.property("showingBefore"))
        QTest.mousePress(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events, [True])
        self.assertTrue(card.is_showing_before())
        self.assertTrue(card.ui.previewToggle.property("showingBefore"))
        self.assertTrue(card.is_expanded)

        # Releasing inside toggles to "before" and stays there.
        QTest.mouseRelease(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events, [True])
        self.assertTrue(card.ui.previewToggle.isChecked())
        self.assertTrue(card.is_showing_before())

        # Second click toggles back to "after".
        QTest.mouseClick(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events, [True, False])
        self.assertFalse(card.ui.previewToggle.isChecked())
        self.assertFalse(card.ui.previewToggle.property("showingBefore"))
        self.assertFalse(card.is_showing_before())

        # Press-and-drag-off peeks "before" while held down and returns to "after" on release.
        QTest.mousePress(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events, [True, False, True])
        QTest.mouseMove(card.ui.previewToggle, QPoint(-20, -20))
        QTest.mouseRelease(card.ui.previewToggle, Qt.LeftButton, pos=QPoint(-20, -20))
        self.assertEqual(events, [True, False, True, False])
        self.assertFalse(card.ui.previewToggle.isChecked())

        # Long press from "after" shows "before" on mouse down and returns to "after" on mouse up.
        QTest.mousePress(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events[-1], True)
        self.assertTrue(card.is_showing_before())
        timer.now_ms += PREVIEW_LONG_PRESS_MS
        QTest.mouseRelease(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events[-1], False)
        self.assertFalse(card.ui.previewToggle.isChecked())
        self.assertFalse(card.ui.previewToggle.isDown())
        self.assertFalse(card.ui.previewToggle.property("showingBefore"))
        self.assertFalse(card.is_showing_before())

        # Follow-up short click right after long press still toggles cleanly.
        QTest.mouseClick(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events[-1], True)
        self.assertTrue(card.ui.previewToggle.isChecked())

        # Long press when starting in "before" also returns to "after" on release.
        QTest.mousePress(card.ui.previewToggle, Qt.LeftButton)
        self.assertTrue(card.is_showing_before())
        timer.now_ms += PREVIEW_LONG_PRESS_MS
        QTest.mouseRelease(card.ui.previewToggle, Qt.LeftButton)
        self.assertEqual(events[-1], False)
        self.assertFalse(card.ui.previewToggle.isChecked())
        self.assertFalse(card.is_showing_before())

        # Collapsing resets to "after" (emitting False) and hides the chip; re-expanding keeps "after".
        QTest.mouseClick(card.ui.previewToggle, Qt.LeftButton)
        self.assertTrue(card.ui.previewToggle.isChecked())
        self.assertEqual(events[-1], True)
        card.setExpanded(False)
        self.assertEqual(events[-1], False)
        self.assertFalse(card.ui.previewToggle.isVisible())
        self.assertFalse(card.ui.previewToggle.isChecked())
        self.assertFalse(card.is_showing_before())
        card.setExpanded(True)
        self.assertTrue(card.ui.previewToggle.isVisible())
        self.assertFalse(card.ui.previewToggle.isChecked())
        self.assertFalse(card.is_showing_before())

        # A slow synchronous preview load during mouse down must not turn a quick click into a long press.
        def slow_handler(showing_before):
            if showing_before:
                timer.now_ms += PREVIEW_LONG_PRESS_MS

        card.before_after_toggled.connect(slow_handler)
        try:
            QTest.mousePress(card.ui.previewToggle, Qt.LeftButton)
            QTest.mouseRelease(card.ui.previewToggle, Qt.LeftButton)
        finally:
            card.before_after_toggled.disconnect(slow_handler)
        self.assertTrue(card.ui.previewToggle.isChecked())
        self.assertTrue(card.is_showing_before())
