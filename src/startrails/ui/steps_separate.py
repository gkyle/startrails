"""Settings and setup controls widget for Step 2: Separate Stars."""

from __future__ import annotations

from typing import Any, Dict, Optional

from PySide6.QtCore import Qt, Signal

from startrails.lib.finish.starnet import DEFAULT_STRIDE
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class SeparateStarsSettings(QWidget):
    """Card body widget for Separate Stars handling dependency setup and separation settings."""

    setup_requested = Signal()
    browse_requested = Signal()
    repair_requested = Signal()
    change_requested = Signal()
    run_separation_requested = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("SeparateStarsSettings")
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        # -------------------------------------------------------------
        # Unconfigured Container (Set Up / Use Existing)
        # -------------------------------------------------------------
        self.unconfigured_box = QFrame(self)
        self.unconfigured_box.setObjectName("unconfiguredBox")
        self.unconfigured_box.setStyleSheet(
            "QFrame#unconfiguredBox {"
            "    background-color: #fffbeb;"
            "    border: 1px solid #fef3c7;"
            "    border-radius: 6px;"
            "    padding: 8px;"
            "}"
        )
        unconf_layout = QVBoxLayout(self.unconfigured_box)
        unconf_layout.setContentsMargins(6, 6, 6, 6)
        unconf_layout.setSpacing(6)

        self.lbl_unconf_msg = QLabel("StarNet2 is required to separate stars from the sky background.", self)
        self.lbl_unconf_msg.setWordWrap(True)
        self.lbl_unconf_msg.setStyleSheet("color: #92400e; font-size: 11px; line-height: 1.3;")
        unconf_layout.addWidget(self.lbl_unconf_msg)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self.btn_setup_starnet = QPushButton("Set Up StarNet2…", self.unconfigured_box)
        self.btn_setup_starnet.setCursor(Qt.PointingHandCursor)
        self.btn_setup_starnet.setStyleSheet(
            "QPushButton { background-color: #d97706; color: white; border-radius: 4px; "
            "padding: 5px 10px; font-weight: 600; font-size: 11px; } "
            "QPushButton:hover { background-color: #b45309; }"
        )
        self.btn_setup_starnet.clicked.connect(self.setup_requested.emit)
        btn_row.addWidget(self.btn_setup_starnet)

        self.btn_browse_starnet = QPushButton("Use Existing…", self.unconfigured_box)
        self.btn_browse_starnet.setCursor(Qt.PointingHandCursor)
        self.btn_browse_starnet.setStyleSheet(
            "QPushButton { background-color: #ffffff; color: #475569; border: 1px solid #cbd5e1; "
            "border-radius: 4px; padding: 5px 10px; font-size: 11px; } "
            "QPushButton:hover { background-color: #f1f5f9; }"
        )
        self.btn_browse_starnet.clicked.connect(self.browse_requested.emit)
        btn_row.addWidget(self.btn_browse_starnet)

        unconf_layout.addLayout(btn_row)
        layout.addWidget(self.unconfigured_box)

        # -------------------------------------------------------------
        # Configured Container (StarNet info, Stride, Run)
        # -------------------------------------------------------------
        self.configured_box = QWidget(self)
        conf_layout = QVBoxLayout(self.configured_box)
        conf_layout.setContentsMargins(0, 0, 0, 0)
        conf_layout.setSpacing(6)

        # Installation identity header
        header_row = QHBoxLayout()
        header_row.setSpacing(4)

        self.lbl_starnet_info = QLabel("StarNet2 Ready", self.configured_box)
        self.lbl_starnet_info.setStyleSheet("font-size: 11px; font-weight: 600; color: #1e293b;")
        header_row.addWidget(self.lbl_starnet_info)
        header_row.addStretch(1)

        self.btn_repair = QPushButton("Repair", self.configured_box)
        self.btn_repair.setCursor(Qt.PointingHandCursor)
        self.btn_repair.setStyleSheet(
            "QPushButton { border: none; color: #0284c7; font-size: 11px; text-decoration: underline; background: transparent; } "
            "QPushButton:hover { color: #0369a1; }"
        )
        self.btn_repair.clicked.connect(self.repair_requested.emit)
        header_row.addWidget(self.btn_repair)

        self.btn_change = QPushButton("Change…", self.configured_box)
        self.btn_change.setCursor(Qt.PointingHandCursor)
        self.btn_change.setStyleSheet(
            "QPushButton { border: none; color: #64748b; font-size: 11px; text-decoration: underline; background: transparent; } "
            "QPushButton:hover { color: #334155; }"
        )
        self.btn_change.clicked.connect(self.change_requested.emit)
        header_row.addWidget(self.btn_change)

        conf_layout.addLayout(header_row)

        # Stride control
        stride_row = QHBoxLayout()
        stride_row.setSpacing(6)
        lbl_stride = QLabel("Stride:", self.configured_box)
        lbl_stride.setStyleSheet("font-size: 11px; color: #475569;")
        stride_row.addWidget(lbl_stride)

        self.combo_stride = QComboBox(self.configured_box)
        for stride, label in ((DEFAULT_STRIDE, "Standard"), (128, "Fine"), (64, "Very Fine")):
            self.combo_stride.addItem(f"{stride} ({label})", stride)
        self.combo_stride.setStyleSheet("font-size: 11px; padding: 2px 4px;")
        stride_row.addWidget(self.combo_stride)
        stride_row.addStretch(1)
        conf_layout.addLayout(stride_row)

        # Separate Stars Action Button
        self.btn_separate = QPushButton("Separate Stars", self.configured_box)
        self.btn_separate.setCursor(Qt.PointingHandCursor)
        self.btn_separate.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; border-radius: 4px; "
            "padding: 6px 12px; font-weight: 600; font-size: 12px; } "
            "QPushButton:disabled { background-color: #94a3b8; } "
            "QPushButton:hover:!disabled { background-color: #0369a1; }"
        )
        # Step 6 exposes setup; the processing action is wired in Step 7.
        self.btn_separate.setEnabled(False)
        self.btn_separate.hide()
        self.btn_separate.clicked.connect(self.run_separation_requested.emit)
        conf_layout.addWidget(self.btn_separate)

        layout.addWidget(self.configured_box)

        # Status / Error label
        self.lbl_status = QLabel("", self)
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size: 11px; color: #dc2626;")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

    def refresh_status(self, status: Dict[str, Any], has_prerequisites: bool = True) -> None:
        """Update widget layout and enabled state according to StarNet status and prerequisites."""
        is_configured = status.get("configured", False)
        self.unconfigured_box.setVisible(not is_configured)
        self.configured_box.setVisible(is_configured)
        notice = status.get("setup_notice")
        self.btn_setup_starnet.setEnabled(notice is None)
        if notice is not None:
            self.lbl_unconf_msg.setText(notice)

        if is_configured:
            version = status.get("version", "2.6.2")
            build = status.get("build", "")
            backend = status.get("backend_id", "")
            managed_str = "Managed" if status.get("managed", False) else "Custom"
            details = f"v{version}-{build} ({backend}) • {managed_str}" if build else f"v{version}"
            self.lbl_starnet_info.setText(f"StarNet2 {details}")
            self.btn_separate.setEnabled(False)
        else:
            self.btn_separate.setEnabled(False)

    def get_stride(self) -> int:
        return self.combo_stride.currentData()


__all__ = ["SeparateStarsSettings"]
