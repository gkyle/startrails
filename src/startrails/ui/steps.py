"""Behavior for Designer-authored operation cards and settings."""
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QFrame, QWidget

from .ui_step import Ui_StepCard
from .ui_step_detect_streaks import Ui_DetectSettings
from .ui_step_stack_images import Ui_StackSettings
from .ui_step_fill_gaps import Ui_FillSettings
from .ui_step_export_artifacts import Ui_ExportSettings


class StepCard(QFrame):
    def __init__(self, title, body, number=None, expanded=False, parent=None):
        super().__init__(parent)
        self.ui = Ui_StepCard()
        self.ui.setupUi(self)
        self._status = "ready"
        self.ui.toggle.setText(title)
        self.ui.toggle.setAccessibleName(title)
        self.has_number = number is not None
        self.ui.number.setVisible(self.has_number)
        self.ui.number.setText(str(number or ""))
        if not self.has_number:
            self.ui.statusBadge.setVisible(False)
        self.ui.contentLayout.addWidget(body)
        self.ui.toggle.toggled.connect(self.setExpanded)
        self.ui.headerWidget.mousePressEvent = self._on_header_clicked
        self.setExpanded(expanded)
        self._update_status_appearance()

    def _on_header_clicked(self, event):
        if event.button() == Qt.LeftButton:
            self.ui.toggle.toggle()
            event.accept()
            return
        super(QWidget, self.ui.headerWidget).mousePressEvent(event)

    def setExpanded(self, expanded):
        with QSignalBlocker(self.ui.toggle):
            self.ui.toggle.setChecked(expanded)
        self.ui.chevron.setText("▼" if expanded else "▶")
        self.ui.body.setVisible(expanded)
        if not expanded:
            self.setFixedHeight(self.ui.headerWidget.sizeHint().height() + 2)
        else:
            self.setMaximumHeight(16777215)
            self.setMinimumHeight(0)
            self.adjustSize()
        self.updateGeometry()

    def setSubtitle(self, text):
        self.ui.subtitle.setText(text)

    def setStatus(self, status: str, subtitle: str | None = None):
        self._status = status
        if subtitle is not None:
            self.ui.subtitle.setText(subtitle)
        self._update_status_appearance()

    def _update_status_appearance(self):
        if not getattr(self, "has_number", True) or not self.ui.number.text():
            return
        if self._status == "done":
            self.ui.statusBadge.setVisible(True)
            self.ui.statusBadge.setText("✓ Done")
            self.ui.statusBadge.setStyleSheet(
                "background-color: #dcfce7; color: #15803d; border-radius: 9px; font-weight: 600; font-size: 10px; padding: 2px 8px; font-family: 'Segoe UI', 'Segoe UI Symbol', sans-serif;"
            )
            self.ui.number.setStyleSheet(
                "background-color: #1e293b; color: #ffffff; border-radius: 15px; font-weight: bold; font-size: 13px;"
            )
        elif self._status == "running":
            self.ui.statusBadge.setVisible(True)
            self.ui.statusBadge.setText("⏳ Running")
            self.ui.statusBadge.setStyleSheet(
                "background-color: #fef3c7; color: #b45309; border-radius: 9px; font-weight: 600; font-size: 10px; padding: 2px 8px; font-family: 'Segoe UI', 'Segoe UI Symbol', sans-serif;"
            )
            self.ui.number.setStyleSheet(
                "background-color: #b45309; color: #ffffff; border-radius: 15px; font-weight: bold; font-size: 13px;"
            )
        elif self._status == "locked":
            self.ui.statusBadge.setVisible(False)
            self.ui.number.setStyleSheet(
                "background-color: #94a3b8; color: #ffffff; border-radius: 15px; font-weight: bold; font-size: 13px;"
            )
        else:  # "ready"
            self.ui.statusBadge.setVisible(True)
            self.ui.statusBadge.setText("✓ Ready")
            self.ui.statusBadge.setStyleSheet(
                "background-color: #e0f2fe; color: #0284c7; border-radius: 9px; font-weight: 600; font-size: 10px; padding: 2px 8px; font-family: 'Segoe UI', 'Segoe UI Symbol', sans-serif;"
            )
            self.ui.number.setStyleSheet(
                "background-color: #0284c7; color: #ffffff; border-radius: 15px; font-weight: bold; font-size: 13px;"
            )


