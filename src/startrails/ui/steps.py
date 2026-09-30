"""Behavior for Designer-authored operation cards and settings."""
from types import SimpleNamespace
from PySide6.QtCore import Qt, QSignalBlocker, QObject, Signal
from PySide6.QtWidgets import QFrame, QWidget, QButtonGroup


class SegmentedButtonGroup(QObject):
    currentIndexChanged = Signal(int)

    def __init__(self, buttons, parent=None):
        super().__init__(parent)
        self.buttons = list(buttons)
        self.group = QButtonGroup(parent or self)
        self.group.setExclusive(True)
        for i, btn in enumerate(self.buttons):
            self.group.addButton(btn, i)
        self.group.idClicked.connect(self._on_clicked)

    def _on_clicked(self, idx):
        self.currentIndexChanged.emit(idx)

    def currentIndex(self):
        return self.group.checkedId()

    def setCurrentIndex(self, index):
        if 0 <= index < len(self.buttons):
            old = self.group.checkedId()
            self.buttons[index].setChecked(True)
            if old != index:
                self.currentIndexChanged.emit(index)

    def setItemEnabled(self, index, enabled):
        if 0 <= index < len(self.buttons):
            self.buttons[index].setEnabled(enabled)

    def model(self):
        class _ModelAdapter:
            def __init__(self, buttons):
                self._buttons = buttons
            def item(self, index):
                class _ItemAdapter:
                    def __init__(self, btn):
                        self._btn = btn
                    def setEnabled(self, val):
                        self._btn.setEnabled(val)
                return _ItemAdapter(self._buttons[index])
        return _ModelAdapter(self.buttons)

from .ui_step import Ui_StepCard
from .ui_step_detect_streaks import Ui_DetectSettings
from .ui_step_stack_images import Ui_StackSettings
from .ui_step_fill_gaps import Ui_FillSettings
from .ui_step_export_artifacts import Ui_ExportSettings
from .ui_step_review_detections import Ui_ReviewSettings
from .ui_step_additional_tools import Ui_ToolsSettings


class StepCard(QFrame):
    expanded = Signal()

    def __init__(self, title, body, number=None, expanded=False, parent=None, ui=None, prefix=None):
        super().__init__(parent)
        self.has_number = number is not None
        self._status = "ready"
        if ui is not None and prefix is not None:
            self.frame = getattr(ui, prefix)
            self.ui = SimpleNamespace(
                headerWidget=getattr(ui, f"{prefix}Header"),
                number=getattr(ui, f"{prefix}Number", None),
                toggle=getattr(ui, f"{prefix}Toggle"),
                statusBadge=getattr(ui, f"{prefix}StatusBadge", None),
                subtitle=getattr(ui, f"{prefix}Subtitle"),
                chevron=getattr(ui, f"{prefix}Chevron"),
                body=getattr(ui, f"{prefix}Body"),
                contentLayout=getattr(ui, f"{prefix}BodyLayout", None),
            )
        else:
            self.frame = self
            self.ui = Ui_StepCard()
            self.ui.setupUi(self)
            if body is not None:
                self.ui.contentLayout.addWidget(body)

        self.ui.toggle.setText(title)
        self.ui.toggle.setAccessibleName(title)
        if self.ui.number is not None:
            self.ui.number.setVisible(True)
            self.ui.number.setText(str(number or ""))
        if not self.has_number and self.ui.statusBadge is not None:
            self.ui.statusBadge.setVisible(False)
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
        target = self.frame if getattr(self, "frame", None) is not None else self
        if not expanded:
            target.setFixedHeight(self.ui.headerWidget.sizeHint().height() + 2)
        else:
            target.setMaximumHeight(16777215)
            target.setMinimumHeight(0)
            target.adjustSize()
        target.updateGeometry()
        if expanded:
            self.expanded.emit()

    def setSubtitle(self, text):
        self.ui.subtitle.setText(text)

    def setStatus(self, status: str, subtitle: str | None = None):
        self._status = status
        if subtitle is not None:
            self.ui.subtitle.setText(subtitle)
        self._update_status_appearance()

    def _update_status_appearance(self):
        # Appearance lives in the forms; only the current state changes here.
        status = self._status if self.has_number else "neutral"
        for widget in (self.ui.number, self.ui.statusBadge):
            if widget is not None and widget.property("stepStatus") != status:
                widget.setProperty("stepStatus", status)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
        if self.ui.statusBadge is not None:
            self.ui.statusBadge.setVisible(self.has_number and status != "locked")
            if self.has_number:
                self.ui.statusBadge.setText({
                    "done": "\u2713 Done",
                    "running": "\u23f3 Running",
                }.get(status, "\u2713 Ready"))


