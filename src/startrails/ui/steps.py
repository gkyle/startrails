"""Shared UI helpers and StepCard widget for Designer-authored operation cards."""

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
    """Synchronize a percent slider and spinbox, deferring value commits while dragging."""

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
    """Set a percent slider and spinbox without emitting change signals."""
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

                    def isEnabled(self):
                        return self._btn.isEnabled()

                return _ItemAdapter(self._buttons[index])

        return _ModelAdapter(self.buttons)


from .ui_step import Ui_StepCard


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
