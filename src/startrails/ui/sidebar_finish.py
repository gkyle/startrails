"""Composition of the Finish mode sidebar shell and step cards."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QWidget

from startrails.lib.finish.defaults import (
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
)
from startrails.lib.project_finish import FinishProject
from startrails.ui.steps_recombine import FinishRecombineSettings
from startrails.ui.theme import system_theme
from .ui_sidebar_finish import Ui_SidebarFinish

if TYPE_CHECKING:
    from startrails.app import App
    from startrails.ui.steps import StepCard


class SidebarFinish(QWidget):
    """Sidebar widget hosting Finish mode project actions, file sections, step cards, and outputs."""

    def __init__(self, parent: Optional[QWidget] = None, app: Optional[App] = None):
        super().__init__(parent)
        self.app = app
        self.setObjectName("SidebarFinish")

        self.ui = Ui_SidebarFinish()
        self.ui.setupUi(self)

        # File sections
        self.inputFiles = self.ui.inputFiles
        self.outputFiles = self.ui.outputFiles
        self.outputs = self.outputFiles

        # Step cards and settings
        self.skyCard = self.ui.skyCard
        self.skySettings = self.ui.skySettings
        self.skySettings.app = self.app

        self.separateCard = self.ui.separateCard
        self.separateSettings = self.ui.separateSettings

        self.starlessCard = self.ui.starlessCard
        self.starlessSettings = self.ui.starlessSettings

        self.recombineCard = self.ui.recombineCard
        self.recombineSettings = self.ui.recombineSettings

        # Action and control aliases
        self.newProject = self.ui.newProject
        self.openProject = self.ui.openProject
        self.pushButton_newProject = self.newProject
        self.pushButton_openProject = self.openProject
        self.btn_detect_sky = self.skySettings.ui.detect
        self.btn_save_output = self.recombineSettings.btn_save_output
        self.btn_export_layers = self.recombineSettings.btn_export_layers
        self.check_compare_original = self.recombineSettings.check_compare_original
        self.slider_star_amount = self.recombineSettings.slider_star_amount
        self.slider_star_threshold = self.recombineSettings.slider_star_threshold

        self._step_cards = (self.skyCard, self.separateCard, self.starlessCard, self.recombineCard)
        for card in self._step_cards:
            card.expanded.connect(lambda c=card: self._collapse_other_steps(c))

        system_theme().register(self)

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def lock_output_files_height(self) -> None:
        """Lock output files table to a constant 4-row height to prevent vertical position shifts."""
        if hasattr(self, "outputFiles") and self.outputFiles.model.rowCount() > 0:
            hh = self.outputFiles.ui.files.header().height() or 26
            self.outputFiles.ui.files.setFixedHeight(hh + 4 * 24 + 4)

    def update_from_project(self, project: FinishProject, dimensions: Optional[tuple[int, int]]) -> None:
        """Update file sections and step prerequisites from active project."""
        self.separateSettings.set_from_project(project)
        self.starlessSettings.set_from_project(project)
        self.recombineSettings.set_from_project(project)
        self.update_prerequisites(project)

    def update_prerequisites(self, project: FinishProject) -> None:
        """Update enabled states and subtitles according to stage prerequisite availability."""
        has_source = project.source_is_current()
        has_mask = project.current_artifact_path(ROLE_SKY_MASK) is not None
        has_starless = project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None
        has_stars = project.current_artifact_path(ROLE_SEPARATED_STARS) is not None
        settings = project.get_settings()
        has_denoise_endpoint = (
            project.current_artifact_path(ROLE_DENOISE_ENDPOINT) is not None
            or project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        )
        has_finished_starless = (
            project.current_artifact_path(ROLE_FINISHED_STARLESS) is not None
            if settings.enable_starless_sharpen
            else project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        )

        self.skySettings.refresh_inputs(has_source=has_source)

        star_removal_status = {}
        if (
            hasattr(self, "app")
            and self.app
            and hasattr(self.app, "workflow")
            and hasattr(self.app.workflow, "get_star_removal_status")
        ):
            star_removal_status = self.app.workflow.get_star_removal_status()

        self.separateSettings.refresh_status(star_removal_status, has_prerequisites=has_source and has_mask)

        graxpert_status = {}
        if (
            hasattr(self, "app")
            and self.app
            and hasattr(self.app, "workflow")
            and hasattr(self.app.workflow, "get_graxpert_status")
        ):
            graxpert_status = self.app.workflow.get_graxpert_status()

        self.starlessSettings.refresh_status(
            graxpert_status,
            has_prerequisites=has_starless,
            has_endpoint=has_denoise_endpoint,
        )

        if not has_source:
            self.skyCard.setStatus("locked", "Prerequisite: Source image required")
            self.separateCard.setStatus("locked", "Prerequisite: Source image required")
            self.starlessCard.setStatus("locked", "Prerequisite: Source image required")
            self.recombineCard.setStatus("locked", "Prerequisite: Source image required")
            self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            self.btn_export_layers.setEnabled(False)
            return

        if has_mask:
            self.skyCard.setStatus("done", "Sky mask defined")
        else:
            self.skyCard.setStatus("ready", "Ready to define sky region")

        if not has_mask:
            self.separateCard.setStatus("locked", "Prerequisite: Sky region required")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.recombineCard.setStatus("locked", "Prerequisite: Sky region required")
            self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            self.btn_export_layers.setEnabled(False)
            return

        if not (has_starless and has_stars):
            if not star_removal_status.get("configured", False):
                self.separateCard.setStatus("ready", "Star removal model missing")
            else:
                self.separateCard.setStatus("ready", "Ready to separate stars")
            self.starlessCard.setStatus("locked", "Prerequisite: Separated starless required")
            self.recombineCard.setStatus("locked", "Prerequisite: Separated layers required")
            self.recombineSettings.refresh_prerequisites(has_prerequisites=False)
            self.btn_save_output.setEnabled(False)
            self.btn_export_layers.setEnabled(False)
            return

        graxpert_ready = bool(graxpert_status.get("configured", graxpert_status.get("model_ready", False)))

        self.separateCard.setStatus("done", "Stars separated")
        if has_finished_starless:
            self.starlessCard.setStatus("done", "Starless finished")
        elif has_denoise_endpoint:
            self.starlessCard.setStatus("ready", "Ready to update starless")
        elif not graxpert_ready:
            self.starlessCard.setStatus("ready", "GraXpert setup required")
        else:
            self.starlessCard.setStatus("ready", "Ready to finish starless")

        self.recombineSettings.refresh_prerequisites(has_prerequisites=True)

        if project.current_export_path() is not None:
            self.recombineCard.setStatus("done", "Finished image saved")
        else:
            self.recombineCard.setStatus("ready", "Ready to recombine")

        ready = has_source and has_mask and has_starless and has_stars
        self.btn_save_output.setEnabled(ready)
        self.btn_export_layers.setEnabled(ready)


__all__ = ["FinishRecombineSettings", "SidebarFinish"]
