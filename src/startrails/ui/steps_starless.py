"""Settings and setup controls widget for Step 3: Finish Starless."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QButtonGroup, QWidget

from startrails.lib.finish.defaults import (
    DEFAULT_DENOISE_SCOPE,
    DEFAULT_DENOISE_STRENGTH_PERCENT,
    DEFAULT_DETAIL_AMOUNT_PERCENT,
    DEFAULT_ENABLE_STARLESS_DENOISE,
    DEFAULT_ENABLE_STARLESS_SHARPEN,
    DEFAULT_STRUCTURE_AMOUNT_PERCENT,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
)
from startrails.lib.project_finish import FinishProject
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
    reset_requested = Signal()
    settings_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ui = Ui_FinishStarlessSettings()
        self.ui.setupUi(self)

        # Direct attribute aliases on self for backward compatibility and test access
        self.unconfigured_box = self.ui.unconfigured_box
        self.configured_box = self.ui.configured_box
        self.lbl_unconf_msg = self.ui.lbl_unconf_msg
        self.lbl_provider_dot = self.ui.lbl_provider_dot
        self.lbl_provider_info = self.ui.lbl_provider_info

        self.lbl_enable_denoise = self.ui.lbl_enable_denoise
        self.check_enable_denoise = self.ui.check_enable_denoise
        self.check_enable_starless = self.ui.check_enable_denoise

        self.slider_strength = self.ui.slider_strength
        self.slider_denoise_strength = self.ui.slider_strength
        self.lbl_strength_value = self.ui.lbl_strength_value
        self.radio_sky_only = self.ui.radio_sky_only
        self.radio_whole_image = self.ui.radio_whole_image

        self.lbl_enable_sharpen = self.ui.lbl_enable_sharpen
        self.check_enable_sharpen = self.ui.check_enable_sharpen

        self.slider_structure = self.ui.slider_structure
        self.slider_structure_amount = self.ui.slider_structure
        self.lbl_structure_value = self.ui.lbl_structure_value
        self.slider_detail = self.ui.slider_detail
        self.slider_detail_amount = self.ui.slider_detail
        self.lbl_detail_value = self.ui.lbl_detail_value
        self.btn_reset = self.ui.btn_reset
        self.lbl_status = self.ui.lbl_status

        self.scope_group = QButtonGroup(self)
        self.scope_group.setExclusive(True)
        self.scope_group.addButton(self.radio_sky_only, 0)
        self.scope_group.addButton(self.radio_whole_image, 1)

        self._is_ready: bool = False
        self._has_prerequisites: bool = True
        self._has_endpoint: bool = False
        self._default_unconf_msg = (
            "GraXpert AI model (3.0.2) is missing or unverified. Zero-strength finishing remains available."
        )

        self.lbl_status.hide()
        self.unconfigured_box.setVisible(True)
        self.configured_box.setVisible(False)
        self._update_controls_enabled()

        self._init_events()

    def _init_events(self) -> None:
        self.check_enable_denoise.toggled.connect(self._on_enable_denoise_toggled)
        self.check_enable_sharpen.toggled.connect(self._on_enable_sharpen_toggled)

        self.slider_strength.valueChanged.connect(self._on_strength_slider_changed)
        self.slider_strength.sliderPressed.connect(self.slider_dragging.emit)
        self.slider_strength.sliderReleased.connect(self._on_strength_slider_released)

        self.radio_sky_only.toggled.connect(self._on_scope_toggled)
        self.radio_whole_image.toggled.connect(self._on_scope_toggled)

        self.slider_structure.valueChanged.connect(self._on_structure_slider_changed)
        self.slider_structure.sliderPressed.connect(self.slider_dragging.emit)
        self.slider_structure.sliderReleased.connect(self._on_structure_slider_released)

        self.slider_detail.valueChanged.connect(self._on_detail_slider_changed)
        self.slider_detail.sliderPressed.connect(self.slider_dragging.emit)
        self.slider_detail.sliderReleased.connect(self._on_detail_slider_released)

        self.btn_reset.clicked.connect(self._on_reset_clicked)

    def _on_enable_denoise_toggled(self, checked: bool) -> None:
        self._update_controls_enabled()
        self.enable_denoise_changed.emit(checked)
        self.settings_changed.emit()

    def _on_enable_sharpen_toggled(self, checked: bool) -> None:
        self._update_controls_enabled()
        self.enable_sharpen_changed.emit(checked)
        self.settings_changed.emit()

    def _on_strength_slider_changed(self, value: int) -> None:
        self.lbl_strength_value.setText(f"{value}%")
        if self.slider_strength.isSliderDown():
            self.slider_dragging.emit()
        else:
            self.denoise_strength_changed.emit(float(value))
            self.settings_changed.emit()

    def _on_strength_slider_released(self) -> None:
        val = self.slider_strength.value()
        self.lbl_strength_value.setText(f"{val}%")
        self.denoise_strength_changed.emit(float(val))
        self.settings_changed.emit()

    def _on_scope_toggled(self, checked: bool) -> None:
        if checked:
            self.denoise_scope_changed.emit(self.get_scope())
            self.settings_changed.emit()

    def _on_structure_slider_changed(self, value: int) -> None:
        self.lbl_structure_value.setText(f"{value}%")
        if self.slider_structure.isSliderDown():
            self.slider_dragging.emit()
        else:
            self.structure_amount_changed.emit(float(value))
            self.settings_changed.emit()

    def _on_structure_slider_released(self) -> None:
        val = self.slider_structure.value()
        self.lbl_structure_value.setText(f"{val}%")
        self.structure_amount_changed.emit(float(val))
        self.settings_changed.emit()

    def _on_detail_slider_changed(self, value: int) -> None:
        self.lbl_detail_value.setText(f"{value}%")
        if self.slider_detail.isSliderDown():
            self.slider_dragging.emit()
        else:
            self.detail_amount_changed.emit(float(value))
            self.settings_changed.emit()

    def _on_detail_slider_released(self) -> None:
        val = self.slider_detail.value()
        self.lbl_detail_value.setText(f"{val}%")
        self.detail_amount_changed.emit(float(val))
        self.settings_changed.emit()

    def _on_reset_clicked(self) -> None:
        self.set_enable_denoise(DEFAULT_ENABLE_STARLESS_DENOISE)
        self.set_enable_sharpen(DEFAULT_ENABLE_STARLESS_SHARPEN)
        self.set_strength(DEFAULT_DENOISE_STRENGTH_PERCENT)
        self.set_scope(DEFAULT_DENOISE_SCOPE)
        self.set_structure(DEFAULT_STRUCTURE_AMOUNT_PERCENT)
        self.set_detail(DEFAULT_DETAIL_AMOUNT_PERCENT)
        self.reset_requested.emit()
        self.settings_changed.emit()

    def _update_controls_enabled(self) -> None:
        denoise_active = self._has_prerequisites and self.get_enable_denoise()
        sharpen_active = self._has_prerequisites and self.get_enable_sharpen()

        self.slider_strength.setEnabled(denoise_active)
        self.radio_sky_only.setEnabled(denoise_active)
        self.radio_whole_image.setEnabled(denoise_active)

        self.slider_structure.setEnabled(sharpen_active)
        self.slider_detail.setEnabled(sharpen_active)

        self.check_enable_denoise.setEnabled(self._has_prerequisites)
        self.lbl_enable_denoise.setEnabled(self._has_prerequisites)
        self.check_enable_sharpen.setEnabled(self._has_prerequisites)
        self.lbl_enable_sharpen.setEnabled(self._has_prerequisites)
        self.btn_reset.setEnabled(self._has_prerequisites)

    def get_enable_denoise(self) -> bool:
        """Return whether starless denoising is enabled."""
        return self.check_enable_denoise.isChecked()

    def set_enable_denoise(self, enabled: bool) -> None:
        """Update denoise checkbox state without emitting change signals."""
        with QSignalBlocker(self.check_enable_denoise):
            self.check_enable_denoise.setChecked(enabled)
        self._update_controls_enabled()

    def get_enable_sharpen(self) -> bool:
        """Return whether starless sharpening is enabled."""
        return self.check_enable_sharpen.isChecked()

    def set_enable_sharpen(self, enabled: bool) -> None:
        """Update sharpen checkbox state without emitting change signals."""
        with QSignalBlocker(self.check_enable_sharpen):
            self.check_enable_sharpen.setChecked(enabled)
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
        """Update the slider position and display label without emitting change signals."""
        val = int(round(strength))
        val = max(0, min(100, val))
        self.lbl_strength_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_strength):
            self.slider_strength.setValue(val)

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
        """Update the structure slider position and display label without emitting change signals."""
        val = int(round(value))
        val = max(0, min(100, val))
        self.lbl_structure_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_structure):
            self.slider_structure.setValue(val)

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
        """Update the detail slider position and display label without emitting change signals."""
        val = int(round(value))
        val = max(0, min(100, val))
        self.lbl_detail_value.setText(f"{val}%")
        with QSignalBlocker(self.slider_detail):
            self.slider_detail.setValue(val)

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
        """Update provider/readiness display and interactive control states."""
        self._has_prerequisites = has_prerequisites
        self._has_endpoint = has_endpoint

        policy = status.get("policy")
        model_ready = status.get("model_ready", False)
        is_ready = bool(model_ready and policy and policy.get("verified", False))
        self._is_ready = is_ready

        self.unconfigured_box.setVisible(not is_ready)
        self.configured_box.setVisible(is_ready)

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
        else:
            configured_provider = policy.get("provider", "CPU")
            configured_label = self._format_provider_label(configured_provider)
            variant = policy.get("variant")
            variant_str = f" ({variant})" if variant else ""

            exec_provider = status.get("execution_provider")
            fallback_reason = status.get("fallback_reason")

            if exec_provider and exec_provider != configured_provider:
                actual_label = self._format_provider_label(exec_provider)
                if fallback_reason:
                    details = (
                        f"{actual_label} (fallback: {fallback_reason}; configured: {configured_label}{variant_str})"
                    )
                else:
                    details = f"{actual_label} (fallback from {configured_label}{variant_str})"
                self.lbl_provider_dot.setStyleSheet("color: #f59e0b;")
            elif fallback_reason:
                details = f"{configured_label}{variant_str} (fallback: {fallback_reason})"
                self.lbl_provider_dot.setStyleSheet("color: #f59e0b;")
            else:
                details = f"{configured_label}{variant_str}"
                self.lbl_provider_dot.setStyleSheet("color: #10b981;")

            info_text = f"GraXpert AI 3.0.2 • {details}"
            self.lbl_provider_info.setText(info_text)
            self.configured_box.setToolTip(info_text)

        # Control enable states
        self._update_controls_enabled()

    @staticmethod
    def _format_provider_label(provider: str) -> str:
        if provider == "CUDAExecutionProvider":
            return "CUDA (GPU)"
        if provider == "CPUExecutionProvider":
            return "CPU"
        return provider


__all__ = ["FinishStarlessSettings"]
