"""Settings and setup controls widget for Step 3: Finish Starless."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QButtonGroup, QWidget

from startrails.lib.finish.defaults import (
    DEFAULT_DENOISE_STRENGTH_PERCENT,
    DEFAULT_DETAIL_AMOUNT_PERCENT,
    DEFAULT_ENABLE_STARLESS_SHARPEN,
    DEFAULT_STRUCTURE_AMOUNT_PERCENT,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
)
from startrails.lib.project_finish import FinishProject
from .steps import bind_percent_slider_spinbox, set_percent_slider_spinbox
from .ui_step_finish_starless import Ui_FinishStarlessSettings


class FinishStarlessSettings(QWidget):
    """Step 3 card body widget handling GraXpert AI denoise and sharpening settings."""

    enable_denoise_changed = Signal(bool)
    enable_sharpen_changed = Signal(bool)
    enable_starless_changed = enable_denoise_changed
    run_denoise_requested = Signal()
    denoise_strength_changed = Signal(float)
    strength_changed = denoise_strength_changed
    denoise_scope_changed = Signal(str)
    scope_changed = denoise_scope_changed
    structure_amount_changed = Signal(float)
    structure_changed = structure_amount_changed
    detail_amount_changed = Signal(float)
    detail_changed = detail_amount_changed
    slider_dragging = Signal()
    settings_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ui = Ui_FinishStarlessSettings()
        self.ui.setupUi(self)

        # Direct attribute aliases on self for backward compatibility and test access
        self.unconfigured_box = self.ui.unconfigured_box
        self.lbl_unconf_msg = self.ui.lbl_unconf_msg

        self.lbl_enable_denoise = self.ui.lbl_enable_denoise
        self.check_enable_denoise = self.ui.check_enable_denoise
        self.check_enable_starless = self.ui.check_enable_denoise

        self.slider_strength = self.ui.slider_strength
        self.slider_denoise_strength = self.ui.slider_strength
        self.spin_strength = self.ui.spin_strength
        self.spin_denoise_strength = self.ui.spin_strength
        self.radio_sky_only = self.ui.radio_sky_only
        self.radio_whole_image = self.ui.radio_whole_image

        self.lbl_enable_sharpen = self.ui.lbl_enable_sharpen
        self.check_enable_sharpen = self.ui.check_enable_sharpen

        self.slider_structure = self.ui.slider_structure
        self.slider_structure_amount = self.ui.slider_structure
        self.spin_structure = self.ui.spin_structure
        self.spin_structure_amount = self.ui.spin_structure
        self.slider_detail = self.ui.slider_detail
        self.slider_detail_amount = self.ui.slider_detail
        self.spin_detail = self.ui.spin_detail
        self.spin_detail_amount = self.ui.spin_detail
        self.lbl_status = self.ui.lbl_status

        self.scope_group = QButtonGroup(self)
        self.scope_group.setExclusive(True)
        self.scope_group.addButton(self.radio_sky_only, 0)
        self.scope_group.addButton(self.radio_whole_image, 1)

        self._is_ready: bool = False
        self._has_prerequisites: bool = True
        self._has_endpoint: bool = False
        self._remembered_enable_sharpen: bool = DEFAULT_ENABLE_STARLESS_SHARPEN
        self._default_unconf_msg = (
            "GraXpert AI model (3.0.2) is missing or unverified. Zero-strength finishing remains available."
        )

        self.lbl_status.hide()
        self.unconfigured_box.setVisible(True)
        self.set_strength(DEFAULT_DENOISE_STRENGTH_PERCENT)
        self.set_structure(DEFAULT_STRUCTURE_AMOUNT_PERCENT)
        self.set_detail(DEFAULT_DETAIL_AMOUNT_PERCENT)
        self._update_controls_enabled()

        self._init_events()

    def _init_events(self) -> None:
        self.check_enable_denoise.toggled.connect(self._on_enable_denoise_toggled)
        self.check_enable_sharpen.toggled.connect(self._on_enable_sharpen_toggled)

        for slider, spin, signal in (
            (self.slider_strength, self.spin_strength, self.denoise_strength_changed),
            (self.slider_structure, self.spin_structure, self.structure_amount_changed),
            (self.slider_detail, self.spin_detail, self.detail_amount_changed),
        ):
            bind_percent_slider_spinbox(slider, spin, signal, self.settings_changed, self.slider_dragging)

        self.radio_sky_only.toggled.connect(self._on_scope_toggled)
        self.radio_whole_image.toggled.connect(self._on_scope_toggled)

    def _on_enable_denoise_toggled(self, checked: bool) -> None:
        self._update_controls_enabled()
        self.enable_denoise_changed.emit(checked)
        self.settings_changed.emit()

    def _on_enable_sharpen_toggled(self, checked: bool) -> None:
        self._remembered_enable_sharpen = bool(checked)
        self._update_controls_enabled()
        self.enable_sharpen_changed.emit(checked)
        self.settings_changed.emit()

    def _on_scope_toggled(self, checked: bool) -> None:
        if checked:
            self.denoise_scope_changed.emit(self.get_scope())
            self.settings_changed.emit()

    def _update_controls_enabled(self) -> None:
        denoise_enabled = self.get_enable_denoise()
        denoise_active = self._has_prerequisites and denoise_enabled
        sharpen_enabled = denoise_enabled and self._remembered_enable_sharpen
        sharpen_active = self._has_prerequisites and sharpen_enabled

        with QSignalBlocker(self.check_enable_sharpen):
            self.check_enable_sharpen.setChecked(sharpen_enabled)

        self.slider_strength.setEnabled(denoise_active)
        self.spin_strength.setEnabled(denoise_active)
        self.radio_sky_only.setEnabled(denoise_active)
        self.radio_whole_image.setEnabled(denoise_active)

        self.slider_structure.setEnabled(sharpen_active)
        self.spin_structure.setEnabled(sharpen_active)
        self.slider_detail.setEnabled(sharpen_active)
        self.spin_detail.setEnabled(sharpen_active)

        self.check_enable_denoise.setEnabled(self._has_prerequisites)
        self.lbl_enable_denoise.setEnabled(self._has_prerequisites)
        self.check_enable_sharpen.setEnabled(denoise_active)
        self.lbl_enable_sharpen.setEnabled(denoise_active)

    def get_enable_denoise(self) -> bool:
        """Return whether starless denoising is enabled."""
        return self.check_enable_denoise.isChecked()

    def set_enable_denoise(self, enabled: bool) -> None:
        """Update denoise checkbox state without emitting change signals."""
        with QSignalBlocker(self.check_enable_denoise):
            self.check_enable_denoise.setChecked(enabled)
        self._update_controls_enabled()

    def get_enable_sharpen(self) -> bool:
        """Return whether post-denoise sharpening is effectively enabled."""
        return self.get_enable_denoise() and self.check_enable_sharpen.isChecked()

    def set_enable_sharpen(self, enabled: bool) -> None:
        """Update post-denoise sharpen checkbox state without emitting change signals."""
        self._remembered_enable_sharpen = bool(enabled)
        with QSignalBlocker(self.check_enable_sharpen):
            self.check_enable_sharpen.setChecked(self._remembered_enable_sharpen if self.get_enable_denoise() else False)
        self._update_controls_enabled()

    def get_enable_starless(self) -> bool:
        """Alias returning overall starless adjustment enablement."""
        return self.get_enable_denoise()

    def set_enable_starless(self, enabled: bool) -> None:
        """Alias setting starless adjustment enablement."""
        self.set_enable_denoise(enabled)

    def is_slider_down(self) -> bool:
        """Return True if any starless slider is actively held down."""
        return bool(
            self.slider_strength.isSliderDown()
            or self.slider_structure.isSliderDown()
            or self.slider_detail.isSliderDown()
        )

    def get_strength(self) -> float:
        """Return the current denoise strength as a percentage (0.0 to 100.0)."""
        return float(self.slider_strength.value())

    def set_strength(self, strength: float) -> None:
        """Update the strength slider and spinbox without emitting change signals."""
        set_percent_slider_spinbox(self.slider_strength, self.spin_strength, strength)

    def get_scope(self) -> str:
        """Return the selected scope ('sky_only' or 'whole_image')."""
        return SCOPE_WHOLE_IMAGE if self.radio_whole_image.isChecked() else SCOPE_SKY_ONLY

    def set_scope(self, scope: str) -> None:
        """Update the scope radio buttons without emitting change signals."""
        with QSignalBlocker(self.radio_sky_only), QSignalBlocker(self.radio_whole_image):
            if scope == SCOPE_WHOLE_IMAGE:
                self.radio_whole_image.setChecked(True)
                self.radio_sky_only.setChecked(False)
            else:
                self.radio_sky_only.setChecked(True)
                self.radio_whole_image.setChecked(False)

    def get_structure(self) -> float:
        """Return the current structure amount as a percentage (0.0 to 100.0)."""
        return float(self.slider_structure.value())

    def get_structure_amount(self) -> float:
        """Alias returning the structure amount as a percentage."""
        return self.get_structure()

    def set_structure(self, value: float) -> None:
        """Update the structure slider and spinbox without emitting change signals."""
        set_percent_slider_spinbox(self.slider_structure, self.spin_structure, value)

    def set_structure_amount(self, value: float) -> None:
        """Alias setting the structure amount without emitting change signals."""
        self.set_structure(value)

    def get_detail(self) -> float:
        """Return the current detail amount as a percentage (0.0 to 100.0)."""
        return float(self.slider_detail.value())

    def get_detail_amount(self) -> float:
        """Alias returning the detail amount as a percentage."""
        return self.get_detail()

    def set_detail(self, value: float) -> None:
        """Update the detail slider and spinbox without emitting change signals."""
        set_percent_slider_spinbox(self.slider_detail, self.spin_detail, value)

    def set_detail_amount(self, value: float) -> None:
        """Alias setting the detail amount without emitting change signals."""
        self.set_detail(value)

    def set_from_project(self, project: FinishProject) -> None:
        """Populate widget controls from active FinishProject settings."""
        settings = project.get_settings()
        self.set_enable_denoise(settings.enable_starless_denoise)
        self.set_enable_sharpen(settings.enable_starless_sharpen)
        self.set_strength(settings.denoise_strength)
        self.set_scope(settings.denoise_scope)
        self.set_structure(settings.structure_amount)
        self.set_detail(settings.detail_amount)

    def refresh_status(
        self,
        status: Dict[str, Any],
        has_prerequisites: bool = True,
        has_endpoint: bool = False,
    ) -> None:
        """Update device/readiness display and interactive control states."""
        self._has_prerequisites = has_prerequisites
        self._has_endpoint = has_endpoint

        model_ready = bool(status.get("model_ready", status.get("configured", False)))
        is_ready = model_ready
        self._is_ready = is_ready

        self.unconfigured_box.setVisible(not is_ready)

        if not is_ready:
            setup_error = status.get("setup_error")
            if has_endpoint:
                if setup_error:
                    self.lbl_unconf_msg.setText(
                        f"GraXpert setup required ({setup_error}). Cached denoise endpoint is available for blending."
                    )
                else:
                    self.lbl_unconf_msg.setText(
                        "GraXpert model unavailable. Cached denoise endpoint is available for blending."
                    )
            else:
                if setup_error:
                    self.lbl_unconf_msg.setText(f"GraXpert setup required: {setup_error}")
                elif not model_ready:
                    self.lbl_unconf_msg.setText("GraXpert AI model (3.0.2) is missing or unverified.")
                else:
                    self.lbl_unconf_msg.setText(self._default_unconf_msg)

        # Control enable states
        self._update_controls_enabled()


__all__ = ["FinishStarlessSettings"]
