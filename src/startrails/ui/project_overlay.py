"""Welcome and Project Selection Overlay for StarTrails AI.

Supports selecting between "Star Trails" and "Denoise" workflows for:
1. Application startup without an open project
2. "New Project" workflow selection
3. "Open Project" workflow selection
"""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Literal, override
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QColor, QFont, QIcon, QKeyEvent, QPainter, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QSizePolicy,
)

from startrails.lib.recent import get_recent_projects
from startrails.lib.project_type import (
    STARTRAILS_EXT,
    DENOISE_EXT,
    LEGACY_STARTRAILS_EXT,
    TYPE_STARTRAILS,
    TYPE_DENOISE,
    detect_project_type_from_path,
)
from startrails.ui.theme import system_theme, is_dark
import startrails.ui.resources_rc


def _load_project_pixmap(project_type: str) -> QPixmap:
    """Load project icon from Qt resources with filesystem fallback."""
    pix = QPixmap(f":/startrails/ui/project_{project_type}.png")
    if pix.isNull():
        disk_path = Path(__file__).resolve().parent / "icons" / f"project_{project_type}.png"
        if disk_path.exists():
            pix = QPixmap(str(disk_path))
    return pix


OverlayMode = Literal["welcome", "new", "open"]


class ClickableCard(QFrame):
    """QFrame that emits clicked signal on mouse release."""

    clicked = Signal()

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)

    @override
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class ProjectWelcomeOverlay(QWidget):
    """Semi-transparent modal overlay prompting the user to create or open

    either a Star Trails or Denoise project.
    """

    createStarTrailsRequested = Signal()
    createDenoiseRequested = Signal()
    openStarTrailsRequested = Signal()
    openDenoiseRequested = Signal()
    projectSelected = Signal(str)       # Emits selected project path to load
    browseRequested = Signal()          # Emits when user chooses to browse any project file on disk
    dismissed = Signal()                # Emits when user dismisses the overlay

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("ProjectWelcomeOverlay")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._mode: OverlayMode = "welcome"
        self._can_dismiss: bool = False

        self._init_ui()
        system_theme().register(self)

    def _init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 24, 24, 24)
        root_layout.setAlignment(Qt.AlignCenter)

        # Card container
        self.card = QFrame(self)
        self.card.setObjectName("WelcomeCard")
        self.card.setFixedWidth(780)

        card_layout = QVBoxLayout(self.card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(16)

        # -------------------------------------------------------------
        # Header (Logo, Title, Subtitle, Close Button)
        # -------------------------------------------------------------
        header_layout = QHBoxLayout()
        header_layout.setSpacing(14)

        # Logo badge
        lbl_logo = QLabel("ST", self.card)
        lbl_logo.setObjectName("OverlayLogoBadge")
        lbl_logo.setFixedSize(40, 40)
        lbl_logo.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_logo)

        # Title text block
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        self.lbl_title = QLabel("Welcome to StarTrails AI", self.card)
        self.lbl_title.setObjectName("OverlayTitle")
        self.lbl_subtitle = QLabel("Select a project workflow to get started", self.card)
        self.lbl_subtitle.setObjectName("OverlaySubtitle")
        title_box.addWidget(self.lbl_title)
        title_box.addWidget(self.lbl_subtitle)
        header_layout.addLayout(title_box, 1)

        # Close button
        self.btn_close = QPushButton("✕", self.card)
        self.btn_close.setObjectName("OverlayCloseBtn")
        self.btn_close.setFixedSize(32, 32)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setToolTip("Dismiss")
        self.btn_close.clicked.connect(self._on_close_clicked)
        header_layout.addWidget(self.btn_close)

        card_layout.addLayout(header_layout)

        # -------------------------------------------------------------
        # Mode Selection: Side-by-Side Cards (Star Trails vs. Denoise)
        # -------------------------------------------------------------
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(18)
        cards_layout.setContentsMargins(0, 4, 0, 4)

        # Card 1: Star Trails
        self.card_startrails = ClickableCard(self.card)
        self.card_startrails.setObjectName("OptionCardStarTrails")
        layout_st = QVBoxLayout(self.card_startrails)
        layout_st.setContentsMargins(18, 16, 18, 18)
        layout_st.setSpacing(10)
        layout_st.setAlignment(Qt.AlignTop)

        # Icon
        self.lbl_icon_st = QLabel(self.card_startrails)
        self.lbl_icon_st.setObjectName("OverlayIcon")
        self.lbl_icon_st.setAlignment(Qt.AlignCenter)
        self.lbl_icon_st.setFixedHeight(175)
        st_pix = _load_project_pixmap("startrails")
        if not st_pix.isNull():
            self.lbl_icon_st.setPixmap(st_pix.scaled(176, 174, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout_st.addWidget(self.lbl_icon_st)

        # Title & Badge
        lbl_st_title = QLabel("Star Trails", self.card_startrails)
        lbl_st_title.setObjectName("CardHeaderTitle")
        lbl_st_title.setAlignment(Qt.AlignCenter)
        layout_st.addWidget(lbl_st_title)

        lbl_st_desc = QLabel(
            "Align & stack time-lapse sequences with AI satellite streak removal and gap filling.",
            self.card_startrails,
        )
        lbl_st_desc.setObjectName("CardDescription")
        lbl_st_desc.setWordWrap(True)
        lbl_st_desc.setAlignment(Qt.AlignCenter)
        lbl_st_desc.setFixedHeight(38)
        layout_st.addWidget(lbl_st_desc)

        layout_st.addSpacing(4)

        # Action Buttons for Star Trails
        self.btn_st_new = QPushButton("New Star Trails Project", self.card_startrails)
        self.btn_st_new.setObjectName("PrimaryActionButton")
        self.btn_st_new.setFixedHeight(34)
        self.btn_st_new.setCursor(Qt.PointingHandCursor)
        self.btn_st_new.clicked.connect(self._on_st_new_clicked)
        layout_st.addWidget(self.btn_st_new)

        self.btn_st_open = QPushButton("Open Star Trails...", self.card_startrails)
        self.btn_st_open.setObjectName("SecondaryActionButton")
        self.btn_st_open.setFixedHeight(34)
        self.btn_st_open.setCursor(Qt.PointingHandCursor)
        self.btn_st_open.clicked.connect(self._on_st_open_clicked)
        layout_st.addWidget(self.btn_st_open)

        self.card_startrails.clicked.connect(self._on_card_st_clicked)
        cards_layout.addWidget(self.card_startrails, 1)

        # Card 2: Denoise
        self.card_denoise = ClickableCard(self.card)
        self.card_denoise.setObjectName("OptionCardDenoise")
        layout_dn = QVBoxLayout(self.card_denoise)
        layout_dn.setContentsMargins(18, 16, 18, 18)
        layout_dn.setSpacing(10)
        layout_dn.setAlignment(Qt.AlignTop)

        # Icon
        self.lbl_icon_dn = QLabel(self.card_denoise)
        self.lbl_icon_dn.setObjectName("OverlayIcon")
        self.lbl_icon_dn.setAlignment(Qt.AlignCenter)
        self.lbl_icon_dn.setFixedHeight(175)
        dn_pix = _load_project_pixmap("denoise")
        if not dn_pix.isNull():
            self.lbl_icon_dn.setPixmap(dn_pix.scaled(176, 174, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        layout_dn.addWidget(self.lbl_icon_dn)

        # Title & Badge
        lbl_dn_title = QLabel("Astro Denoise", self.card_denoise)
        lbl_dn_title.setObjectName("CardHeaderTitle")
        lbl_dn_title.setAlignment(Qt.AlignCenter)
        layout_dn.addWidget(lbl_dn_title)

        lbl_dn_desc = QLabel(
            "Dual sky/ground alignment with AI landscape mask generation and horizon blending.",
            self.card_denoise,
        )
        lbl_dn_desc.setObjectName("CardDescription")
        lbl_dn_desc.setWordWrap(True)
        lbl_dn_desc.setAlignment(Qt.AlignCenter)
        lbl_dn_desc.setFixedHeight(38)
        layout_dn.addWidget(lbl_dn_desc)

        layout_dn.addSpacing(4)

        # Action Buttons for Denoise
        self.btn_dn_new = QPushButton("New Denoise Project", self.card_denoise)
        self.btn_dn_new.setObjectName("PrimaryActionButton")
        self.btn_dn_new.setFixedHeight(34)
        self.btn_dn_new.setCursor(Qt.PointingHandCursor)
        self.btn_dn_new.clicked.connect(self._on_dn_new_clicked)
        layout_dn.addWidget(self.btn_dn_new)

        self.btn_dn_open = QPushButton("Open Denoise...", self.card_denoise)
        self.btn_dn_open.setObjectName("SecondaryActionButton")
        self.btn_dn_open.setFixedHeight(34)
        self.btn_dn_open.setCursor(Qt.PointingHandCursor)
        self.btn_dn_open.clicked.connect(self._on_dn_open_clicked)
        layout_dn.addWidget(self.btn_dn_open)

        self.card_denoise.clicked.connect(self._on_card_dn_clicked)
        cards_layout.addWidget(self.card_denoise, 1)

        card_layout.addLayout(cards_layout)

        # -------------------------------------------------------------
        # Footer: Recent Projects & Browse All Files
        # -------------------------------------------------------------
        self.footer_frame = QFrame(self.card)
        self.footer_frame.setObjectName("OverlayFooterFrame")
        layout_footer = QVBoxLayout(self.footer_frame)
        layout_footer.setContentsMargins(14, 10, 14, 10)
        layout_footer.setSpacing(6)

        lbl_recent_title = QLabel("Recent Projects", self.footer_frame)
        lbl_recent_title.setObjectName("FooterSectionTitle")
        layout_footer.addWidget(lbl_recent_title)

        row_recent = QHBoxLayout()
        row_recent.setSpacing(8)

        self.combo_recent = QComboBox(self.footer_frame)
        self.combo_recent.setFixedHeight(32)
        self.combo_recent.setCursor(Qt.PointingHandCursor)
        self.combo_recent.activated.connect(self._on_combo_activated)
        row_recent.addWidget(self.combo_recent, 1)

        self.btn_open_recent = QPushButton("Open", self.footer_frame)
        self.btn_open_recent.setObjectName("RecentOpenBtn")
        self.btn_open_recent.setFixedHeight(32)
        self.btn_open_recent.setFixedWidth(64)
        self.btn_open_recent.setCursor(Qt.PointingHandCursor)
        self.btn_open_recent.clicked.connect(self._on_open_recent_clicked)
        row_recent.addWidget(self.btn_open_recent)

        self.btn_browse_all = QPushButton("Browse Files...", self.footer_frame)
        self.btn_browse_all.setObjectName("SecondaryActionButton")
        self.btn_browse_all.setFixedHeight(32)
        self.btn_browse_all.setCursor(Qt.PointingHandCursor)
        self.btn_browse_all.clicked.connect(self._on_browse_all_clicked)
        row_recent.addWidget(self.btn_browse_all)

        layout_footer.addLayout(row_recent)
        card_layout.addWidget(self.footer_frame)

        # Cancel button bar (hidden in welcome mode, visible in new/open modes)
        self.cancel_row = QHBoxLayout()
        self.cancel_row.setContentsMargins(0, 0, 0, 0)
        self.cancel_row.addStretch(1)
        self.btn_cancel = QPushButton("Cancel", self.card)
        self.btn_cancel.setObjectName("SecondaryActionButton")
        self.btn_cancel.setFixedHeight(32)
        self.btn_cancel.setFixedWidth(90)
        self.btn_cancel.setCursor(Qt.PointingHandCursor)
        self.btn_cancel.clicked.connect(self._on_close_clicked)
        self.cancel_row.addWidget(self.btn_cancel)
        card_layout.addLayout(self.cancel_row)

        root_layout.addWidget(self.card)

        self._apply_stylesheet()
        self.refresh_recent_projects()

    def _apply_stylesheet(self):
        """Set stylesheet styling for the overlay and cards."""
        self.setStyleSheet("""
            #ProjectWelcomeOverlay {
                background-color: rgba(15, 23, 42, 0.78);
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Arial, sans-serif;
            }
            QFrame#WelcomeCard {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 14px;
            }
            QLabel#OverlayLogoBadge {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0284c7, stop:1 #0369a1);
                color: #ffffff;
                font-size: 16px;
                font-weight: 800;
                border-radius: 8px;
            }
            QLabel#OverlayTitle {
                color: #0f172a;
                font-size: 19px;
                font-weight: 700;
            }
            QLabel#OverlaySubtitle {
                color: #64748b;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton#OverlayCloseBtn {
                background-color: transparent;
                border: none;
                border-radius: 16px;
                color: #64748b;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#OverlayCloseBtn:hover {
                background-color: #f1f5f9;
                color: #0f172a;
            }
            QPushButton#OverlayCloseBtn:pressed {
                background-color: #e2e8f0;
            }
            QFrame#OptionCardStarTrails, QFrame#OptionCardDenoise {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
            }
            QFrame#OptionCardStarTrails:hover, QFrame#OptionCardDenoise:hover {
                border-color: #0284c7;
                background-color: #f0f9ff;
            }
            QLabel#CardHeaderTitle {
                color: #0f172a;
                font-size: 16px;
                font-weight: 700;
            }
            QLabel#CardDescription {
                color: #64748b;
                font-size: 12px;
                line-height: 1.3;
            }
            QPushButton#PrimaryActionButton {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                border: none;
                border-radius: 6px;
                padding: 4px 12px;
            }
            QPushButton#PrimaryActionButton:hover {
                background-color: #0369a1;
            }
            QPushButton#PrimaryActionButton:pressed {
                background-color: #0c4a6e;
            }
            QPushButton#SecondaryActionButton {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                color: #334155;
                font-size: 12px;
                font-weight: 500;
                padding: 4px 12px;
            }
            QPushButton#SecondaryActionButton:hover {
                background-color: #f1f5f9;
                border-color: #94a3b8;
                color: #0f172a;
            }
            QPushButton#SecondaryActionButton:pressed {
                background-color: #e2e8f0;
            }
            QFrame#OverlayFooterFrame {
                background-color: #f8fafc;
                border: 1px solid #e2e8f0;
                border-radius: 10px;
            }
            QLabel#FooterSectionTitle {
                color: #334155;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton#RecentOpenBtn {
                background-color: #0284c7;
                color: #ffffff;
                font-size: 12px;
                font-weight: 600;
                border: none;
                border-radius: 6px;
            }
            QPushButton#RecentOpenBtn:hover {
                background-color: #0369a1;
            }
            QPushButton#RecentOpenBtn:disabled {
                background-color: #94a3b8;
                color: #e2e8f0;
            }
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 4px 10px;
                color: #0f172a;
                font-size: 12px;
            }
            QComboBox:hover {
                border-color: #94a3b8;
            }
        """)

    def set_overlay_mode(self, mode: OverlayMode = "welcome", can_dismiss: bool = True):
        """Configure overlay display for welcome, new project, or open project workflow."""
        self._mode = mode
        self._can_dismiss = can_dismiss

        self.btn_close.setVisible(can_dismiss)
        self.btn_cancel.setVisible(can_dismiss and mode in ("new", "open"))

        if mode == "welcome":
            self.lbl_title.setText("Welcome to StarTrails AI")
            self.lbl_subtitle.setText("Select a project workflow to get started")
            self.btn_st_new.setText("New Star Trails Project")
            self.btn_st_new.setVisible(True)
            self.btn_st_open.setText("Open Existing...")
            self.btn_st_open.setVisible(True)

            self.btn_dn_new.setText("New Denoise Project")
            self.btn_dn_new.setVisible(True)
            self.btn_dn_open.setText("Open Existing...")
            self.btn_dn_open.setVisible(True)

            self.footer_frame.setVisible(True)

        elif mode == "new":
            self.lbl_title.setText("Create New Project")
            self.lbl_subtitle.setText("Choose workflow type for your new project")
            self.btn_st_new.setText("Create Star Trails Project")
            self.btn_st_new.setVisible(True)
            self.btn_st_open.setVisible(False)

            self.btn_dn_new.setText("Create Denoise Project")
            self.btn_dn_new.setVisible(True)
            self.btn_dn_open.setVisible(False)

            self.footer_frame.setVisible(False)

        elif mode == "open":
            self.lbl_title.setText("Open Project")
            self.lbl_subtitle.setText("Select workflow type or pick from recent projects")
            self.btn_st_new.setVisible(False)
            self.btn_st_open.setText("Open Star Trails Project...")
            self.btn_st_open.setVisible(True)

            self.btn_dn_new.setVisible(False)
            self.btn_dn_open.setText("Open Denoise Project...")
            self.btn_dn_open.setVisible(True)

            self.footer_frame.setVisible(True)

        self.refresh_recent_projects()

    def refresh_recent_projects(self):
        """Repopulate recent projects dropdown."""
        self.combo_recent.clear()
        recent = get_recent_projects()

        if not recent:
            self.combo_recent.addItem("No recent projects found", None)
            self.btn_open_recent.setEnabled(False)
            return

        for p in recent:
            ptype = detect_project_type_from_path(p)
            tag = "[Denoise]" if ptype == TYPE_DENOISE else "[Star Trails]"
            label = f"{tag} {p.name}  —  {p.parent}"
            self.combo_recent.addItem(label, str(p))

        self.btn_open_recent.setEnabled(True)

    # -------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------
    def _on_card_st_clicked(self):
        if self._mode == "new":
            self._on_st_new_clicked()
        elif self._mode == "open":
            self._on_st_open_clicked()

    def _on_card_dn_clicked(self):
        if self._mode == "new":
            self._on_dn_new_clicked()
        elif self._mode == "open":
            self._on_dn_open_clicked()

    def _on_st_new_clicked(self):
        self.createStarTrailsRequested.emit()

    def _on_st_open_clicked(self):
        self.openStarTrailsRequested.emit()

    def _on_dn_new_clicked(self):
        self.createDenoiseRequested.emit()

    def _on_dn_open_clicked(self):
        self.openDenoiseRequested.emit()

    def _on_open_recent_clicked(self):
        data = self.combo_recent.currentData()
        if data:
            self.projectSelected.emit(str(data))

    def _on_combo_activated(self, index: int):
        data = self.combo_recent.itemData(index)
        if data:
            self.projectSelected.emit(str(data))

    def _on_browse_all_clicked(self):
        self.browseRequested.emit()

    def _on_close_clicked(self):
        if self._can_dismiss:
            self.dismissed.emit()
            self.hide()

    @override
    def mousePressEvent(self, event):
        # Prevent clicks on the dark backdrop from passing through to underlying controls
        event.accept()

    @override
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key_Escape:
            if self._can_dismiss:
                self._on_close_clicked()
            event.accept()
            return
        super().keyPressEvent(event)
