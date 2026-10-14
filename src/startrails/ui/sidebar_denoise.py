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

        # Bind Designer-created components; static composition lives in the form.
        self.starFiles = self.ui.starFiles
        self.noiseFiles = self.ui.noiseFiles
        self.outputFiles = self.ui.outputFiles
        self.outputs = self.outputFiles
        for name in ("sky", "align", "stack", "tune"):
            settings = getattr(self.ui, name + "Settings")
            settings.app = app
            settings.set_from_project()
            setattr(self, name + "Settings", settings)
            setattr(self, name + "Card", getattr(self.ui, name + "Card"))

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
        self.skyCard.expansion_changed.connect(self.skySettings.ui.showMaskOverlay.setChecked)

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
