"""Settings and setup controls widget for Step 4: Finish Stars."""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QButtonGroup, QWidget

from startrails.lib.finish.defaults import (
    DEFAULT_GLOW_STAR_COUNT,
    DEFAULT_ROUND_STARS_AMOUNT_PERCENT,
    DEFAULT_ROUND_STARS_ENABLED,
    DEFAULT_STAR_COUNT_CUTOFF,
    DEFAULT_STAR_GLOW_AMOUNT_PERCENT,
    DEFAULT_STAR_GLOW_ENABLED,
    DEFAULT_STAR_GLOW_RADIUS_PX,
    GLOW_STAR_COUNT_PRESETS,
    STAR_COUNT_CUTOFF_PRESETS,
)
from startrails.lib.project_finish import FinishProject
from .ui_step_finish_stars import Ui_FinishStarsSettings

VALID_PREVIEW_LAYERS = ("composite", "finished_stars", "original_stars", "excluded_stars")


class FinishStarsSettings(QWidget):
    """Step 4 card body widget handling star selection, rounding, glow, and preview layers."""

    star_count_cutoff_changed = Signal(object)
    round_stars_enabled_changed = Signal(bool)
    round_stars_amount_changed = Signal(float)
    star_glow_enabled_changed = Signal(bool)
    glow_star_count_changed = Signal(int)
    star_glow_amount_changed = Signal(float)
    star_glow_radius_px_changed = Signal(float)
    preview_layer_changed = Signal(str)
    compare_pressed = Signal()
    compare_released = Signal()
    reset_requested = Signal()
    settings_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ui = Ui_FinishStarsSettings()
        self.ui.setupUi(self)

        # Attribute aliases for direct and test access
        self.combo_star_cutoff = self.ui.combo_star_cutoff
        self.lbl_star_cutoff_info = self.ui.lbl_star_cutoff_info

        self.check_round_stars = self.ui.check_round_stars
        self.slider_round_stars = self.ui.slider_round_stars
        self.lbl_round_stars_value = self.ui.lbl_round_stars_value

        self.check_star_glow = self.ui.check_star_glow
        self.combo_glow_count = self.ui.combo_glow_count
        self.slider_glow_amount = self.ui.slider_glow_amount
        self.lbl_glow_amount_value = self.ui.lbl_glow_amount_value
        self.slider_glow_radius = self.ui.slider_glow_radius
        self.lbl_glow_radius_value = self.ui.lbl_glow_radius_value

        self.radio_preview_composite = self.ui.radio_preview_composite
        self.radio_preview_finished_stars = self.ui.radio_preview_finished_stars
        self.radio_preview_original_stars = self.ui.radio_preview_original_stars
        self.radio_preview_excluded_stars = self.ui.radio_preview_excluded_stars
        self.btn_compare = self.ui.btn_compare

        self.btn_reset = self.ui.btn_reset
        self.lbl_status = self.ui.lbl_status
        self.lbl_help = self.ui.lbl_help
        self.help_box = self.ui.help_box

        # Populate preset item data directly on combos
        for i, preset in enumerate(STAR_COUNT_CUTOFF_PRESETS):
            self.combo_star_cutoff.setItemData(i, preset)
        for i, preset in enumerate(GLOW_STAR_COUNT_PRESETS):
            self.combo_glow_count.setItemData(i, preset)

        self.preview_group = QButtonGroup(self)
        self.preview_group.setExclusive(True)
        self.preview_group.addButton(self.radio_preview_composite, 0)
        self.preview_group.addButton(self.radio_preview_finished_stars, 1)
        self.preview_group.addButton(self.radio_preview_original_stars, 2)
        self.preview_group.addButton(self.radio_preview_excluded_stars, 3)

        self._has_prerequisites: bool = False
        self.lbl_status.hide()

        self.set_star_count_cutoff(DEFAULT_STAR_COUNT_CUTOFF)
        self.set_glow_star_count(DEFAULT_GLOW_STAR_COUNT)

        self._init_events()
        self.refresh_prerequisites(False)

    def _init_events(self) -> None:
        self.combo_star_cutoff.currentIndexChanged.connect(self._on_star_cutoff_changed)

        self.check_round_stars.toggled.connect(self._on_round_stars_toggled)
        self.slider_round_stars.valueChanged.connect(self._on_round_stars_slider_changed)

        self.check_star_glow.toggled.connect(self._on_star_glow_toggled)
        self.combo_glow_count.currentIndexChanged.connect(self._on_glow_count_changed)
        self.slider_glow_amount.valueChanged.connect(self._on_glow_amount_slider_changed)
        self.slider_glow_radius.valueChanged.connect(self._on_glow_radius_slider_changed)

        self.radio_preview_composite.toggled.connect(self._on_preview_layer_toggled)
        self.radio_preview_finished_stars.toggled.connect(self._on_preview_layer_toggled)
        self.radio_preview_original_stars.toggled.connect(self._on_preview_layer_toggled)
        self.radio_preview_excluded_stars.toggled.connect(self._on_preview_layer_toggled)

        self.btn_compare.pressed.connect(self.compare_pressed)
        self.btn_compare.released.connect(self.compare_released)

        self.btn_reset.clicked.connect(self._on_reset_clicked)

    def _on_star_cutoff_changed(self, index: int) -> None:
        if 0 <= index < len(STAR_COUNT_CUTOFF_PRESETS):
            cutoff = STAR_COUNT_CUTOFF_PRESETS[index]
            self.star_count_cutoff_changed.emit(cutoff)
            self.settings_changed.emit()

    def _on_round_stars_toggled(self, checked: bool) -> None:
        self.slider_round_stars.setEnabled(checked and self._has_prerequisites)
        self.round_stars_enabled_changed.emit(checked)
        self.settings_changed.emit()

    def _on_round_stars_slider_changed(self, value: int) -> None:
        self.lbl_round_stars_value.setText(f"{value}%")
        self.round_stars_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_star_glow_toggled(self, checked: bool) -> None:
        self.combo_glow_count.setEnabled(checked and self._has_prerequisites)
        self.slider_glow_amount.setEnabled(checked and self._has_prerequisites)
        self.slider_glow_radius.setEnabled(checked and self._has_prerequisites)
        self.star_glow_enabled_changed.emit(checked)
        self.settings_changed.emit()

    def _on_glow_count_changed(self, index: int) -> None:
        if 0 <= index < len(GLOW_STAR_COUNT_PRESETS):
            count = GLOW_STAR_COUNT_PRESETS[index]
            self.glow_star_count_changed.emit(count)
            self.settings_changed.emit()

    def _on_glow_amount_slider_changed(self, value: int) -> None:
        self.lbl_glow_amount_value.setText(f"{value}%")
        self.star_glow_amount_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_glow_radius_slider_changed(self, value: int) -> None:
        self.lbl_glow_radius_value.setText(f"{value} px")
        self.star_glow_radius_px_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_preview_layer_toggled(self, checked: bool) -> None:
        if checked:
            layer = self.get_preview_layer()
            self.preview_layer_changed.emit(layer)

    def _on_reset_clicked(self) -> None:
        self.set_star_count_cutoff(DEFAULT_STAR_COUNT_CUTOFF)
        self.set_round_stars_enabled(DEFAULT_ROUND_STARS_ENABLED)
        self.set_round_stars_amount(DEFAULT_ROUND_STARS_AMOUNT_PERCENT)
        self.set_star_glow_enabled(DEFAULT_STAR_GLOW_ENABLED)
        self.set_glow_star_count(DEFAULT_GLOW_STAR_COUNT)
        self.set_star_glow_amount(DEFAULT_STAR_GLOW_AMOUNT_PERCENT)
        self.set_star_glow_radius_px(DEFAULT_STAR_GLOW_RADIUS_PX)
        self.set_preview_layer("composite")
        self.reset_requested.emit()
        self.settings_changed.emit()

    # Getters and Setters

    def get_star_count_cutoff(self) -> Optional[int]:
        data = self.combo_star_cutoff.currentData()
        return data if data is not None else None

    def set_star_count_cutoff(self, cutoff: Optional[int]) -> None:
        if cutoff not in STAR_COUNT_CUTOFF_PRESETS:
            raise ValueError(f"Unsupported star cutoff preset: {cutoff!r}. Must be one of {STAR_COUNT_CUTOFF_PRESETS}")
        index = STAR_COUNT_CUTOFF_PRESETS.index(cutoff)
        with QSignalBlocker(self.combo_star_cutoff):
            self.combo_star_cutoff.setCurrentIndex(index)

    def set_cutoff_display(
        self,
        included_count: Optional[int],
        total_count: Optional[int],
        score: Optional[float] = None,
    ) -> None:
        """Display 'N of M stars' and cutoff score on the information label."""
        if included_count is None or total_count is None:
            self.lbl_star_cutoff_info.setText("—")
            return
        if score is not None:
            self.lbl_star_cutoff_info.setText(
                f"{included_count:,} of {total_count:,} stars · cutoff score: {score:.2f}"
            )
        else:
            self.lbl_star_cutoff_info.setText(f"{included_count:,} of {total_count:,} stars")

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

    def get_star_glow_enabled(self) -> bool:
        return self.check_star_glow.isChecked()

    def set_star_glow_enabled(self, enabled: bool) -> None:
        with QSignalBlocker(self.check_star_glow):
            self.check_star_glow.setChecked(bool(enabled))
        self.combo_glow_count.setEnabled(bool(enabled) and self._has_prerequisites)
        self.slider_glow_amount.setEnabled(bool(enabled) and self._has_prerequisites)
        self.slider_glow_radius.setEnabled(bool(enabled) and self._has_prerequisites)

    def get_glow_star_count(self) -> int:
        data = self.combo_glow_count.currentData()
        if data is None:
            raise ValueError("Glow star count combo has no selection.")
        return int(data)

    def set_glow_star_count(self, count: int) -> None:
        if count not in GLOW_STAR_COUNT_PRESETS:
            raise ValueError(f"Unsupported glow star count preset: {count!r}. Must be one of {GLOW_STAR_COUNT_PRESETS}")
        index = GLOW_STAR_COUNT_PRESETS.index(count)
        with QSignalBlocker(self.combo_glow_count):
            self.combo_glow_count.setCurrentIndex(index)

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

    def get_preview_layer(self) -> str:
        if self.radio_preview_finished_stars.isChecked():
            return "finished_stars"
        if self.radio_preview_original_stars.isChecked():
            return "original_stars"
        if self.radio_preview_excluded_stars.isChecked():
            return "excluded_stars"
        return "composite"

    def set_preview_layer(self, layer: str) -> None:
        if layer not in VALID_PREVIEW_LAYERS:
            raise ValueError(f"Unknown preview layer '{layer}'. Must be one of {VALID_PREVIEW_LAYERS}")
        with (
            QSignalBlocker(self.radio_preview_composite),
            QSignalBlocker(self.radio_preview_finished_stars),
            QSignalBlocker(self.radio_preview_original_stars),
            QSignalBlocker(self.radio_preview_excluded_stars),
        ):
            self.radio_preview_composite.setChecked(layer == "composite")
            self.radio_preview_finished_stars.setChecked(layer == "finished_stars")
            self.radio_preview_original_stars.setChecked(layer == "original_stars")
            self.radio_preview_excluded_stars.setChecked(layer == "excluded_stars")

    def set_from_project(self, project: FinishProject) -> None:
        """Populate widget controls from active FinishProject settings."""
        settings = project.get_settings()
        self.set_star_count_cutoff(settings.star_count_cutoff)
        self.set_round_stars_enabled(settings.round_stars_enabled)
        self.set_round_stars_amount(settings.round_stars_amount)
        self.set_star_glow_enabled(settings.star_glow_enabled)
        self.set_glow_star_count(settings.glow_star_count)
        self.set_star_glow_amount(settings.star_glow_amount)
        self.set_star_glow_radius_px(settings.star_glow_radius_px)

    def refresh_prerequisites(self, has_prerequisites: bool = True) -> None:
        """Enable or disable interactive controls based on separation availability."""
        self._has_prerequisites = has_prerequisites

        self.combo_star_cutoff.setEnabled(has_prerequisites)

        self.check_round_stars.setEnabled(has_prerequisites)
        self.slider_round_stars.setEnabled(has_prerequisites and self.check_round_stars.isChecked())

        self.check_star_glow.setEnabled(has_prerequisites)
        self.combo_glow_count.setEnabled(has_prerequisites and self.check_star_glow.isChecked())
        self.slider_glow_amount.setEnabled(has_prerequisites and self.check_star_glow.isChecked())
        self.slider_glow_radius.setEnabled(has_prerequisites and self.check_star_glow.isChecked())

        self.btn_reset.setEnabled(has_prerequisites)
        self.btn_compare.setEnabled(has_prerequisites)
        self.radio_preview_composite.setEnabled(has_prerequisites)
        self.radio_preview_finished_stars.setEnabled(has_prerequisites)
        self.radio_preview_original_stars.setEnabled(has_prerequisites)
        self.radio_preview_excluded_stars.setEnabled(has_prerequisites)


__all__ = ["FinishStarsSettings"]
