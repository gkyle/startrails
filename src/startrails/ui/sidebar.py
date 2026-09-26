"""Composition of the sidebar's Designer forms."""
from PySide6.QtWidgets import QWidget
from .ui_sidebar import Ui_Sidebar
from .file_manager import FileSection
from .steps import StepCard, DetectSettings, StackSettings, FillSettings, ExportSettings


class Sidebar(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.ui = Ui_Sidebar()
        self.ui.setupUi(self)
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

    def refresh_inputs(self):
        self.detect.refresh_inputs()
        self.stack.refresh_inputs()

    def reset_settings(self):
        self.detect.reset()
        self.stack.reset()
