"""Startrails-specific step settings widgets."""

from types import SimpleNamespace
from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget
from startrails.lib.gpu import resolve_torch_device
from startrails.lib.project_startrails import Project
from startrails.lib.startrails.defaults import (
    DEFAULT_MERGE_METHOD_INDEX,
    FADE_MODE_BOTH,
    FADE_MODE_END,
    FADE_MODE_OFF,
    FADE_MODE_START,
    MERGE_METHODS,
    PERCENT_SCALE,
    STARTRAILS_DEFAULTS,
    STREAKS_KEEP_INDEX,
    STREAKS_REMOVE_INDEX,
)
from .steps import SegmentedButtonGroup, toggle_advanced_settings, update_gpu_checkbox
from .ui_step_startrails_additional_tools import Ui_ToolsSettings
from .ui_step_startrails_detect_streaks import Ui_DetectSettings
from .ui_step_startrails_fill_gaps import Ui_FillSettings
from .ui_step_startrails_review_detections import Ui_ReviewSettings
from .ui_step_startrails_stack_images import Ui_StackSettings


class DetectSettings(QWidget):
    def __init__(self, app=None, parent=None, ui=None):
        if isinstance(app, QWidget) and parent is None:
            parent = app
            app = None
        super().__init__(parent)
        self.app = app
        if ui is not None:
            if hasattr(ui, "detectMergeNMS") and hasattr(ui, "detectMergeNMM"):
                merge_method = SegmentedButtonGroup([ui.detectMergeNMS, ui.detectMergeNMM], parent=self)
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
        toggle_advanced_settings(self, checked)

    def reset(self):
        self.ui.confidence.setValue(STARTRAILS_DEFAULTS.conf_threshold)
        self.ui.mergeThreshold.setValue(STARTRAILS_DEFAULTS.merge_threshold)
        self.ui.mergeMethod.setCurrentIndex(DEFAULT_MERGE_METHOD_INDEX)
        self._first_file = None
        self.ui.error.clear()
        self.ui.error.hide()
        self.refresh_inputs()

    def refresh_inputs(self):
        files = self.app.getInputFileList() if (self.app and hasattr(self.app, "getInputFileList")) else []
        first = files[0] if files else None
        self.ui.run.setEnabled(bool(files))
        update_gpu_checkbox(self.ui.useGPU, self.app, enabled=bool(files))
        if first is not self._first_file:
            self._first_file = first
            self.suggest_device(True)

    def suggest_device(self, use_gpu):
        if self._first_file is None:
            return
        available = resolve_torch_device(use_gpu=use_gpu).type != "cpu"
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(available) and self.ui.useGPU.isEnabled())

    def values(self):
        for field in (self.ui.confidence, self.ui.mergeThreshold):
            if not field.hasAcceptableInput():
                self.ui.error.setText("Enter thresholds between 0 and 1.")
                self.ui.error.show()
                field.setFocus()
                return None
        self.ui.error.clear()
        self.ui.error.hide()
        return dict(
            confThreshold=self.ui.confidence.value(),
            mergeThreshold=self.ui.mergeThreshold.value(),
            mergeMethod=MERGE_METHODS[self.ui.mergeMethod.currentIndex()],
            useGPU=self.ui.useGPU.isChecked(),
        )


