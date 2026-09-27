"""Composition of the sidebar's Designer forms."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from startrails.lib.file import OutputFile
from .ui_sidebar import Ui_Sidebar
from .file_manager import FileSection
from .steps import StepCard, DetectSettings, StackSettings, FillSettings, ExportSettings


class Sidebar(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.ui = Ui_Sidebar()
        self.ui.setupUi(self)
        self.ui.contentLayout.setAlignment(Qt.AlignTop)
        self.inputs = FileSection("Input Files", inputs=True)
        self.outputs = FileSection("Output Files")
        self.ui.inputLayout.addWidget(self.inputs)
        self.ui.outputLayout.addWidget(self.outputs)
        self.detect = DetectSettings(app)
        self.stack = StackSettings(app)
        self.fill = FillSettings()
        self.exports = ExportSettings()
        self.detectCard = StepCard("Detect Streaks", self.detect, 1, expanded=True)
        self.stackCard = StepCard("Stack Images", self.stack, 2)
        self.fillCard = StepCard("Fill Gaps", self.fill, 3)
        self.exportCard = StepCard("Optional: Export Artifacts", self.exports)
        self.ui.detectLayout.addWidget(self.detectCard)
        self.ui.stackLayout.addWidget(self.stackCard)
        self.ui.fillLayout.addWidget(self.fillCard)
        self.ui.exportLayout.addWidget(self.exportCard)
        self.exportCard.setSubtitle("Export masks or training samples")
        self.update_operations_progress(app)

    def refresh_inputs(self):
        self.detect.refresh_inputs()
        self.stack.refresh_inputs()

    def reset_settings(self):
        self.detect.reset()
        self.stack.reset()

    def update_operations_progress(self, app, current_file=None):
        """Update progress bar, status labels, and step status badges."""
        inputs = app.getInputFileList() if hasattr(app, "getInputFileList") else []
        outputs = app.getOutputFileList() if hasattr(app, "getOutputFileList") else []
        has_inputs = bool(inputs)
        has_masks = any(len(f.streaksMasks) > 0 or len(f.streaksManualMasks) > 0 for f in inputs)
        has_stacked = any(isinstance(f, OutputFile) and f.operation == "Stacked" for f in outputs)
        has_filled = any(isinstance(f, OutputFile) and f.operation == "FillGaps" for f in outputs)

        if not has_inputs:
            self.detectCard.setStatus("locked", "Add input files to begin")
        elif has_masks:
            self.detectCard.setStatus("done", "Streak masks detected")
        else:
            self.detectCard.setStatus("ready", "Ready to detect streaks")

        if not has_inputs:
            self.stackCard.setStatus("locked", "Add input files to begin")
        elif has_stacked:
            self.stackCard.setStatus("done", "Stacked image generated")
        else:
            self.stackCard.setStatus("ready", "Ready · detection is optional")

        fill_eligible = isinstance(current_file, OutputFile) and current_file.operation == "Stacked"
        if has_filled:
            self.fillCard.setStatus("done", "Gaps filled for stacked image")
        elif fill_eligible:
            self.fillCard.setStatus("ready", "Ready to fill gaps")
        else:
            self.fillCard.setStatus("locked", "Select a stacked output image")

        completed = sum(1 for flag in (has_masks, has_stacked, has_filled) if flag)
        self.ui.operationsProgress.setValue(completed)
        self.ui.operationsProgressLabel.setText(f"{completed} of 3 steps complete")
