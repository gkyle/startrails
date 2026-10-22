"""Composition of the Denoise mode sidebar's Designer forms."""

from __future__ import annotations
from typing import Optional
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from startrails.ui.file_manager import FileSection
from startrails.ui.steps import StepCard
from startrails.ui.steps_denoise import (
    DenoiseSkySettings,
    DenoiseAlignSettings,
    DenoiseStackSettings,
    DenoiseTuneSettings,
    DenoiseExportSettings,
)
from startrails.ui.ui_sidebar_denoise import Ui_SidebarDenoise
from startrails.ui.theme import system_theme


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
        for name in ("sky", "align", "stack", "tune", "export"):
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
        self.lbl_ops_progress = self.ui.operationsProgressLabel
        self.ops_progress_bar = self.ui.operationsProgress

        # Step action button aliases
        self.btn_detect_sky = self.skySettings.ui.detect
        self.btn_align_stars = self.alignSettings.ui.run
        self.btn_stack = self.stackSettings.ui.run
        self.btn_compose = getattr(self.tuneSettings.ui, "run", None)

        # Step card accordion behavior
        self._step_cards = (self.skyCard, self.alignCard, self.stackCard, self.tuneCard, self.exportCard)
        for card in self._step_cards:
            card.expanded.connect(lambda c=card: self._collapse_other_steps(c))
        self.skyCard.expansion_changed.connect(self.skySettings.ui.showMaskOverlay.setChecked)
        self.skySettings.ui.showMaskOverlay.setChecked(self.skyCard.is_expanded)
        self.sync_expanded_step()

        self.update_operations_progress(app)
        system_theme().register(self)

    def sync_expanded_step(self) -> None:
        """Apply accordion behavior to a step that is already expanded."""
        for card in self._step_cards:
            if card.is_expanded:
                self._collapse_other_steps(card)
                break

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        self.starFiles.setExpanded(False)
        self.noiseFiles.setExpanded(False)
        self.outputFiles.setExpanded(False)
        for card in self._step_cards:
            if card is not expanded_card and card.ui.toggle.isChecked():
                card.setExpanded(False)

    def init_app(self, app) -> None:
        self.app = app
        for settings in (self.skySettings, self.alignSettings, self.stackSettings, self.tuneSettings, self.exportSettings):
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
        self.exportSettings.reset()
        self.skySettings.ui.showMaskOverlay.setChecked(self.skyCard.is_expanded)

    def refresh_inputs(self) -> None:
        self.update_operations_progress()

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

        has_stars = bool(proj and proj.star_files)
        mask_path = getattr(proj, "mask_path", None)
        has_mask = bool(mask_path and not proj.mask_invalidated and Path(mask_path).is_file())
        homographies = getattr(proj, "homographies", None) if proj else None
        has_homo = bool(homographies)
        has_compositor = self._has_compositor
        output_saved = self._output_saved
        can_process = has_stars and has_mask

        has_manual = bool(getattr(proj, "has_manual_sky_corrections", False))
        self.skySettings.refresh_inputs(has_manual_corrections=has_manual)
        self.exportSettings.refresh_inputs(has_manual_corrections=has_manual)
        self.alignSettings.refresh_inputs(ready=can_process)
        self.stackSettings.refresh_inputs(ready=can_process)
        self.tuneSettings.refresh_inputs(ready=has_compositor)

        if not has_stars:
            self.skyCard.setStatus("locked", "Add star images to begin")
        else:
            self.skyCard.setStatus("done" if has_mask else "ready",
                                   "Sky mask defined" if has_mask else "Ready to detect or paint mask")

        if not can_process:
            prerequisite = "Add star images to begin" if not has_stars else "Requires sky mask"
            self.alignCard.setStatus("locked", prerequisite)
            self.stackCard.setStatus("locked", prerequisite)
        else:
            self.alignCard.setStatus("done" if has_homo else "ready",
                                     f"{len(homographies)} frames aligned" if has_homo else "Ready to align")
            self.stackCard.setStatus("done" if has_compositor else "ready",
                                     "Base stacks ready" if has_compositor else
                                     ("Ready to stack" if has_homo else "Ready to align and stack"))

        if not has_compositor:
            self.tuneCard.setStatus("locked", "Requires base stacks")
        else:
            self.tuneCard.setStatus("done" if output_saved else "ready", "Live canvas tuning active")

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