class StackSettings(QWidget):
    settings_changed = Signal()

    def __init__(self, app=None, parent=None, ui=None):
        if isinstance(app, QWidget) and parent is None:
            parent = app
            app = None
        super().__init__(parent)
        self.app = app
        if ui is not None:
            if hasattr(ui, "stackStreaksKeep") and hasattr(ui, "stackStreaksRemove"):
                streaks_widget = SegmentedButtonGroup([ui.stackStreaksKeep, ui.stackStreaksRemove], parent=self)
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
                    [self.ui.stackFadeOff, self.ui.stackFadeStart, self.ui.stackFadeEnd, self.ui.stackFadeBoth],
                    parent=self,
                )
        for attr in (
            "run",
            "advancedToggle",
            "advancedBody",
            "useGPU",
            "useGPULabel",
            "batchSize",
            "batchLabel",
            "fadeAmount",
            "amountLabel",
            "memory",
            "error",
            "method",
            "methodLabel",
            "streaksLabel",
            "fadeLabel",
            "streaks",
            "fade",
        ):
            stack_attr = f"stack{attr[0].upper()}{attr[1:]}"
            if hasattr(self.ui, stack_attr) and not hasattr(self.ui, attr):
                setattr(self.ui, attr, getattr(self.ui, stack_attr))
            elif hasattr(self.ui, attr) and not hasattr(self.ui, stack_attr):
                setattr(self.ui, stack_attr, getattr(self.ui, attr))
        self._first_file = None
        self._has_masks = None
        if getattr(self.ui, "advancedToggle", None) is not None:
            self.ui.advancedToggle.toggled.connect(self._toggle_advanced)
            self.ui.advancedToggle.setChecked(False)
            self._toggle_advanced(False)
        self.ui.useGPU.toggled.connect(self.suggest_batch)
        self.ui.fade.currentIndexChanged.connect(lambda index: self.ui.fadeAmount.setEnabled(index != FADE_MODE_OFF))
        self.reset()
        self.ui.fade.currentIndexChanged.connect(self._on_setting_changed)
        self.ui.fadeAmount.valueChanged.connect(self._on_setting_changed)
        self.ui.batchSize.valueChanged.connect(self._on_setting_changed)
        self.ui.useGPU.toggled.connect(self._on_setting_changed)
        if hasattr(self.ui, "streaks"):
            if hasattr(self.ui.streaks, "currentIndexChanged"):
                self.ui.streaks.currentIndexChanged.connect(self._on_setting_changed)

    def _toggle_advanced(self, checked):
        toggle_advanced_settings(self, checked)

    def _on_setting_changed(self, *args):
        self._persist_to_project()
        self.settings_changed.emit()

    def _persist_to_project(self):
        project = getattr(self.app, "project", None)
        if project is None or not hasattr(project, "fadeMode"):
            return
        project.fadeMode = self.ui.fade.currentIndex()
        project.fadeAmount = self.ui.fadeAmount.value()
        project.batchSize = self.ui.batchSize.value()
        project.useGPU = self.ui.useGPU.isChecked()
        if hasattr(self.ui, "streaks") and self.ui.streaks is not None and self._has_masks:
            project.streaksRemoved = (self.ui.streaks.currentIndex() == STREAKS_REMOVE_INDEX)

    def set_from_project(self):
        project = getattr(self.app, "project", None)
        source = project if project is not None else Project()

        with QSignalBlocker(self.ui.fade):
            self.ui.fade.setCurrentIndex(int(source.fadeMode))
        self.ui.fadeAmount.setEnabled(self.ui.fade.currentIndex() != FADE_MODE_OFF)
        with QSignalBlocker(self.ui.fadeAmount):
            self.ui.fadeAmount.setValue(int(source.fadeAmount))
        with QSignalBlocker(self.ui.batchSize):
            self.ui.batchSize.setValue(int(source.batchSize))
        with QSignalBlocker(self.ui.useGPU):
            self.ui.useGPU.setChecked(bool(source.useGPU))

        if hasattr(self.ui, "streaks") and self.ui.streaks is not None:
            saved_streaks = source.streaksRemoved
            with QSignalBlocker(self.ui.streaks):
                if saved_streaks is None:
                    target_idx = STREAKS_REMOVE_INDEX if self._has_masks else STREAKS_KEEP_INDEX
                else:
                    target_idx = STREAKS_REMOVE_INDEX if (saved_streaks and self._has_masks) else STREAKS_KEEP_INDEX
                self.ui.streaks.setCurrentIndex(target_idx)

    def reset(self):
        self._has_masks = None
        self.set_has_masks(False)
        self._first_file = None
        self.ui.error.clear()
        self.ui.error.hide()
        self.set_from_project()
        self.refresh_inputs()

    def set_has_masks(self, available):
        self.ui.streaks.model().item(STREAKS_REMOVE_INDEX).setEnabled(available)
        project = getattr(self.app, "project", None)
        source = project if project is not None else Project()
        saved_streaks = source.streaksRemoved
        if available != self._has_masks:
            self._has_masks = available
            if hasattr(self.ui, "streaks") and self.ui.streaks is not None:
                if saved_streaks is None:
                    target_idx = STREAKS_REMOVE_INDEX if available else STREAKS_KEEP_INDEX
                else:
                    target_idx = STREAKS_REMOVE_INDEX if (available and saved_streaks) else STREAKS_KEEP_INDEX
                with QSignalBlocker(self.ui.streaks):
                    self.ui.streaks.setCurrentIndex(target_idx)

    def set_streaks_removed(self, removed: bool = True):
        if hasattr(self.ui, "streaks") and self.ui.streaks is not None:
            target_idx = STREAKS_REMOVE_INDEX if (removed and bool(self._has_masks)) else STREAKS_KEEP_INDEX
            if self.ui.streaks.currentIndex() != target_idx:
                self.ui.streaks.setCurrentIndex(target_idx)
            else:
                self._on_setting_changed()

    def refresh_inputs(self):
        files = self.app.getInputFileList() if (self.app and hasattr(self.app, "getInputFileList")) else []
        first = files[0] if files else None
        self.ui.run.setEnabled(bool(files))
        update_gpu_checkbox(self.ui.useGPU, self.app, enabled=bool(files))
        if first is not self._first_file:
            self._first_file = first
            self.suggest_batch(True)
        if first is None:
            self.ui.memory.setText("Add input files for a batch suggestion.")

    def suggest_batch(self, use_gpu):
        if self._first_file is None or not self.app or not hasattr(self.app, "stackSuggestBatchSize"):
            return
        try:
            size, memory, available = self.app.stackSuggestBatchSize(self._first_file, use_gpu)
        except (OSError, ValueError) as error:
            self.ui.memory.setText(f"Batch suggestion unavailable: {error}")
            available = False
        else:
            device = "GPU" if available else "CPU"
            self.ui.memory.setText(f"Suggested batch: {size} · {memory / 1024**3:.2f} GB {device}")
            project = getattr(self.app, "project", None)
            if project is None:
                with QSignalBlocker(self.ui.batchSize):
                    self.ui.batchSize.setValue(max(1, int(size)))
        if not available:
            with QSignalBlocker(self.ui.useGPU):
                self.ui.useGPU.setChecked(False)
        elif getattr(self.app, "project", None) is None:
            with QSignalBlocker(self.ui.useGPU):
                self.ui.useGPU.setChecked(bool(available) and self.ui.useGPU.isEnabled())

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
        amount = self.ui.fadeAmount.value() / PERCENT_SCALE
        return dict(
            streaksRemoved=self.ui.streaks.currentIndex() == STREAKS_REMOVE_INDEX,
            fade=mode != FADE_MODE_OFF,
            fadeAmount=(
                amount if mode in (FADE_MODE_START, FADE_MODE_BOTH) else 0.0,
                amount if mode in (FADE_MODE_END, FADE_MODE_BOTH) else 0.0,
            ),
            batchSize=self.ui.batchSize.value(),
            useGPU=self.ui.useGPU.isChecked(),
        )


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
        if isinstance(app, QWidget) and parent is None:
            parent = app
            app = None
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
                nextSource=ui.nextSource,
                backToStack=ui.backToStack,
                sourceLookupStatus=ui.sourceLookupStatus,
                pendingCorrectionsNotice=getattr(ui, "pendingCorrectionsNotice", None),
                training=getattr(ui, "exportTraining", getattr(ui, "training", None)),
                contribute=getattr(ui, "contribute", getattr(ui, "contributeTraining", None)),
            )
        else:
            self.ui = Ui_ReviewSettings()
            self.ui.setupUi(self)
            if not hasattr(self.ui, "pendingCorrectionsNotice"):
                self.ui.pendingCorrectionsNotice = None
            if not hasattr(self.ui, "training"):
                self.ui.training = None
            if not hasattr(self.ui, "contribute"):
                self.ui.contribute = None
        self.set_pending_notice_visible(False)

    def set_pending_notice_visible(self, visible: bool):
        notice = getattr(self.ui, "pendingCorrectionsNotice", None)
        if notice is not None:
            notice.setVisible(bool(visible))

    def set_counts(self, auto: int, manual: int, deleted: int):
        if getattr(self.ui, "statAutoNum", None) is not None:
            self.ui.statAutoNum.setText(str(auto))
        if getattr(self.ui, "statManualNum", None) is not None:
            self.ui.statManualNum.setText(str(manual))
        if getattr(self.ui, "statDeletedNum", None) is not None:
            self.ui.statDeletedNum.setText(str(deleted))

    def reset(self):
        self.set_counts(0, 0, 0)
        self.set_pending_notice_visible(False)
        if getattr(self.ui, "showDeletedMasks", None) is not None:
            with QSignalBlocker(self.ui.showDeletedMasks):
                self.ui.showDeletedMasks.setChecked(False)


class AdditionalToolsSettings(QWidget):
    def __init__(self, parent=None, ui=None):
        super().__init__(parent)
        if ui is not None:
            self.ui = SimpleNamespace(
                masks=getattr(ui, "exportMasks", getattr(ui, "masks", None)),
                contribute=getattr(
                    ui, "contribute", getattr(ui, "contributeTraining", getattr(ui, "pushButton_contribute", None))
                ),
                training=getattr(
                    ui, "training", getattr(ui, "exportTraining", getattr(ui, "pushButton_exportTraining", None))
                ),
                showDeletedMasks=getattr(ui, "exportShowDeletedMasks", getattr(ui, "showDeletedMasks", None)),
            )
        else:
            self.ui = Ui_ToolsSettings()
            self.ui.setupUi(self)


class ExportSettings(ReviewSettings):
    """Backward-compatible wrapper for review/export settings."""

    def __init__(self, parent=None, ui=None):
        super().__init__(app=None, parent=parent, ui=ui)