class DetectSettings(QWidget):
    def __init__(self, app, parent=None, ui=None):
        super().__init__(parent)
        self.app = app
        if ui is not None:
            if hasattr(ui, "detectMergeNMS") and hasattr(ui, "detectMergeNMM"):
                merge_method = SegmentedButtonGroup(
                    [ui.detectMergeNMS, ui.detectMergeNMM], parent=self
                )
            else:
                merge_method = getattr(ui, "detectMergeMethod", None)

            advanced_toggle = getattr(ui, "detectAdvancedToggle", getattr(ui, "advancedToggle", None))
            advanced_body = getattr(ui, "detectAdvancedBody", getattr(ui, "advancedBody", None))

            self.ui = SimpleNamespace(
                confidenceLabel=ui.detectConfidenceLabel,
                confidence=ui.detectConfidence,
                mergeLabel=ui.detectMergeLabel,
                mergeMethod=merge_method,
                thresholdLabel=ui.detectThresholdLabel,
                mergeThreshold=ui.detectMergeThreshold,
                useGPU=ui.detectUseGPU,
                error=ui.detectError,
                run=ui.detectRun,
                advancedToggle=advanced_toggle,
                advancedBody=advanced_body,
            )
        else:
            self.ui = Ui_DetectSettings()
            self.ui.setupUi(self)
            if hasattr(self.ui, "detectMergeNMS") and hasattr(self.ui, "detectMergeNMM"):
                self.ui.mergeMethod = SegmentedButtonGroup(
                    [self.ui.detectMergeNMS, self.ui.detectMergeNMM], parent=self
                )
        self._first_file = None
        if getattr(self.ui, "advancedToggle", None) is not None:
            self.ui.advancedToggle.toggled.connect(self._toggle_advanced)
            self.ui.advancedToggle.setChecked(False)
            self._toggle_advanced(False)
        self.ui.useGPU.toggled.connect(self.suggest_device)
        self.reset()

    def _toggle_advanced(self, checked):
        body = getattr(self.ui, "advancedBody", None)
        if body is not None:
            body.setVisible(checked)
        toggle = getattr(self.ui, "advancedToggle", None)
        if toggle is not None:
            toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
            toggle.setToolTip("Hide advanced settings" if checked else "Show advanced settings")
        self.updateGeometry()
        if body is not None and body.parentWidget() is not None:
            body.parentWidget().updateGeometry()
            body.parentWidget().adjustSize()

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

    def suggest_device(self, use_gpu):
        if self._first_file is None:
            return
        try:
            _, _, available = self.app.stackSuggestBatchSize(self._first_file, use_gpu)
        except (OSError, ValueError):
            available = False
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
    def __init__(self, app, parent=None, ui=None):
        super().__init__(parent)
        self.app = app
        if ui is not None:
            if hasattr(ui, "stackStreaksKeep") and hasattr(ui, "stackStreaksRemove"):
                streaks_widget = SegmentedButtonGroup(
                    [ui.stackStreaksKeep, ui.stackStreaksRemove], parent=self
                )
            else:
                streaks_widget = getattr(ui, "stackStreaks", None)

            if hasattr(ui, "stackFadeOff") and hasattr(ui, "stackFadeBoth"):
                fade_widget = SegmentedButtonGroup(
                    [ui.stackFadeOff, ui.stackFadeStart, ui.stackFadeEnd, ui.stackFadeBoth], parent=self
                )
            else:
                fade_widget = getattr(ui, "stackFade", None)

            advanced_toggle = getattr(ui, "stackAdvancedToggle", getattr(ui, "advancedToggle", None))
            advanced_body = getattr(ui, "stackAdvancedBody", getattr(ui, "advancedBody", None))

            self.ui = SimpleNamespace(
                methodLabel=ui.stackMethodLabel,
                method=ui.stackMethod,
                streaksLabel=ui.stackStreaksLabel,
                streaks=streaks_widget,
                fadeLabel=ui.stackFadeLabel,
                fade=fade_widget,
                amountLabel=ui.stackAmountLabel,
                fadeAmount=ui.stackFadeAmount,
                useGPU=ui.stackUseGPU,
                batchLabel=ui.stackBatchLabel,
                batchSize=ui.stackBatchSize,
                memory=ui.stackMemory,
                error=ui.stackError,
                run=ui.stackRun,
                advancedToggle=advanced_toggle,
                advancedBody=advanced_body,
            )
        else:
            self.ui = Ui_StackSettings()
            self.ui.setupUi(self)
            if hasattr(self.ui, "stackStreaksKeep") and hasattr(self.ui, "stackStreaksRemove"):
                self.ui.streaks = SegmentedButtonGroup(
                    [self.ui.stackStreaksKeep, self.ui.stackStreaksRemove], parent=self
                )
            if hasattr(self.ui, "stackFadeOff") and hasattr(self.ui, "stackFadeBoth"):
                self.ui.fade = SegmentedButtonGroup(
                    [self.ui.stackFadeOff, self.ui.stackFadeStart, self.ui.stackFadeEnd, self.ui.stackFadeBoth], parent=self
                )
        self._first_file = None
        self._has_masks = None
        if getattr(self.ui, "advancedToggle", None) is not None:
            self.ui.advancedToggle.toggled.connect(self._toggle_advanced)
            self.ui.advancedToggle.setChecked(False)
            self._toggle_advanced(False)
        self.ui.useGPU.toggled.connect(self.suggest_batch)
        self.ui.fade.currentIndexChanged.connect(lambda index: self.ui.fadeAmount.setEnabled(index != 0))
        self.reset()

    def _toggle_advanced(self, checked):
        body = getattr(self.ui, "advancedBody", None)
        if body is not None:
            body.setVisible(checked)
        toggle = getattr(self.ui, "advancedToggle", None)
        if toggle is not None:
            toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
            toggle.setToolTip("Hide advanced settings" if checked else "Show advanced settings")
        self.updateGeometry()
        if body is not None and body.parentWidget() is not None:
            body.parentWidget().updateGeometry()
            body.parentWidget().adjustSize()

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
    def __init__(self, parent=None, ui=None):
        super().__init__(parent)
        if ui is not None:
            self.ui = SimpleNamespace(
                target=ui.fillTarget,
                run=ui.fillRun,
            )
        else:
            self.ui = Ui_FillSettings()
            self.ui.setupUi(self)


