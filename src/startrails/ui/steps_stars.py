"""Settings and setup controls widget for Step 4: Finish Stars."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QButtonGroup, QWidget

from startrails.lib.finish.defaults import (
    DEFAULT_FAINT_STAR_AMOUNT_PERCENT,
    DEFAULT_FAINT_STAR_SUPPRESSION,
    DEFAULT_ROUND_STARS_AMOUNT_PERCENT,
    DEFAULT_ROUND_STARS_ENABLED,
    DEFAULT_STAR_AMOUNT_PERCENT,
    DEFAULT_STAR_GLOW_AMOUNT_PERCENT,
    DEFAULT_STAR_GLOW_ENABLED,
    DEFAULT_STAR_GLOW_RADIUS_PX,
)
from startrails.lib.project_finish import FinishProject
from .ui_step_finish_stars import Ui_FinishStarsSettings


class FinishStarsSettings(QWidget):
    """Step 4 card body widget handling star cosmetic profile, suppression, glow and amount."""

    star_amount_changed = Signal(float)
    round_stars_enabled_changed = Signal(bool)
    round_stars_amount_changed = Signal(float)
    faint_star_suppression_changed = Signal(bool)
    faint_star_amount_changed = Signal(float)
    star_glow_enabled_changed = Signal(bool)
    star_glow_amount_changed = Signal(float)
    star_glow_radius_px_changed = Signal(float)
    preview_layer_changed = Signal(str)
    reset_requested = Signal()
    settings_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ui = Ui_FinishStarsSettings()
        self.ui.setupUi(self)

        # Attribute aliases for direct and test access
        self.check_round_stars = self.ui.check_round_stars
        self.slider_round_stars = self.ui.slider_round_stars
        self.lbl_round_stars_value = self.ui.lbl_round_stars_value

        self.check_faint_suppression = self.ui.check_faint_suppression
        self.slider_faint_suppression = self.ui.slider_faint_suppression
        self.lbl_faint_suppression_value = self.ui.lbl_faint_suppression_value

        self.check_star_glow = self.ui.check_star_glow
        self.slider_glow_amount = self.ui.slider_glow_amount
        self.lbl_glow_amount_value = self.ui.lbl_glow_amount_value
        self.slider_glow_radius = self.ui.slider_glow_radius
        self.lbl_glow_radius_value = self.ui.lbl_glow_radius_value

        self.slider_star_amount = self.ui.slider_star_amount
        self.lbl_star_amount_value = self.ui.lbl_star_amount_value

        self.radio_preview_composite = self.ui.radio_preview_composite
        self.radio_preview_stars = self.ui.radio_preview_stars
        self.btn_reset = self.ui.btn_reset
        self.lbl_status = self.ui.lbl_status
        self.lbl_help = self.ui.lbl_help
        self.help_box = self.ui.help_box

        self.preview_group = QButtonGroup(self)
        self.preview_group.setExclusive(True)
        self.preview_group.addButton(self.radio_preview_composite, 0)
        self.preview_group.addButton(self.radio_preview_stars, 1)

        self._has_prerequisites: bool = False
        self.lbl_status.hide()

        self._init_events()
        self.refresh_prerequisites(False)

    def _init_events(self) -> None:
        self.check_round_stars.toggled.connect(self._on_round_stars_toggled)
        self.slider_round_stars.valueChanged.connect(self._on_round_stars_slider_changed)

        self.check_faint_suppression.toggled.connect(self._on_faint_suppression_toggled)
        self.slider_faint_suppression.valueChanged.connect(self._on_faint_suppression_slider_changed)

        self.check_star_glow.toggled.connect(self._on_star_glow_toggled)
        self.slider_glow_amount.valueChanged.connect(self._on_glow_amount_slider_changed)
        self.slider_glow_radius.valueChanged.connect(self._on_glow_radius_slider_changed)

        self.slider_star_amount.valueChanged.connect(self._on_star_amount_slider_changed)

        self.radio_preview_composite.toggled.connect(self._on_preview_layer_toggled)
        self.radio_preview_stars.toggled.connect(self._on_preview_layer_toggled)

        self.btn_reset.clicked.connect(self._on_reset_clicked)

    def _on_round_stars_toggled(self, checked: bool) -> None:
        self.slider_round_stars.setEnabled(checked and self._has_prerequisites)
        self.round_stars_enabled_changed.emit(checked)
        self.settings_changed.emit()

    def _on_round_stars_slider_changed(self, value: int) -> None:
        self.lbl_round_stars_value.setText(f"{value}%")
        self.round_stars_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_faint_suppression_toggled(self, checked: bool) -> None:
        self.slider_faint_suppression.setEnabled(checked and self._has_prerequisites)
        self.faint_star_suppression_changed.emit(checked)
        self.settings_changed.emit()

    def _on_faint_suppression_slider_changed(self, value: int) -> None:
        self.lbl_faint_suppression_value.setText(f"{value}%")
        self.faint_star_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_star_glow_toggled(self, checked: bool) -> None:
        self.slider_glow_amount.setEnabled(checked and self._has_prerequisites)
        self.slider_glow_radius.setEnabled(checked and self._has_prerequisites)
        self.star_glow_enabled_changed.emit(checked)
        self.settings_changed.emit()

    def _on_glow_amount_slider_changed(self, value: int) -> None:
        self.lbl_glow_amount_value.setText(f"{value}%")
        self.star_glow_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_glow_radius_slider_changed(self, value: int) -> None:
        self.lbl_glow_radius_value.setText(f"{value} px")
        self.star_glow_radius_px_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_star_amount_slider_changed(self, value: int) -> None:
        self.lbl_star_amount_value.setText(f"{value}%")
        self.star_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_preview_layer_toggled(self, checked: bool) -> None:
        if checked:
            layer = "stars" if self.radio_preview_stars.isChecked() else "composite"
            self.preview_layer_changed.emit(layer)

    def _on_reset_clicked(self) -> None:
        self.set_round_stars_enabled(DEFAULT_ROUND_STARS_ENABLED)
        self.set_round_stars_amount(DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
        self.set_faint_star_suppression(DEFAULT_FAINT_STAR_SUPPRESSION)
        self.set_faint_star_amount(DEFAULT_FAINT_STAR_AMOUNT_PERCENT)
        self.set_star_glow_enabled(DEFAULT_STAR_GLOW_ENABLED)
        self.set_star_glow_amount(DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
        self.set_star_glow_radius_px(DEFAULT_STAR_GLOW_RADIUS_PX)
        self.set_star_amount(DEFAULT_STAR_AMOUNT_PERCENT)
        self.set_preview_layer("composite")
        self.reset_requested.emit()
        self.settings_changed.emit()

    # Getters and Setters

    def get_round_stars_enabled(self) -> bool:
        return self.check_round_stars.isChecked()

    def set_round_stars_enabled(self, enabled: bool) -> None:
        with QSignalBlocker(self.check_round_stars):
            self.check_round_stars.setChecked(bool(enabled))
        self.slider_round_stars.setEnabled(bool(enabled) and self._has_prerequisites)

    def get_round_stars_amount(self) -> float:
        return float(self.slider_round_stars.value())

    def set_round_stars_amount(self, amount: float) -> None:
        val = int(round(amount))
        val = max(0, min(100, val))
        self.lbl_round_stars_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_round_stars):
            self.slider_round_stars.setValue(val)

    def get_faint_star_suppression(self) -> bool:
        return self.check_faint_suppression.isChecked()

    def set_faint_star_suppression(self, enabled: bool) -> None:
        with QSignalBlocker(self.check_faint_suppression):
            self.check_faint_suppression.setChecked(bool(enabled))
        self.slider_faint_suppression.setEnabled(bool(enabled) and self._has_prerequisites)

    def get_faint_star_amount(self) -> float:
        return float(self.slider_faint_suppression.value())

    def set_faint_star_amount(self, amount: float) -> None:
        val = int(round(amount))
        val = max(0, min(100, val))
        self.lbl_faint_suppression_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_faint_suppression):
            self.slider_faint_suppression.setValue(val)

    def get_star_glow_enabled(self) -> bool:
        return self.check_star_glow.isChecked()

    def set_star_glow_enabled(self, enabled: bool) -> None:
        with QSignalBlocker(self.check_star_glow):
            self.check_star_glow.setChecked(bool(enabled))
        self.slider_glow_amount.setEnabled(bool(enabled) and self._has_prerequisites)
        self.slider_glow_radius.setEnabled(bool(enabled) and self._has_prerequisites)

    def get_star_glow_amount(self) -> float:
        return float(self.slider_glow_amount.value())

    def set_star_glow_amount(self, amount: float) -> None:
        val = int(round(amount))
        val = max(0, min(100, val))
        self.lbl_glow_amount_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_glow_amount):
            self.slider_glow_amount.setValue(val)

    def get_star_glow_radius_px(self) -> float:
        return float(self.slider_glow_radius.value())

    def set_star_glow_radius_px(self, radius: float) -> None:
        val = int(round(radius))
        val = max(1, min(50, val))
        self.lbl_glow_radius_value.setText(f"{val} px")
        with QSignalBlocker(self.slider_glow_radius):
            self.slider_glow_radius.setValue(val)

    def get_star_amount(self) -> float:
        return float(self.slider_star_amount.value())

    def set_star_amount(self, amount: float) -> None:
        val = int(round(amount))
        val = max(0, min(100, val))
        self.lbl_star_amount_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_star_amount):
            self.slider_star_amount.setValue(val)

    def get_preview_layer(self) -> str:
        return "stars" if self.radio_preview_stars.isChecked() else "composite"

    def set_preview_layer(self, layer: str) -> None:
        with QSignalBlocker(self.radio_preview_composite), QSignalBlocker(self.radio_preview_stars):
            if layer == "stars":
                self.radio_preview_stars.setChecked(True)
                self.radio_preview_composite.setChecked(False)
            else:
                self.radio_preview_composite.setChecked(True)
                self.radio_preview_stars.setChecked(False)

    def set_from_project(self, project: FinishProject) -> None:
        """Populate widget controls from active FinishProject settings."""
        settings = project.get_settings()
        self.set_round_stars_enabled(settings.round_stars_enabled)
        self.set_round_stars_amount(settings.round_stars_amount)
        self.set_faint_star_suppression(settings.faint_star_suppression)
        self.set_faint_star_amount(settings.faint_star_amount)
        self.set_star_glow_enabled(settings.star_glow_enabled)
        self.set_star_glow_amount(settings.star_glow_amount)
        self.set_star_glow_radius_px(settings.star_glow_radius_px)
        self.set_star_amount(settings.star_amount)

    def refresh_prerequisites(self, has_prerequisites: bool = True) -> None:
        """Enable or disable interactive controls based on separation availability."""
        self._has_prerequisites = has_prerequisites

        self.check_round_stars.setEnabled(has_prerequisites)
        self.slider_round_stars.setEnabled(has_prerequisites and self.check_round_stars.isChecked())

        self.check_faint_suppression.setEnabled(has_prerequisites)
        self.slider_faint_suppression.setEnabled(has_prerequisites and self.check_faint_suppression.isChecked())

        self.check_star_glow.setEnabled(has_prerequisites)
        self.slider_glow_amount.setEnabled(has_prerequisites and self.check_star_glow.isChecked())
        self.slider_glow_radius.setEnabled(has_prerequisites and self.check_star_glow.isChecked())

        self.slider_star_amount.setEnabled(has_prerequisites)
        self.btn_reset.setEnabled(has_prerequisites)
        self.radio_preview_composite.setEnabled(has_prerequisites)
        self.radio_preview_stars.setEnabled(has_prerequisites)


__all__ = ["FinishStarsSettings"]
