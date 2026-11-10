"""Settings and controls widget for Step 2: Separate Stars."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget

from startrails.lib.finish.nox import DEFAULT_STRIDE, validate_separation_stride
from startrails.lib.project_finish import FinishProject
from .ui_step_separate import Ui_SeparateStarsSettings


class SeparateStarsSettings(QWidget):
    """Card body widget for Separate Stars handling Nox inference settings."""

    run_separation_requested = Signal()
    stride_changed = Signal(int)
    chroma_postfilter_changed = Signal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ui = Ui_SeparateStarsSettings()
        self.ui.setupUi(self)

        # Direct attribute aliases for callers and tests
        self.unconfigured_box = self.ui.unconfigured_box
        self.configured_box = self.ui.configured_box
        self.lbl_unconf_msg = self.ui.lbl_unconf_msg
        self.combo_stride = self.ui.combo_stride
        self.lbl_chroma_postfilter = self.ui.lbl_chroma_postfilter
        self.check_chroma_postfilter = self.ui.check_chroma_postfilter
        self.btn_separate = self.ui.btn_separate
        self.lbl_status = self.ui.lbl_status

        self._default_unconf_msg = "Star removal model is missing or unavailable."
        self._standard_strides = ((DEFAULT_STRIDE, "Standard"), (128, "Fine"), (64, "Very Fine"))

        self.lbl_status.hide()
        self.unconfigured_box.setVisible(False)
        self.configured_box.setVisible(True)
        self._init_events()
        self._init_strides()

    def _init_events(self) -> None:
        self.btn_separate.clicked.connect(self.run_separation_requested.emit)
        self.combo_stride.currentIndexChanged.connect(lambda _index: self.stride_changed.emit(self.get_stride()))
        self.combo_stride.currentIndexChanged.connect(lambda _index: self._cleanup_custom_stride_items())
        self.check_chroma_postfilter.toggled.connect(self.chroma_postfilter_changed.emit)

    def _init_strides(self) -> None:
        for stride, label in self._standard_strides:
            self.combo_stride.addItem(f"{stride} ({label})", stride)

    def refresh_status(self, status: Dict[str, Any], has_prerequisites: bool = True) -> None:
        """Update widget visibility and enabled state according to model readiness and prerequisites."""
        model_ready = bool(status.get("model_ready", status.get("configured", False)))
        self.unconfigured_box.setVisible(not model_ready)
        self.configured_box.setVisible(model_ready)

        if model_ready:
            self.btn_separate.setEnabled(has_prerequisites)
        else:
            setup_error = status.get("setup_error")
            self.lbl_unconf_msg.setText(setup_error if setup_error else self._default_unconf_msg)
            self.btn_separate.setEnabled(False)

    def get_stride(self) -> int:
        return self.combo_stride.currentData()

    def get_chroma_postfilter(self) -> bool:
        """Return whether radial chroma post-filtering is enabled."""
        return bool(self.check_chroma_postfilter.isChecked())

    def set_chroma_postfilter(self, enabled: bool) -> None:
        """Update chroma post-filter toggle without emitting a settings change."""
        with QSignalBlocker(self.check_chroma_postfilter):
            self.check_chroma_postfilter.setChecked(bool(enabled))

    def _cleanup_custom_stride_items(self) -> None:
        """Remove transient custom stride entries once the user picks a standard value."""
        standard_values = {s for s, _ in self._standard_strides}
        current = self.combo_stride.currentData()
        if current in standard_values:
            with QSignalBlocker(self.combo_stride):
                for i in range(self.combo_stride.count() - 1, -1, -1):
                    if self.combo_stride.itemData(i) not in standard_values:
                        self.combo_stride.removeItem(i)

    def set_stride(self, stride: int) -> None:
        """Restore the project's selected stride without emitting a settings change.

        Valid strides outside the preset list are shown as a temporary custom
        entry instead of raising or silently falling back to the default.
        """
        validate_separation_stride(stride)
        standard_values = {s for s, _ in self._standard_strides}
        with QSignalBlocker(self.combo_stride):
            self.combo_stride.clear()
            for s, label in self._standard_strides:
                self.combo_stride.addItem(f"{s} ({label})", s)
            if stride not in standard_values:
                self.combo_stride.addItem(f"{stride} (Custom)", stride)
            index = self.combo_stride.findData(stride)
            self.combo_stride.setCurrentIndex(index)

    def set_from_project(self, project: FinishProject) -> None:
        """Populate widget controls from active FinishProject settings."""
        settings = project.get_settings()
        self.set_stride(settings.starnet_stride)
        self.set_chroma_postfilter(settings.chroma_postfilter)


__all__ = ["SeparateStarsSettings"]