class ReviewSettings(QWidget):
    def __init__(self, app=None, parent=None, ui=None):
        super().__init__(parent)
        self.app = app
        if ui is not None:
            self.ui = SimpleNamespace(
                statAuto=getattr(ui, "reviewStatAuto", None),
                statAutoNum=getattr(ui, "reviewStatAutoNum", None),
                statManual=getattr(ui, "reviewStatManual", None),
                statManualNum=getattr(ui, "reviewStatManualNum", None),
                statDeleted=getattr(ui, "reviewStatDeleted", None),
                statDeletedNum=getattr(ui, "reviewStatDeletedNum", None),
                showDeletedMasks=getattr(ui, "exportShowDeletedMasks", getattr(ui, "showDeletedMasks", None)),
                findBrightest=getattr(ui, "findBrightest", None),
                training=getattr(ui, "exportTraining", getattr(ui, "training", None)),
            )
        else:
            self.ui = Ui_ReviewSettings()
            self.ui.setupUi(self)

    def set_counts(self, auto: int, manual: int, deleted: int):
        if getattr(self.ui, "statAutoNum", None) is not None:
            self.ui.statAutoNum.setText(str(auto))
        if getattr(self.ui, "statManualNum", None) is not None:
            self.ui.statManualNum.setText(str(manual))
        if getattr(self.ui, "statDeletedNum", None) is not None:
            self.ui.statDeletedNum.setText(str(deleted))

    def reset(self):
        self.set_counts(0, 0, 0)
        if getattr(self.ui, "showDeletedMasks", None) is not None:
            with QSignalBlocker(self.ui.showDeletedMasks):
                self.ui.showDeletedMasks.setChecked(False)


class AdditionalToolsSettings(QWidget):
    def __init__(self, parent=None, ui=None):
        super().__init__(parent)
        if ui is not None:
            self.ui = SimpleNamespace(masks=ui.exportMasks)
        else:
            self.ui = Ui_ToolsSettings()
            self.ui.setupUi(self)


class ExportSettings(ReviewSettings):
    """Backward-compatible wrapper for review/export settings."""
    def __init__(self, parent=None, ui=None):
        super().__init__(app=None, parent=parent, ui=ui)
