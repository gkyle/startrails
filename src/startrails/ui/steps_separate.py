"""Settings and setup controls widget for Step 2: Separate Stars."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import QSignalBlocker, Signal
from PySide6.QtWidgets import QWidget

from startrails.lib.finish.starnet import DEFAULT_STRIDE, MAX_STRIDE, MIN_STRIDE
from .ui_step_separate import Ui_SeparateStarsSettings


class SeparateStarsSettings(QWidget):
    """Card body widget for Separate Stars handling dependency setup and separation settings."""

    setup_requested = Signal()
    browse_requested = Signal()
    repair_requested = Signal()
    change_requested = Signal()
    run_separation_requested = Signal()
    stride_changed = Signal(int)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.ui = Ui_SeparateStarsSettings()
        self.ui.setupUi(self)

        # Backward compatibility aliases for existing tests and call sites
        self.unconfigured_box = self.ui.unconfigured_box
        self.configured_box = self.ui.configured_box
        self.lbl_unconf_msg = self.ui.lbl_unconf_msg
        self.btn_setup_starnet = self.ui.btn_setup_starnet
        self.btn_browse_starnet = self.ui.btn_browse_starnet
        self.lbl_starnet_info = self.ui.lbl_starnet_info
        self.btn_repair = self.ui.btn_repair
        self.btn_change = self.ui.btn_change
        self.combo_stride = self.ui.combo_stride
        self.btn_separate = self.ui.btn_separate
        self.lbl_status = self.ui.lbl_status

        self._default_unconf_msg = "StarNet2 is required to separate stars from the sky background."
        self._standard_strides = ((DEFAULT_STRIDE, "Standard"), (128, "Fine"), (64, "Very Fine"))

        self.lbl_status.hide()
        self._init_events()
        self._init_strides()

    def _init_events(self) -> None:
        self.btn_setup_starnet.clicked.connect(self.setup_requested.emit)
        self.btn_browse_starnet.clicked.connect(self.browse_requested.emit)
        self.btn_repair.clicked.connect(self.repair_requested.emit)
        self.btn_change.clicked.connect(self.change_requested.emit)
        self.btn_separate.clicked.connect(self.run_separation_requested.emit)
        self.combo_stride.currentIndexChanged.connect(lambda _index: self.stride_changed.emit(self.get_stride()))
        self.combo_stride.currentIndexChanged.connect(lambda _index: self._cleanup_custom_stride_items())

    def _init_strides(self) -> None:
        for stride, label in self._standard_strides:
            self.combo_stride.addItem(f"{stride} ({label})", stride)

    def refresh_status(self, status: Dict[str, Any], has_prerequisites: bool = True) -> None:
        """Update widget layout and enabled state according to StarNet status and prerequisites."""
        is_configured = status.get("configured", False)
        self.unconfigured_box.setVisible(not is_configured)
        self.configured_box.setVisible(is_configured)
        notice = status.get("setup_notice")
        self.btn_setup_starnet.setEnabled(notice is None)
        if notice is not None:
            self.lbl_unconf_msg.setText(notice)
        else:
            self.lbl_unconf_msg.setText(self._default_unconf_msg)

        if is_configured:
            version = status.get("version", "2.6.2")
            build = status.get("build", "")
            backend = status.get("backend_id", "")
            managed_str = "Managed" if status.get("managed", False) else "Custom"
            details = f"v{version}-{build} ({backend}) • {managed_str}" if build else f"v{version}"
            self.lbl_starnet_info.setText(f"StarNet2 {details}")
            self.btn_separate.setEnabled(has_prerequisites)
        else:
            self.btn_separate.setEnabled(False)

    def get_stride(self) -> int:
        return self.combo_stride.currentData()

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

        CLI-valid strides outside the preset list are shown as a temporary custom
        entry instead of raising or silently falling back to the default.
        """
        if (
            not isinstance(stride, int)
            or stride < MIN_STRIDE
            or stride > MAX_STRIDE
            or stride % 2 != 0
        ):
            raise ValueError(
                f"StarNet stride must be an even integer between {MIN_STRIDE} and {MAX_STRIDE}, got {stride}"
            )
        standard_values = {s for s, _ in self._standard_strides}
        with QSignalBlocker(self.combo_stride):
            self.combo_stride.clear()
            for s, label in self._standard_strides:
                self.combo_stride.addItem(f"{s} ({label})", s)
            if stride not in standard_values:
                self.combo_stride.addItem(f"{stride} (Custom)", stride)
            index = self.combo_stride.findData(stride)
            self.combo_stride.setCurrentIndex(index)


__all__ = ["SeparateStarsSettings"]
