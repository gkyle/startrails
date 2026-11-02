"""Settings and setup controls widget for Step 3: Finish Starless."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QButtonGroup, QWidget

from startrails.lib.finish.defaults import (
    DEFAULT_DENOISE_SCOPE,
    DEFAULT_DENOISE_STRENGTH_PERCENT,
    SCOPE_SKY_ONLY,
    SCOPE_WHOLE_IMAGE,
)
from startrails.lib.project_finish import FinishProject
from .ui_step_finish_starless import Ui_FinishStarlessSettings


class FinishStarlessSettings(QWidget):
    """Step 3 card body widget handling GraXpert AI denoise settings and execution."""

    run_denoise_requested = Signal()
    denoise_strength_changed = Signal(float)
    strength_changed = denoise_strength_changed
    denoise_scope_changed = Signal(str)
    scope_changed = denoise_scope_changed
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
        self.slider_strength = self.ui.slider_strength
        self.slider_denoise_strength = self.ui.slider_strength
        self.lbl_strength_value = self.ui.lbl_strength_value
        self.radio_sky_only = self.ui.radio_sky_only
        self.radio_whole_image = self.ui.radio_whole_image
        self.btn_run_denoise = self.ui.btn_run_denoise
        self.btn_reset = self.ui.btn_reset
        self.lbl_status = self.ui.lbl_status

        self.scope_group = QButtonGroup(self)
        self.scope_group.setExclusive(True)
        self.scope_group.addButton(self.radio_sky_only, 0)
        self.scope_group.addButton(self.radio_whole_image, 1)

        self._is_ready: bool = False
        self._has_prerequisites: bool = False
        self._has_endpoint: bool = False
        self._default_unconf_msg = (
            "GraXpert AI model (3.0.2) is missing or unverified. Zero-strength finishing remains available."
        )

        self.lbl_status.hide()
        self.unconfigured_box.setVisible(True)
        self.configured_box.setVisible(False)
        self._update_run_denoise_enabled()

        self._init_events()

    def _init_events(self) -> None:
        self.slider_strength.valueChanged.connect(self._on_strength_slider_changed)
        self.radio_sky_only.toggled.connect(self._on_scope_toggled)
        self.radio_whole_image.toggled.connect(self._on_scope_toggled)
        self.btn_run_denoise.clicked.connect(self.run_denoise_requested.emit)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

    def _on_strength_slider_changed(self, value: int) -> None:
        self.lbl_strength_value.setText(f"{value}%")
        self._update_run_denoise_enabled()
        self.denoise_strength_changed.emit(float(value))
        self.settings_changed.emit()

    def _on_scope_toggled(self, checked: bool) -> None:
        if checked:
            self.denoise_scope_changed.emit(self.get_scope())
            self.settings_changed.emit()

    def _on_reset_clicked(self) -> None:
        self.set_strength(DEFAULT_DENOISE_STRENGTH_PERCENT)
        self.set_scope(DEFAULT_DENOISE_SCOPE)
        self.reset_requested.emit()
        self.settings_changed.emit()

    def _update_run_denoise_enabled(self) -> None:
        strength = self.get_strength()
        can_run = self._has_prerequisites and (self._is_ready or self._has_endpoint or strength == 0.0)
        self.btn_run_denoise.setEnabled(can_run)

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
        self._update_run_denoise_enabled()

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

    def set_from_project(self, project: FinishProject) -> None:
        """Populate widget controls from active FinishProject settings."""
        settings = project.get_settings()
        self.set_strength(settings.denoise_strength)
        self.set_scope(settings.denoise_scope)

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
        self.slider_strength.setEnabled(has_prerequisites)
        self.radio_sky_only.setEnabled(has_prerequisites)
        self.radio_whole_image.setEnabled(has_prerequisites)
        self.btn_reset.setEnabled(has_prerequisites)
        self._update_run_denoise_enabled()

    @staticmethod
    def _format_provider_label(provider: str) -> str:
        if provider == "CUDAExecutionProvider":
            return "CUDA (GPU)"
        if provider == "CPUExecutionProvider":
            return "CPU"
        return provider


__all__ = ["FinishStarlessSettings"]
