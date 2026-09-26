import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import unittest
from types import SimpleNamespace
from PySide6.QtWidgets import QApplication
from startrails.lib.file import InputFile
from startrails.ui.steps import DetectSettings, StackSettings, StepCard

QT_APP = QApplication.instance() or QApplication([])


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.files = []
        self.suggestions = []

        def suggest(file, gpu):
            self.suggestions.append((file, gpu))
            return 12, 1024**3, False

        self.app = SimpleNamespace(getInputFileList=lambda: self.files, stackSuggestBatchSize=suggest)

    def test_empty_project_is_safe_and_defaults_match(self):
        detect = DetectSettings(self.app)
        stack = StackSettings(self.app)
        self.assertFalse(detect.ui.run.isEnabled())
        self.assertFalse(stack.ui.run.isEnabled())
        self.assertEqual(self.suggestions, [])
        self.assertEqual(detect.values()["confThreshold"], 0.3)
        self.assertEqual(detect.values()["mergeThreshold"], 0.2)
        self.assertEqual(detect.values()["mergeMethod"], "NMS")
        self.assertEqual(stack.values()["fadeAmount"], (0.2, 0.2))
        self.assertFalse(stack.values()["streaksRemoved"])

    def test_refresh_keeps_edits_and_cpu_fallback(self):
        self.files.append(InputFile("image", "image"))
        stack = StackSettings(self.app)
        self.assertEqual(stack.values()["batchSize"], 12)
        self.assertFalse(stack.values()["useGPU"])
        stack.ui.batchSize.setValue(7)
        stack.refresh_inputs()
        self.assertEqual(stack.values()["batchSize"], 7)
        self.assertEqual(len(self.suggestions), 1)
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


if __name__ == "__main__":
    unittest.main()
