"""Composition of the Denoise mode sidebar's Designer forms."""

from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from startrails.ui.file_manager import FileSection
from startrails.ui.steps import StepCard
from startrails.ui.steps_denoise import (
    DenoiseSkySettings,
    DenoiseAlignSettings,
    DenoiseStackSettings,
    DenoiseTuneSettings,
)
from startrails.ui.ui_sidebar_denoise import Ui_SidebarDenoise


class SidebarDenoise(QWidget):
    """Sidebar widget hosting Denoise mode file lists, steps, and pipeline controls."""

    def __init__(self, parent=None, app=None, ui=None):
        if not isinstance(parent, QWidget) and parent is not None:
            app, parent = parent, app
        super().__init__(parent if isinstance(parent, QWidget) else None)
        self.app = app
        self._output_saved: bool = False
        self._has_compositor: bool = False

        if ui is not None:
            self.ui = ui
        else:
            self.ui = Ui_SidebarDenoise()
            self.ui.setupUi(self)
            self.ui.contentLayout.setAlignment(Qt.AlignTop)

        # File Sections
        self.starFiles = FileSection("Star Images", inputs=True, show_legend=False, expanded=True)
        self.noiseFiles = FileSection("Dark Frames", inputs=True, show_legend=False, expanded=False)
        self.outputFiles = FileSection("Output Files", inputs=False, show_legend=False, expanded=True)
        self.outputs = self.outputFiles

        if hasattr(self.ui, "starFilesLayout"):
            self.ui.starFilesLayout.addWidget(self.starFiles)
        if hasattr(self.ui, "noiseFilesLayout"):
            self.ui.noiseFilesLayout.addWidget(self.noiseFiles)
        if hasattr(self.ui, "outputFilesLayout"):
            self.ui.outputFilesLayout.addWidget(self.outputFiles)

        # Step Settings Widgets
        self.skySettings = DenoiseSkySettings(app)
        self.skyCard = StepCard("Define Sky Region", self.skySettings, 1, expanded=True)
        self.skyCard.setSubtitle("Ready to detect or paint mask")

        self.alignSettings = DenoiseAlignSettings(app)
        self.alignCard = StepCard("Align Stars", self.alignSettings, 2, expanded=False)
        self.alignCard.setSubtitle("Requires sky mask")

        self.stackSettings = DenoiseStackSettings(app)
        self.stackCard = StepCard("Stack Sky & Ground", self.stackSettings, 3, expanded=False)
        self.stackCard.setSubtitle("Requires aligned stars")

        self.tuneSettings = DenoiseTuneSettings(app)
        self.tuneCard = StepCard("Tune Horizon", self.tuneSettings, 4, expanded=False)
        self.tuneCard.setSubtitle("Requires base stacks")

        if hasattr(self.ui, "skyLayout"):
            self.ui.skyLayout.addWidget(self.skyCard)
        if hasattr(self.ui, "alignLayout"):
            self.ui.alignLayout.addWidget(self.alignCard)
        if hasattr(self.ui, "stackLayout"):
            self.ui.stackLayout.addWidget(self.stackCard)
        if hasattr(self.ui, "tuneLayout"):
            self.ui.tuneLayout.addWidget(self.tuneCard)

        # Convenient direct references
        self.pushButton_newProject = self.ui.newProject
        self.pushButton_openProject = self.ui.openProject
        self.btn_save_output = self.ui.saveOutput
        self.btn_pipeline = self.ui.runPipeline
        self.progress_bar = self.ui.pipelineProgressBar
        self.lbl_status = self.ui.pipelineStatusLabel
        self.lbl_ops_progress = self.ui.operationsProgressLabel
        self.ops_progress_bar = self.ui.operationsProgress

        # Step action button aliases
        self.btn_detect_sky = self.skySettings.ui.detect
        self.btn_align_stars = self.alignSettings.ui.run
        self.btn_stack = self.stackSettings.ui.run
        self.btn_compose = self.tuneSettings.ui.run

        # Step card accordion behavior
        self._step_cards = (self.skyCard, self.alignCard, self.stackCard, self.tuneCard)
        for card in self._step_cards:
            card.expanded.connect(lambda c=card: self._collapse_other_steps(c))

        self.update_operations_progress(app)

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        self.starFiles.setExpanded(False)
        self.noiseFiles.setExpanded(False)
        self.outputFiles.setExpanded(False)
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def init_app(self, app) -> None:
        self.app = app
        for settings in (self.skySettings, self.alignSettings, self.stackSettings, self.tuneSettings):
            if hasattr(settings, "init_app"):
                settings.init_app(app)
            elif hasattr(settings, "app"):
                settings.app = app
        self.update_operations_progress(app)

    def reset_settings(self) -> None:
        self.skySettings.reset()
        self.alignSettings.reset()
        self.stackSettings.reset()
        self.tuneSettings.reset()

    def refresh_inputs(self) -> None:
        self.skySettings.refresh_inputs()
        self.alignSettings.refresh_inputs()
        self.stackSettings.refresh_inputs()
        self.tuneSettings.refresh_inputs()

    def set_has_compositor(self, has_comp: bool) -> None:
        self._has_compositor = has_comp

    def set_output_saved(self, saved: bool) -> None:
        self._output_saved = saved

    def update_operations_progress(self, app=None) -> None:
        """Update progress bar, status labels, and step status badges."""
        if app is None:
            app = self.app
        wf = getattr(app, "workflow", None) if app else None
        proj = getattr(wf, "project", None) if wf else None

        has_mask = bool(proj and getattr(proj, "mask_path", None))
        homographies = getattr(proj, "homographies", None) if proj else None
        has_homo = bool(homographies)
        has_compositor = self._has_compositor
        output_saved = self._output_saved

        if self.skyCard is not None:
            self.skyCard.setStatus("done" if has_mask else "ready")
            self.skyCard.setSubtitle("Sky mask defined" if has_mask else "Ready to detect or paint mask")

        if self.alignCard is not None:
            self.alignCard.setStatus("done" if has_homo else "ready")
            if has_homo:
                self.alignCard.setSubtitle(f"{len(homographies)} frames aligned")
            else:
                self.alignCard.setSubtitle("Requires sky mask" if not has_mask else "Ready to align")

        if self.stackCard is not None:
            self.stackCard.setStatus("done" if has_compositor else "ready")
            self.stackCard.setSubtitle("Base stacks ready" if has_compositor else "Requires aligned stars")

        if self.tuneCard is not None:
            self.tuneCard.setStatus("done" if output_saved else "ready")
            self.tuneCard.setSubtitle("Live canvas tuning active" if has_compositor else "Requires base stacks")

        completed = sum([
            1 if has_mask else 0,
            1 if has_homo else 0,
            1 if has_compositor else 0,
            1 if output_saved else 0,
        ])
        if self.lbl_ops_progress is not None:
            self.lbl_ops_progress.setText(f"{completed} of 4 steps complete")
        if self.ops_progress_bar is not None:
            self.ops_progress_bar.setValue(completed)
