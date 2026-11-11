"""Behavior for Designer-authored operation cards and settings."""

from types import SimpleNamespace
from typing import Final
from PySide6.QtCore import QElapsedTimer, QEvent, Qt, QSignalBlocker, QObject, Signal, Property
from PySide6.QtWidgets import QButtonGroup, QFrame, QSlider, QSpinBox, QWidget

PREVIEW_LONG_PRESS_MS: Final[int] = 250


def update_gpu_checkbox(checkbox, app, enabled=True):
    gpu_info = getattr(app, "gpuInfo", None)
    gpu_available = bool(gpu_info and gpu_info.get_gpu_present())
    if not gpu_available:
        with QSignalBlocker(checkbox):
            checkbox.setChecked(False)
    checkbox.setEnabled(enabled and gpu_available)


def toggle_advanced_settings(widget: QWidget, checked: bool) -> None:
    body = getattr(widget.ui, "advancedBody", None)
    if body is not None:
        body.setVisible(checked)
    toggle = getattr(widget.ui, "advancedToggle", None)
    if toggle is not None:
        toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
        toggle.setToolTip("Hide advanced settings" if checked else "Show advanced settings")
    p = widget
    while p is not None and not p.isWindow():
        p.updateGeometry()
        if isinstance(p, StepCard):
            break
        p = p.parentWidget()


def bind_percent_slider_spinbox(
    slider: QSlider,
    spinbox: QSpinBox,
    value_signal: Signal,
    settings_changed_signal: Signal,
    dragging_signal: Signal,
) -> None:
    """Synchronize a 0-100 slider and spinbox, deferring value commits while dragging."""

    def on_slider_changed(value: int) -> None:
        with QSignalBlocker(spinbox):
            spinbox.setValue(value)
        if slider.isSliderDown():
            dragging_signal.emit()
        else:
            value_signal.emit(float(value))
            settings_changed_signal.emit()

    def on_slider_released() -> None:
        value = slider.value()
        with QSignalBlocker(spinbox):
            spinbox.setValue(value)
        value_signal.emit(float(value))
        settings_changed_signal.emit()

    def on_spinbox_changed(value: int) -> None:
        with QSignalBlocker(slider):
            slider.setValue(value)
        value_signal.emit(float(value))
        settings_changed_signal.emit()

    slider.valueChanged.connect(on_slider_changed)
    slider.sliderPressed.connect(dragging_signal.emit)
    slider.sliderReleased.connect(on_slider_released)
    spinbox.valueChanged.connect(on_spinbox_changed)


