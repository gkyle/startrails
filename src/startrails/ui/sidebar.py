"""Composition of the sidebar's Designer forms."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget
from startrails.lib.file import OutputFile
from .file_manager import FileSection
from .steps import StepCard, DetectSettings, ReviewSettings, StackSettings, FillSettings, ExportSettings


class Sidebar(QWidget):
    def __init__(self, app, parent=None, ui=None):
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.app = app
        if ui is None and hasattr(parent, "sidebar"):
            ui = parent

        if ui is not None:
            self.ui = ui
            self.inputs = FileSection("Input Files", inputs=True, ui=ui, prefix="inputFiles")
            self.outputs = FileSection("Output Files", inputs=False, ui=ui, prefix="outputFiles")
            self.detect = DetectSettings(app, ui=ui)
            self.review = ReviewSettings(app, ui=ui)
            self.stack = StackSettings(app, ui=ui)
            self.fill = FillSettings(ui=ui)
            self.exports = self.review
            self.detectCard = StepCard("Detect Streaks", self.detect, 1, expanded=True, ui=ui, prefix="stepDetect")
            self.reviewCard = StepCard("Review Detections", self.review, 2, ui=ui, prefix="stepReview")
            self.stackCard = StepCard("Stack Images", self.stack, 3, ui=ui, prefix="stepStack")
            self.fillCard = StepCard("Fill Gaps", self.fill, 4, ui=ui, prefix="stepFill")
            self.exportCard = self.reviewCard
            self.update_operations_progress(app)
        else:
            from .ui_sidebar import Ui_Sidebar
            self.ui = Ui_Sidebar()
            self.ui.setupUi(self)
            self.ui.contentLayout.setAlignment(Qt.AlignTop)
            self.inputs = FileSection("Input Files", inputs=True)
            self.outputs = FileSection("Output Files")
            self.ui.inputLayout.addWidget(self.inputs)
            self.ui.outputLayout.addWidget(self.outputs)
            self.detect = DetectSettings(app)
            self.review = ReviewSettings(app)
            self.stack = StackSettings(app)
            self.fill = FillSettings()
            self.exports = self.review
            self.detectCard = StepCard("Detect Streaks", self.detect, 1, expanded=True)
            self.reviewCard = StepCard("Review Detections", self.review, 2)
            self.stackCard = StepCard("Stack Images", self.stack, 3)
            self.fillCard = StepCard("Fill Gaps", self.fill, 4)
            self.exportCard = self.reviewCard
            self.ui.detectLayout.addWidget(self.detectCard)
            self.ui.reviewLayout.addWidget(self.reviewCard)
            self.ui.stackLayout.addWidget(self.stackCard)
            self.ui.fillLayout.addWidget(self.fillCard)
            self.update_operations_progress(app)

    def refresh_review_counts(self):
        inputs = self.app.getInputFileList() if hasattr(self.app, "getInputFileList") else []
        auto_count = sum(len(f.streaksMasks) for f in inputs if hasattr(f, "streaksMasks") and f.streaksMasks)
        manual_count = sum(len(f.streaksManualMasks) for f in inputs if hasattr(f, "streaksManualMasks") and f.streaksManualMasks)
        deleted_count = sum(len(f.streaksManualDeletedMasks) for f in inputs if hasattr(f, "streaksManualDeletedMasks") and f.streaksManualDeletedMasks)
        self.review.set_counts(auto_count, manual_count, deleted_count)
        return auto_count, manual_count, deleted_count

    def refresh_inputs(self):
        self.detect.refresh_inputs()
        self.stack.refresh_inputs()
        self.refresh_review_counts()

    def reset_settings(self):
        self.detect.reset()
        self.review.reset()
        self.stack.reset()

    def update_operations_progress(self, app, current_file=None):
        """Update progress bar, status labels, and step status badges."""
        inputs = app.getInputFileList() if hasattr(app, "getInputFileList") else []
        outputs = app.getOutputFileList() if hasattr(app, "getOutputFileList") else []
        has_inputs = bool(inputs)
        has_masks = any(len(f.streaksMasks) > 0 or len(f.streaksManualMasks) > 0 for f in inputs)
        has_stacked = any(isinstance(f, OutputFile) and f.operation == "Stacked" for f in outputs)
        has_filled = any(isinstance(f, OutputFile) and f.operation == "FillGaps" for f in outputs)

        auto_count, manual_count, deleted_count = self.refresh_review_counts()
        total_detections = auto_count + manual_count
        has_detections = (auto_count + manual_count + deleted_count) > 0

        if not has_inputs:
            self.detectCard.setStatus("locked", "Add input files to begin")
        elif has_masks:
            self.detectCard.setStatus("done", "Streak masks detected")
        else:
            self.detectCard.setStatus("ready", "Ready to detect streaks")

        if not has_inputs:
            self.reviewCard.setStatus("locked", "Add input files to begin")
        elif has_stacked:
            self.reviewCard.setStatus("done", f"{total_detections} detections reviewed")
        elif has_detections:
            self.reviewCard.setStatus("ready", f"{total_detections} active, {deleted_count} deleted")
        else:
            self.reviewCard.setStatus("ready", "Ready · detection is optional")

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

        completed = sum(1 for flag in (has_masks, has_stacked and has_masks, has_stacked, has_filled) if flag)
        self.ui.operationsProgress.setValue(completed)
        self.ui.operationsProgressLabel.setText(f"{completed} of 4 steps complete")

