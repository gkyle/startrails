"""Composition of the Finish mode sidebar shell and step cards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from startrails.lib.finish.defaults import (
    ROLE_FINISHED_COMPOSITE,
    ROLE_SKY_MASK,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
)
from startrails.lib.project_finish import FinishProject
from startrails.ui.file_manager import FileSection
from startrails.ui.sky_mask_settings import SkyMaskSettings
from startrails.ui.steps import StepCard
from startrails.ui.steps_separate import SeparateStarsSettings
from startrails.ui.theme import system_theme

if TYPE_CHECKING:
    from startrails.app import App


class SidebarFinish(QWidget):
    """Sidebar widget hosting Finish mode project actions, file sections, step cards, and outputs."""

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
        # Input Files Section (single source image)
        # -------------------------------------------------------------
        self.inputFiles = FileSection(title="Input Files", inputs=True, parent=self.content)
        self.inputFiles.setObjectName("inputFiles")
        self.inputFiles.setProperty("show_legend", False)
        self.inputFiles.setProperty("is_expanded", True)
        self.contentLayout.addWidget(self.inputFiles)

        # -------------------------------------------------------------
        # Output Files Section
        # -------------------------------------------------------------
        self.outputFiles = FileSection(title="Output Files", inputs=False, parent=self.content)
        self.outputFiles.setObjectName("outputFiles")
        self.outputFiles.setProperty("show_legend", False)
        self.outputFiles.setProperty("is_expanded", True)
        self.outputs = self.outputFiles
        self.contentLayout.addWidget(self.outputFiles)

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
        self.separateSettings = SeparateStarsSettings(parent=self.content)
        self.separateCard.add_body(self.separateSettings)
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

        self.contentLayout.addStretch(1)
        self.scroll.setWidget(self.content)
        self.root_layout.addWidget(self.scroll)

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def update_from_project(self, project: FinishProject, dimensions: Optional[tuple[int, int]]) -> None:
        """Update file sections and step prerequisites from active project."""
        self.separateSettings.set_stride(project.starnet_stride)
        self.update_prerequisites(project)

    def update_prerequisites(self, project: FinishProject) -> None:
        """Update enabled states and subtitles according to stage prerequisite availability."""
        has_source = project.source_is_current()
        has_mask = project.current_artifact_path(ROLE_SKY_MASK) is not None
        has_starless = project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None
        has_stars = project.current_artifact_path(ROLE_SEPARATED_STARS) is not None
        has_composite = project.current_artifact_path(ROLE_FINISHED_COMPOSITE) is not None

        if hasattr(self, "skySettings"):
            self.skySettings.refresh_inputs(has_source=has_source)

        starnet_status = {}
        if (
            hasattr(self, "app")
            and self.app
            and hasattr(self.app, "workflow")
            and hasattr(self.app.workflow, "get_starnet_status")
        ):
            starnet_status = self.app.workflow.get_starnet_status()

        if hasattr(self, "separateSettings"):
            self.separateSettings.refresh_status(starnet_status, has_prerequisites=has_source and has_mask)

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
            self.recombineCard.setStatus("locked", "Prerequisite: Sky region required")
            self.btn_save_output.setEnabled(False)
            return

        if not (has_starless and has_stars):
            if not starnet_status.get("configured", False):
                self.separateCard.setStatus("ready", "StarNet2 setup required")
            else:
                self.separateCard.setStatus("ready", "Ready to separate stars")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.starsCard.setStatus("locked", "Prerequisite: Separated stars required")
            self.recombineCard.setStatus("locked", "Prerequisite: Separated layers required")
            self.btn_save_output.setEnabled(False)
            return

        self.separateCard.setStatus("done", "Stars separated")
        self.starlessCard.setStatus("ready", "Ready to finish starless")
        self.starsCard.setStatus("ready", "Ready to finish stars")
        self.recombineCard.setStatus("ready", "Ready to recombine")
        self.btn_save_output.setEnabled(has_composite)


__all__ = ["SidebarFinish"]