def set_percent_slider_spinbox(slider: QSlider, spinbox: QSpinBox, value: float) -> None:
    """Set a synchronized 0-100 slider and spinbox without emitting change signals."""
    clamped = max(0, min(100, int(round(value))))
    with QSignalBlocker(slider), QSignalBlocker(spinbox):
        slider.setValue(clamped)
        spinbox.setValue(clamped)


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
    expansion_changed = Signal(bool)
    before_after_toggled = Signal(bool)

    def add_body(self, body):
        """Qt Designer custom-container page insertion API."""
        self.ui.contentLayout.addWidget(body)

    def _set_title(self, value):
        self.ui.toggle.setText(value.replace("&", "&&"))
        self.ui.toggle.setAccessibleName(value)

    def _set_step_number(self, value):
        self.has_number = bool(value and value > 0)
        if self.ui.number is not None:
            self.ui.number.setText(str(value) if self.has_number else ("!" if getattr(self, "_alert", False) else ""))
        if self.ui.statusBadge is not None:
            self.ui.statusBadge.setVisible(self.has_number)
        self._update_status_appearance()

    title = Property(str, lambda self: self.ui.toggle.text().replace("&&", "&"), _set_title)
    step_number = Property(
        int,
        lambda self: (
            int(self.ui.number.text()) if self.ui.number is not None and self.ui.number.text().isdigit() else 0
        ),
        _set_step_number,
    )
    is_expanded = Property(bool, lambda self: self.ui.toggle.isChecked(), lambda self, value: self.setExpanded(value))
    subtitle = Property(str, lambda self: self.ui.subtitle.text(), lambda self, value: self.setSubtitle(value))
    alert = Property(bool, lambda self: getattr(self, "_alert", False), lambda self, value: self.set_alert(value))
    before_after_enabled = Property(
        bool,
        lambda self: getattr(self, "_before_after_enabled", False),
        lambda self, value: self.set_before_after_enabled(value),
    )

    def __init__(self, title="Step", body=None, number=None, expanded=False, parent=None, ui=None, prefix=None):
        if isinstance(title, QWidget) and parent is None:
            parent = title
            title = "Step"
        super().__init__(parent)
        self.has_number = number is not None
        self._status = "ready"
        self._alert = False
        self._before_after_enabled = False
        self._showing_before = False
        self._press_timer = QElapsedTimer()
        self._press_active = False
        if ui is not None and prefix is not None:
            self.frame = getattr(ui, prefix)
            self.ui = SimpleNamespace(
                headerWidget=getattr(ui, f"{prefix}Header"),
                number=getattr(ui, f"{prefix}Number", None),
                toggle=getattr(ui, f"{prefix}Toggle"),
                statusBadge=getattr(ui, f"{prefix}StatusBadge", None),
                previewToggle=getattr(ui, f"{prefix}PreviewToggle", None),
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

        self._set_title(title)
        if self.ui.number is not None:
            self.ui.number.setVisible(True)
            self.ui.number.setText(str(number) if number is not None else "")
        if not self.has_number and self.ui.statusBadge is not None:
            self.ui.statusBadge.setVisible(False)
        if self.ui.previewToggle is not None:
            self.ui.previewToggle.setVisible(False)
            self.ui.previewToggle.installEventFilter(self)
            self.ui.previewToggle.pressed.connect(self._on_preview_pressed)
            self.ui.previewToggle.toggled.connect(self._on_preview_toggled)
            self.ui.previewToggle.released.connect(self._on_preview_released)
            self._update_preview_visual(False)
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

    def _sync_collapsed_height(self) -> None:
        if not self.ui.toggle.isChecked():
            target = self.frame if getattr(self, "frame", None) is not None else self
            target.setFixedHeight(self.ui.headerWidget.sizeHint().height() + 2)
            target.updateGeometry()

    def setExpanded(self, expanded):
        expanded = bool(expanded and self._status != "locked")
        with QSignalBlocker(self.ui.toggle):
            self.ui.toggle.setChecked(expanded)
        self.ui.chevron.setProperty("expanded", expanded)
        self.ui.chevron.style().unpolish(self.ui.chevron)
        self.ui.chevron.style().polish(self.ui.chevron)
        self.ui.body.setVisible(expanded)
        self.reset_before_after(emit=True)
        self._update_preview_visibility()
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
        self.expansion_changed.emit(expanded)

    def setSubtitle(self, text):
        self.ui.subtitle.setText(text)
        self._sync_collapsed_height()

    @property
    def status(self) -> str:
        return self._status

    def setStatus(self, status: str, subtitle: str | None = None):
        self._status = status
        if subtitle is not None:
            self.ui.subtitle.setText(subtitle)
        self._update_status_appearance()
        self.ui.toggle.setEnabled(status != "locked")
        if status == "locked":
            self.setExpanded(False)
        self._sync_collapsed_height()

    def set_before_after_enabled(self, enabled: bool = True) -> None:
        """Enable or disable the before/after preview chip on this step card."""
        enabled = bool(enabled)
        if self._before_after_enabled == enabled:
            return
        self._before_after_enabled = enabled
        if not enabled:
            self.reset_before_after(emit=False)
        self._update_status_appearance()
        self._sync_collapsed_height()

    def is_showing_before(self) -> bool:
        """Return True when the before/after preview toggle is showing the before state."""
        return self._showing_before

    def reset_before_after(self, emit: bool = False) -> None:
        """Return the before/after toggle to its default 'after' state."""
        if self.ui.previewToggle is not None:
            with QSignalBlocker(self.ui.previewToggle):
                self.ui.previewToggle.setChecked(False)
            self._update_preview_visual(False)
        changed = self._showing_before
        self._showing_before = False
        if emit and changed:
            self.before_after_toggled.emit(False)

    def _update_preview_visual(self, showing_before: bool) -> None:
        toggle = self.ui.previewToggle
        if toggle is None:
            return
        toggle.setToolTip(
            "Showing before — click for after" if showing_before else "Compare before and after preview"
        )
        if toggle.property("showingBefore") != showing_before:
            toggle.setProperty("showingBefore", showing_before)
            toggle.style().unpolish(toggle)
            toggle.style().polish(toggle)
            toggle.update()

    def _set_showing_before(self, showing_before: bool) -> None:
        showing_before = bool(showing_before)
        self._update_preview_visual(showing_before)
        if self._showing_before == showing_before:
            return
        self._showing_before = showing_before
        self.before_after_toggled.emit(showing_before)

    def _on_preview_pressed(self) -> None:
        self._set_showing_before(True)
        if self._press_active:
            # Exclude synchronous preview work on press so slow image loads
            # do not turn a short click into a long press.
            self._press_timer.restart()

    def _on_preview_toggled(self, checked: bool) -> None:
        self._set_showing_before(checked)

    def _on_preview_released(self) -> None:
        if self.ui.previewToggle is not None:
            self._set_showing_before(self.ui.previewToggle.isChecked())

    def eventFilter(self, obj, event):
        if obj is getattr(self.ui, "previewToggle", None):
            event_type = event.type()
            if event_type in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonDblClick):
                if event.button() == Qt.LeftButton:
                    self._press_timer.start()
                    self._press_active = True
            elif event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.LeftButton:
                is_long_press = (
                    self._press_active
                    and self._press_timer.isValid()
                    and self._press_timer.elapsed() >= PREVIEW_LONG_PRESS_MS
                )
                self._press_active = False
                if is_long_press:
                    with QSignalBlocker(obj):
                        obj.setDown(False)
                        obj.setChecked(False)
                    self._set_showing_before(False)
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def set_alert(self, alert: bool = True) -> None:
        alert = bool(alert)
        if getattr(self, "_alert", False) == alert:
            return
        self._alert = alert
        self._update_status_appearance()

    setAlert = set_alert

    def _update_status_appearance(self):
        # Appearance lives in the forms; only the current state changes here.
        if self.has_number:
            status = self._status
        else:
            status = "ready" if getattr(self, "_alert", False) else "neutral"
            if self.ui.number is not None:
                self.ui.number.setText("!" if getattr(self, "_alert", False) else "")

        for widget in (self.ui.number, self.ui.statusBadge):
            if widget is not None and widget.property("stepStatus") != status:
                widget.setProperty("stepStatus", status)
                widget.style().unpolish(widget)
                widget.style().polish(widget)
                widget.update()
        if self.ui.statusBadge is not None:
            self.ui.statusBadge.setVisible(self.has_number and status != "locked")
            if self.has_number:
                self.ui.statusBadge.setText(
                    {
                        "done": "Done",
                        "running": "Running",
                    }.get(status, "Ready")
                )
        self._update_preview_visibility()

    def _update_preview_visibility(self) -> None:
        if self.ui.previewToggle is None:
            return
        status = self._status if self.has_number else "neutral"
        preview_visible = bool(
            self._before_after_enabled and self.has_number and status == "done" and self.ui.toggle.isChecked()
        )
        if not preview_visible:
            self.reset_before_after(emit=False)
        self.ui.previewToggle.setVisible(preview_visible)


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
        self.ui.confidence.setValue(0.3)
        self.ui.mergeThreshold.setValue(0.2)
        self.ui.mergeMethod.setCurrentIndex(1)
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
        if self._first_file is None or not self.app or not hasattr(self.app, "stackSuggestBatchSize"):
            return
        try:
            _, _, available = self.app.stackSuggestBatchSize(self._first_file, use_gpu)
        except (OSError, ValueError):
            available = False
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
            mergeMethod=("NMS", "GREEDYNMM")[self.ui.mergeMethod.currentIndex()],
            useGPU=self.ui.useGPU.isChecked(),
        )


class StackSettings(QWidget):
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
        self.ui.fade.currentIndexChanged.connect(lambda index: self.ui.fadeAmount.setEnabled(index != 0))
        self.reset()

    def _toggle_advanced(self, checked):
        toggle_advanced_settings(self, checked)

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
            self.ui.batchSize.setValue(max(1, int(size)))
            device = "GPU" if available else "CPU"
            self.ui.memory.setText(f"Suggested batch: {size} · {memory / 1024**3:.2f} GB {device}")
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
        amount = self.ui.fadeAmount.value() / 100
        return dict(
            streaksRemoved=self.ui.streaks.currentIndex() == 1,
            fade=mode != 0,
            fadeAmount=(amount if mode in (1, 3) else 0, amount if mode in (2, 3) else 0),
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
                training=getattr(ui, "exportTraining", getattr(ui, "training", None)),
                contribute=getattr(ui, "contribute", getattr(ui, "contributeTraining", None)),
            )
        else:
            self.ui = Ui_ReviewSettings()
            self.ui.setupUi(self)
            if not hasattr(self.ui, "training"):
                self.ui.training = None
            if not hasattr(self.ui, "contribute"):
                self.ui.contribute = None

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