class DetectSettings(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.ui = Ui_DetectSettings()
        self.ui.setupUi(self)
        self._first_file = None
        self.ui.useGPU.toggled.connect(self.suggest_device)
        self.reset()

    def reset(self):
        self.ui.confidence.setValue(0.3)
        self.ui.mergeThreshold.setValue(0.2)
        self.ui.mergeMethod.setCurrentIndex(0)
        self._first_file = None
        self.ui.error.clear()
        self.ui.error.hide()
        self.refresh_inputs()

    def refresh_inputs(self):
        files = self.app.getInputFileList()
        first = files[0] if files else None
        self.ui.run.setEnabled(bool(files))
        self.ui.useGPU.setEnabled(bool(files))
        if first is not self._first_file:
            self._first_file = first
            self.suggest_device(True)
        if first is None:
            self.ui.deviceHint.setText("Add input files to check the device.")

    def suggest_device(self, use_gpu):
        if self._first_file is None:
            return
        try:
            _, _, available = self.app.stackSuggestBatchSize(self._first_file, use_gpu)
        except (OSError, ValueError) as error:
            self.ui.deviceHint.setText(f"Device suggestion unavailable: {error}")
            available = False
        else:
            self.ui.deviceHint.setText("GPU" if available else "CPU")
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(available))

    def values(self):
        for field in (self.ui.confidence, self.ui.mergeThreshold):
            if not field.hasAcceptableInput():
                self.ui.error.setText("Enter thresholds between 0 and 1.")
                self.ui.error.show()
                field.setFocus()
                return None
        self.ui.error.clear()
        self.ui.error.hide()
        return dict(confThreshold=self.ui.confidence.value(),
                    mergeThreshold=self.ui.mergeThreshold.value(),
                    mergeMethod=("NMS", "GREEDYNMM")[self.ui.mergeMethod.currentIndex()],
                    useGPU=self.ui.useGPU.isChecked())


class StackSettings(QWidget):
    def __init__(self, app, parent=None):
        super().__init__(parent)
        self.app = app
        self.ui = Ui_StackSettings()
        self.ui.setupUi(self)
        self._first_file = None
        self._has_masks = None
        self.ui.useGPU.toggled.connect(self.suggest_batch)
        self.ui.fade.currentIndexChanged.connect(lambda index: self.ui.fadeAmount.setEnabled(index != 0))
        self.reset()

    def reset(self):
        self.ui.fade.setCurrentIndex(3)
        self.ui.fadeAmount.setValue(20)
        self.ui.batchSize.setValue(1)
        self._has_masks = None
        self.set_has_masks(False)
        self._first_file = None
        self.ui.error.clear()
        self.ui.error.hide()
        self.refresh_inputs()

    def set_has_masks(self, available):
        self.ui.streaks.model().item(1).setEnabled(available)
        if available != self._has_masks:
            self.ui.streaks.setCurrentIndex(1 if available else 0)
            self._has_masks = available

    def refresh_inputs(self):
        files = self.app.getInputFileList()
        first = files[0] if files else None
        self.ui.run.setEnabled(bool(files))
        self.ui.useGPU.setEnabled(bool(files))
        if first is not self._first_file:
            self._first_file = first
            self.suggest_batch(True)
        if first is None:
            self.ui.memory.setText("Add input files for a batch suggestion.")

    def suggest_batch(self, use_gpu):
        if self._first_file is None:
            return
        try:
            size, memory, available = self.app.stackSuggestBatchSize(self._first_file, use_gpu)
        except (OSError, ValueError) as error:
            self.ui.memory.setText(f"Batch suggestion unavailable: {error}")
            available = False
        else:
            self.ui.batchSize.setValue(max(1, int(size)))
            device = "GPU" if available else "CPU"
            self.ui.memory.setText(f"Suggested batch: {size} · {memory / 1024**3:.2f} GB {device}")
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(available))

    def values(self):
        for field in (self.ui.batchSize, self.ui.fadeAmount):
            if not field.hasAcceptableInput():
                self.ui.error.setText("Enter a positive batch size and a fade amount from 0 to 100%.")
                self.ui.error.show()
                field.setFocus()
                return None
        self.ui.error.clear()
        self.ui.error.hide()
        mode = self.ui.fade.currentIndex()
        amount = self.ui.fadeAmount.value() / 100
        return dict(streaksRemoved=self.ui.streaks.currentIndex() == 1,
                    fade=mode != 0, fadeAmount=(amount if mode in (1, 3) else 0,
                                               amount if mode in (2, 3) else 0),
                    batchSize=self.ui.batchSize.value(), useGPU=self.ui.useGPU.isChecked())


class FillSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_FillSettings()
        self.ui.setupUi(self)


class ExportSettings(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_ExportSettings()
        self.ui.setupUi(self)
