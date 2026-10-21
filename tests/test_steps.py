"""Settings edits, validation, and fade semantics survive UI refresh."""

from types import SimpleNamespace
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from support import QtTestCase
from startrails.lib.file import InputFile
from startrails.ui.steps import DetectSettings, StackSettings, StepCard
from startrails.ui.steps_denoise import DenoiseAlignSettings


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

    def test_align_controls_support_keyboard_navigation_and_activation(self):
        align = DenoiseAlignSettings()
        align.ui.run.setEnabled(True)
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
