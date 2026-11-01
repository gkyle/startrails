"""Composition of the Finish mode sidebar shell and step cards."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from startrails.lib.finish.defaults import ROLE_SKY_MASK, ROLE_SEPARATED_STARLESS, ROLE_SEPARATED_STARS
from startrails.lib.project_finish import FinishProject
from startrails.ui.file_manager import FileSection
from startrails.ui.sky_mask_settings import SkyMaskSettings
from startrails.ui.steps import StepCard
from startrails.ui.theme import system_theme

if TYPE_CHECKING:
    from startrails.app import App


class SidebarFinish(QWidget):
    """Sidebar widget hosting Finish mode project actions, source section, step cards, and outputs."""

    def __init__(self, parent: Optional[QWidget] = None, app: Optional[App] = None):
        super().__init__(parent)
        self.app = app
        self.setObjectName("SidebarFinish")

        self._init_ui()
        system_theme().register(self)

    def _init_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setSpacing(0)
        self.root_layout.setObjectName("layout")
        self.root_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea(self)
        self.scroll.setObjectName("scroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)

        self.content = QWidget()
        self.content.setObjectName("content")
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setSpacing(8)
        self.contentLayout.setObjectName("contentLayout")
        self.contentLayout.setContentsMargins(8, 8, 8, 8)

        # -------------------------------------------------------------
        # Project Actions (New / Open)
        # -------------------------------------------------------------
        self.projectActions = QHBoxLayout()
        self.projectActions.setSpacing(6)
        self.projectActions.setObjectName("projectActions")

        self.newProject = QPushButton("New Project", self.content)
        self.newProject.setObjectName("newProject")
        self.newProject.setCursor(Qt.PointingHandCursor)
        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton("Open Project", self.content)
        self.openProject.setObjectName("openProject")
        self.openProject.setCursor(Qt.PointingHandCursor)
        self.projectActions.addWidget(self.openProject)

        self.pushButton_newProject = self.newProject
        self.pushButton_openProject = self.openProject
        self.contentLayout.addLayout(self.projectActions)

        # -------------------------------------------------------------
        # Source Image Section
        # -------------------------------------------------------------
        self.sourceFrame = QFrame(self.content)
        self.sourceFrame.setObjectName("sourceFrame")
        self.sourceFrame.setStyleSheet(
            "QFrame#sourceFrame {"
            "    background-color: #ffffff;"
            "    border: 1px solid #e2e8f0;"
            "    border-radius: 8px;"
            "    padding: 8px;"
            "}"
        )
        sourceLayout = QVBoxLayout(self.sourceFrame)
        sourceLayout.setContentsMargins(8, 8, 8, 8)
        sourceLayout.setSpacing(4)

        lbl_section = QLabel("Source Image", self.sourceFrame)
        lbl_section.setStyleSheet("font-size: 13px; font-weight: bold; color: #0f172a;")
        sourceLayout.addWidget(lbl_section)

        self.lbl_source_name = QLabel("No image loaded", self.sourceFrame)
        self.lbl_source_name.setStyleSheet("font-size: 12px; font-weight: 600; color: #334155;")
        self.lbl_source_name.setWordWrap(True)
        sourceLayout.addWidget(self.lbl_source_name)

        self.lbl_source_meta = QLabel("Select an 8-bit or 16-bit RGB image", self.sourceFrame)
        self.lbl_source_meta.setStyleSheet("font-size: 11px; color: #64748b;")
        sourceLayout.addWidget(self.lbl_source_meta)

        btnRow = QHBoxLayout()
        btnRow.setSpacing(6)
        self.btn_import_source = QPushButton("Import Image...", self.sourceFrame)
        self.btn_import_source.setCursor(Qt.PointingHandCursor)
        btnRow.addWidget(self.btn_import_source)

        self.btn_replace_source = QPushButton("Replace Source...", self.sourceFrame)
        self.btn_replace_source.setCursor(Qt.PointingHandCursor)
        self.btn_replace_source.setVisible(False)
        btnRow.addWidget(self.btn_replace_source)

        sourceLayout.addLayout(btnRow)
        self.contentLayout.addWidget(self.sourceFrame)

        # -------------------------------------------------------------
        # Step Cards (1 to 5)
        # -------------------------------------------------------------
        self.skyCard = StepCard(title="Define Sky Region", number=1, expanded=False, parent=self.content)
        self.skyCard.setSubtitle("Detect Sky and refine sky protection mask")
        self.skySettings = SkyMaskSettings(parent=self.content, app=self.app)
        self.skyCard.add_body(self.skySettings)
        self.btn_detect_sky = self.skySettings.ui.detect
        self.contentLayout.addWidget(self.skyCard)

        self.separateCard = StepCard(title="Separate Stars", number=2, expanded=False, parent=self.content)
        self.separateCard.setSubtitle("Separate into starless and stars layers")
        self.contentLayout.addWidget(self.separateCard)

        self.starlessCard = StepCard(title="Finish Starless", number=3, expanded=False, parent=self.content)
        self.starlessCard.setSubtitle("AI denoise and structure/detail enhancement")
        self.contentLayout.addWidget(self.starlessCard)

        self.starsCard = StepCard(title="Finish Stars", number=4, expanded=False, parent=self.content)
        self.starsCard.setSubtitle("Star rounding, faint-star suppression, and glow")
        self.contentLayout.addWidget(self.starsCard)

        self.recombineCard = StepCard(title="Recombine & Save", number=5, expanded=False, parent=self.content)
        self.recombineCard.setSubtitle("Blend layers and export image")

        recombineBody = QWidget()
        recombineBodyLayout = QVBoxLayout(recombineBody)
        recombineBodyLayout.setContentsMargins(4, 4, 4, 4)
        recombineBodyLayout.setSpacing(6)

        self.btn_save_output = QPushButton("Save Image", recombineBody)
        self.btn_save_output.setCursor(Qt.PointingHandCursor)
        self.btn_save_output.setStyleSheet("font-weight: 600; padding: 6px;")
        recombineBodyLayout.addWidget(self.btn_save_output)

        self.recombineCard.add_body(recombineBody)
        self.contentLayout.addWidget(self.recombineCard)

        self._step_cards = (self.skyCard, self.separateCard, self.starlessCard, self.starsCard, self.recombineCard)
        for card in self._step_cards:
            card.expanded.connect(lambda c=card: self._collapse_other_steps(c))

        # -------------------------------------------------------------
        # Output Files Section
        # -------------------------------------------------------------
        self.outputFiles = FileSection(title="Output Files", inputs=False, parent=self.content)
        self.outputFiles.setObjectName("outputFiles")
        self.outputFiles.setProperty("show_legend", False)
        self.outputFiles.setProperty("is_expanded", True)
        self.outputs = self.outputFiles
        self.contentLayout.addWidget(self.outputFiles)

        self.contentLayout.addStretch(1)
        self.scroll.setWidget(self.content)
        self.root_layout.addWidget(self.scroll)

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def update_from_project(self, project: FinishProject, dimensions: Optional[tuple[int, int]]) -> None:
        """Update source card information and step prerequisites from active project."""
        if project.source_file is not None:
            name = project.source_file.basename or Path(project.source_file.path).name
            self.lbl_source_name.setText(name)
            depth = project.source_bit_depth
            fmt = Path(project.source_file.path).suffix.lstrip(".").upper()
            if not project.source_is_current():
                self.lbl_source_meta.setText("Source changed or unavailable; import it again")
            elif dimensions:
                self.lbl_source_meta.setText(f"{dimensions[0]} × {dimensions[1]} px • {depth}-bit {fmt}")
            else:
                self.lbl_source_meta.setText(f"{depth}-bit {fmt}")
            self.btn_import_source.setVisible(False)
            self.btn_replace_source.setVisible(True)
        else:
            self.lbl_source_name.setText("No image loaded")
            self.lbl_source_meta.setText("Select an 8-bit or 16-bit RGB image")
            self.btn_import_source.setVisible(True)
            self.btn_replace_source.setVisible(False)

        self.update_prerequisites(project)

    def update_prerequisites(self, project: FinishProject) -> None:
        """Update enabled states and subtitles according to stage prerequisite availability."""
        has_source = project.source_is_current()
        has_mask = project.current_artifact_path(ROLE_SKY_MASK) is not None
        has_starless = project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None
        has_stars = project.current_artifact_path(ROLE_SEPARATED_STARS) is not None

        if hasattr(self, "skySettings"):
            self.skySettings.refresh_inputs(has_source=has_source)

        if not has_source:
            self.skyCard.setStatus("locked", "Prerequisite: Source image required")
            self.separateCard.setStatus("locked", "Prerequisite: Source image required")
            self.starlessCard.setStatus("locked", "Prerequisite: Source image required")
            self.starsCard.setStatus("locked", "Prerequisite: Source image required")
            self.recombineCard.setStatus("locked", "Prerequisite: Source image required")
            self.btn_save_output.setEnabled(False)
            return

        if has_mask:
            self.skyCard.setStatus("done", "Sky mask defined")
        else:
            self.skyCard.setStatus("ready", "Ready to define sky region")

        if not has_mask:
            self.separateCard.setStatus("locked", "Prerequisite: Sky region required")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.starsCard.setStatus("locked", "Prerequisite: Separated stars required")
            self.recombineCard.setStatus("ready", "Ready to export source")
            self.btn_save_output.setEnabled(True)
            return

        if not (has_starless and has_stars):
            self.separateCard.setStatus("ready", "Ready to separate stars")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.starsCard.setStatus("locked", "Prerequisite: Separated stars required")
            self.recombineCard.setStatus("ready", "Ready to export source")
            self.btn_save_output.setEnabled(True)
            return

        self.separateCard.setStatus("done", "Stars separated")
        self.starlessCard.setStatus("ready", "Ready to finish starless")
        self.starsCard.setStatus("ready", "Ready to finish stars")
        self.recombineCard.setStatus("ready", "Ready to recombine")
        self.btn_save_output.setEnabled(True)


__all__ = ["SidebarFinish"]
