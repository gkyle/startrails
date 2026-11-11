"""Settings and controls widget for Step 4: Recombine and Save."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget

from startrails.lib.finish.defaults import FINISH_DEFAULTS
from .steps import bind_percent_slider_spinbox, set_percent_slider_spinbox
from .ui_step_finish_recombine import Ui_FinishRecombineSettings

if TYPE_CHECKING:
    from startrails.lib.project_finish import FinishProject


class FinishRecombineSettings(QWidget):
    """Step 4 card body widget handling layer blending amounts, modes, and export."""

    star_amount_changed = Signal(float)
    star_threshold_changed = Signal(float)
    blend_mode_changed = Signal(str)
    slider_dragging = Signal()
    settings_changed = Signal()
    export_layers_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ui = Ui_FinishRecombineSettings()
        self.ui.setupUi(self)

        # Attribute aliases for backward compatibility and test access
        self.lbl_star_amount_title = self.ui.lbl_star_amount_title
        self.slider_star_amount = self.ui.slider_star_amount
        self.spin_star_amount = self.ui.spin_star_amount
        self.lbl_star_threshold_title = self.ui.lbl_star_threshold_title
        self.slider_star_threshold = self.ui.slider_star_threshold
        self.spin_star_threshold = self.ui.spin_star_threshold
        self.combo_star_blend_mode = self.ui.combo_star_blend_mode
        self.lbl_status = self.ui.lbl_status
        self.btn_save_output = self.ui.btn_save_output
        self.btn_export_layers = self.ui.btn_export_layers

        # Set user data for blend mode combo items
        self.combo_star_blend_mode.setItemData(0, "add")
        self.combo_star_blend_mode.setItemData(1, "screen")

        # Initialize defaults from FINISH_DEFAULTS before connecting events
        self.set_star_amount(FINISH_DEFAULTS.star_amount)
        self.set_star_threshold(FINISH_DEFAULTS.star_threshold)
        self.set_blend_mode(FINISH_DEFAULTS.blend_mode)

        self.lbl_status.hide()
        self._init_events()
        self.refresh_prerequisites(False)

    def _init_events(self) -> None:
        for slider, spin, sig in (
            (self.slider_star_amount, self.spin_star_amount, self.star_amount_changed),
            (self.slider_star_threshold, self.spin_star_threshold, self.star_threshold_changed),
        ):
            bind_percent_slider_spinbox(slider, spin, sig, self.settings_changed, self.slider_dragging)
        self.combo_star_blend_mode.currentIndexChanged.connect(self._on_star_blend_mode_changed)
        self.btn_export_layers.clicked.connect(self.export_layers_requested.emit)

    def is_slider_down(self) -> bool:
        """Return True if any composition slider is actively held down."""
        return bool(self.slider_star_amount.isSliderDown() or self.slider_star_threshold.isSliderDown())

    def _on_star_blend_mode_changed(self, index: int) -> None:
        data = self.combo_star_blend_mode.currentData()
        if data is not None:
            self.blend_mode_changed.emit(str(data))
            self.settings_changed.emit()

    def get_star_amount(self) -> float:
        return float(self.slider_star_amount.value())

    def set_star_amount(self, amount: float) -> None:
        set_percent_slider_spinbox(self.slider_star_amount, self.spin_star_amount, amount)

    def get_star_threshold(self) -> float:
        """Return the exact cutoff, including values beyond the slider's routine range."""
        return float(self.spin_star_threshold.value())

    def set_star_threshold(self, threshold: float) -> None:
        set_percent_slider_spinbox(self.slider_star_threshold, self.spin_star_threshold, threshold)

    def get_blend_mode(self) -> str:
        data = self.combo_star_blend_mode.currentData()
        if data is None:
            raise ValueError("Blend mode combo has no valid selection.")
        return str(data)

    def set_blend_mode(self, mode: str) -> None:
        idx = self.combo_star_blend_mode.findData(mode)
        if idx < 0:
            raise ValueError(f"Unsupported blend mode '{mode}'.")
        with QSignalBlocker(self.combo_star_blend_mode):
            self.combo_star_blend_mode.setCurrentIndex(idx)

    def set_from_project(self, project: FinishProject) -> None:
        settings = project.get_settings()
        self.set_star_amount(settings.star_amount)
        self.set_star_threshold(settings.star_threshold)
        self.set_blend_mode(settings.blend_mode)

    def refresh_prerequisites(self, has_prerequisites: bool = True) -> None:
        self.slider_star_amount.setEnabled(has_prerequisites)
        self.spin_star_amount.setEnabled(has_prerequisites)
        self.slider_star_threshold.setEnabled(has_prerequisites)
        self.spin_star_threshold.setEnabled(has_prerequisites)
        self.combo_star_blend_mode.setEnabled(has_prerequisites)
        self.btn_save_output.setEnabled(has_prerequisites)
        self.btn_export_layers.setEnabled(has_prerequisites)


__all__ = ["FinishRecombineSettings"]
