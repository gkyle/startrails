"""Settings edits, validation, and fade semantics survive UI refresh."""

from types import SimpleNamespace
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from support import QtTestCase
from startrails.lib.file import InputFile
from startrails.lib.project_denoise import DenoiseProject
from startrails.ui.steps import DetectSettings, FillSettings, StackSettings, StepCard, AdditionalToolsSettings
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
            (DenoiseSkySettings(), ("showMaskOverlay",)),
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
