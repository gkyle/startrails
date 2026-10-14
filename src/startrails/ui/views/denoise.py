"""Denoise mode sidebar view and workflow controller."""

from __future__ import annotations
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
from PySide6.QtCore import Slot, Qt, QTimer, QSignalBlocker
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QWidget,
)

from startrails.lib.file import File, DenoiseInputFile, OutputFile
from startrails.ui.file_manager import FileSection
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.sidebar_denoise import SidebarDenoise
from startrails.ui.signals import getSignals
from startrails.ui.steps import StepCard
from startrails.ui.steps_denoise import (
    DenoiseSkySettings,
    DenoiseAlignSettings,
    DenoiseStackSettings,
    DenoiseTuneSettings,
)
from startrails.ui.views.base import ModeView
from startrails.ui.workers_denoise import (
    AutoMaskWorker,
    RefineMaskWorker,
    HorizonOverlayWorker,
    FinalCompositeSaveWorker,
)

if TYPE_CHECKING:
    from startrails.app import App


class DenoiseView(ModeView):
    """View controller managing the Denoise sidebar, input lists, and denoising pipeline."""

    mode_name: str = "denoise"

    def __init__(self, app: App, shell: Any):
        super().__init__(app, shell)
        self._sidebar: Optional[SidebarDenoise] = None
        self._starFiles = None
        self._noiseFiles = None
        self._outputFiles = None

        self._skySettings = None
        self._alignSettings = None
        self._stackSettings = None
        self._tuneSettings = None

        self._skyCard = None
        self._alignCard = None
        self._stackCard = None
        self._tuneCard = None

        self._pushButton_newProject = None
        self._pushButton_openProject = None
        self._btn_detect_sky = None
        self._btn_align_stars = None
        self._btn_stack = None
        self._btn_compose = None
        self._btn_save_output = None
        self._btn_pipeline = None

        self._lbl_ops_progress = None
        self._ops_progress_bar = None
        self._progress_bar = None
        self._lbl_status = None

        self._step_cards: tuple[StepCard, ...] = ()
        self._output_saved: bool = False

        self.last_compositor: Any = None
        self.last_align_result: Any = None

        # Live horizon tuning worker & debounce state
        self._horizon_worker: Optional[HorizonOverlayWorker] = None
        self._horizon_request_id: int = 0
        self._pending_horizon_params: Optional[dict] = None
        self._horizon_debounce_timer = QTimer()
        self._horizon_debounce_timer.setSingleShot(True)
        self._horizon_debounce_timer.setInterval(75)
        self._horizon_debounce_timer.timeout.connect(self._dispatch_horizon_tuning)

        # Async final composite saver state
        self._final_save_worker: Optional[FinalCompositeSaveWorker] = None
        self._final_save_request_id: int = 0
        self._pending_final_save: Optional[dict] = None
        self._horizon_save_debounce_timer = QTimer()
        self._horizon_save_debounce_timer.setSingleShot(True)
        self._horizon_save_debounce_timer.setInterval(1000)
        self._horizon_save_debounce_timer.timeout.connect(self._dispatch_async_save_final_composite)

    def _from_shell(self, name: str) -> Any:
        shell = getattr(self, "shell", None)
        if shell is not None and hasattr(shell, "__dict__"):
            return shell.__dict__.get(name)
        return None

    @property
    def sidebar(self) -> Optional[SidebarDenoise]:
        if self._sidebar is not None:
            return self._sidebar
        shell_sidebar = self._from_shell("sidebar")
        if isinstance(shell_sidebar, SidebarDenoise):
            return shell_sidebar
        return None

    @sidebar.setter
    def sidebar(self, value: Optional[SidebarDenoise]) -> None:
        if value is not None and not isinstance(value, SidebarDenoise):
            return
        self._sidebar = value
        self._init_sidebar_refs()

    @property
    def starFiles(self):
        if self._starFiles is not None:
            return self._starFiles
        return self._from_shell("starFiles")

    @starFiles.setter
    def starFiles(self, value):
        self._starFiles = value

    @property
    def noiseFiles(self):
        if self._noiseFiles is not None:
            return self._noiseFiles
        return self._from_shell("noiseFiles")

    @noiseFiles.setter
    def noiseFiles(self, value):
        self._noiseFiles = value

    @property
    def vignettingFiles(self):
        return None

    @property
    def outputFiles(self):
        if self._outputFiles is not None:
            return self._outputFiles
        return self._from_shell("outputFiles")

    @outputFiles.setter
    def outputFiles(self, value):
        self._outputFiles = value

    @property
    def skySettings(self):
        if self._skySettings is not None:
            return self._skySettings
        return self._from_shell("skySettings")

    @skySettings.setter
    def skySettings(self, value):
        self._skySettings = value

    @property
    def alignSettings(self):
        if self._alignSettings is not None:
            return self._alignSettings
        return self._from_shell("alignSettings")

    @alignSettings.setter
    def alignSettings(self, value):
        self._alignSettings = value

    @property
    def stackSettings(self):
        if self._stackSettings is not None:
            return self._stackSettings
        return self._from_shell("stackSettings")

    @stackSettings.setter
    def stackSettings(self, value):
        self._stackSettings = value

    @property
    def tuneSettings(self):
        if self._tuneSettings is not None:
            return self._tuneSettings
        return self._from_shell("tuneSettings")

    @tuneSettings.setter
    def tuneSettings(self, value):
        self._tuneSettings = value

    @property
    def skyCard(self):
        if self._skyCard is not None:
            return self._skyCard
        return self._from_shell("skyCard")

    @skyCard.setter
    def skyCard(self, value):
        self._skyCard = value

    @property
    def alignCard(self):
        if self._alignCard is not None:
            return self._alignCard
        return self._from_shell("alignCard")

    @alignCard.setter
    def alignCard(self, value):
        self._alignCard = value

    @property
    def stackCard(self):
        if self._stackCard is not None:
            return self._stackCard
        return self._from_shell("stackCard")

    @stackCard.setter
    def stackCard(self, value):
        self._stackCard = value

    @property
    def tuneCard(self):
        if self._tuneCard is not None:
            return self._tuneCard
        return self._from_shell("tuneCard")

    @tuneCard.setter
    def tuneCard(self, value):
        self._tuneCard = value

    @property
    def pushButton_newProject(self):
        if self._pushButton_newProject is not None:
            return self._pushButton_newProject
        return self._from_shell("pushButton_newProject")

    @pushButton_newProject.setter
    def pushButton_newProject(self, value):
        self._pushButton_newProject = value

    @property
    def pushButton_openProject(self):
        if self._pushButton_openProject is not None:
            return self._pushButton_openProject
        return self._from_shell("pushButton_openProject")

    @pushButton_openProject.setter
    def pushButton_openProject(self, value):
        self._pushButton_openProject = value

    @property
    def btn_detect_sky(self):
        if self._btn_detect_sky is not None:
            return self._btn_detect_sky
        return self._from_shell("btn_detect_sky")

    @btn_detect_sky.setter
    def btn_detect_sky(self, value):
        self._btn_detect_sky = value

    @property
    def btn_align_stars(self):
        if self._btn_align_stars is not None:
            return self._btn_align_stars
        return self._from_shell("btn_align_stars")

    @btn_align_stars.setter
    def btn_align_stars(self, value):
        self._btn_align_stars = value

    @property
    def btn_stack(self):
        if self._btn_stack is not None:
            return self._btn_stack
        return self._from_shell("btn_stack")

    @btn_stack.setter
    def btn_stack(self, value):
        self._btn_stack = value

    @property
    def btn_compose(self):
        if self._btn_compose is not None:
            return self._btn_compose
        return self._from_shell("btn_compose")

    @btn_compose.setter
    def btn_compose(self, value):
        self._btn_compose = value

    @property
    def btn_save_output(self):
        if self._btn_save_output is not None:
            return self._btn_save_output
        return self._from_shell("btn_save_output")

    @btn_save_output.setter
    def btn_save_output(self, value):
        self._btn_save_output = value

    @property
    def btn_pipeline(self):
        if self._btn_pipeline is not None:
            return self._btn_pipeline
        return self._from_shell("btn_pipeline")

    @btn_pipeline.setter
    def btn_pipeline(self, value):
        self._btn_pipeline = value

    @property
    def lbl_ops_progress(self):
        if self._lbl_ops_progress is not None:
            return self._lbl_ops_progress
        return self._from_shell("lbl_ops_progress")

    @lbl_ops_progress.setter
    def lbl_ops_progress(self, value):
        self._lbl_ops_progress = value

    @property
    def ops_progress_bar(self):
        if self._ops_progress_bar is not None:
            return self._ops_progress_bar
        return self._from_shell("ops_progress_bar")

    @ops_progress_bar.setter
    def ops_progress_bar(self, value):
        self._ops_progress_bar = value

    @property
    def progress_bar(self):
        if self._progress_bar is not None:
            return self._progress_bar
        return self._from_shell("progress_bar")

    @progress_bar.setter
    def progress_bar(self, value):
        self._progress_bar = value

    @property
    def lbl_status(self):
        if self._lbl_status is not None:
            return self._lbl_status
        return self._from_shell("lbl_status")

    @lbl_status.setter
    def lbl_status(self, value):
        self._lbl_status = value

    def build_sidebar(self, parent: QWidget) -> QWidget:
        if self._sidebar is not None and self._sidebar.parent() is parent:
            return self._sidebar

        if hasattr(parent, "count") and parent.count() > 0:
            existing = parent.widget(0)
            if isinstance(existing, SidebarDenoise):
                self._sidebar = existing
                if hasattr(self._sidebar, "init_app"):
                    self._sidebar.init_app(self.app)
                self.sidebar_widget = self._sidebar
                self._init_sidebar_refs()
                return self._sidebar

        self._sidebar = SidebarDenoise(parent, app=self.app)
        self.sidebar_widget = self._sidebar
        self._init_sidebar_refs()
        return self._sidebar

    def _init_sidebar_refs(self) -> None:
        sb = self.sidebar
        if sb is None:
            return
        self.starFiles = sb.starFiles
        self.noiseFiles = sb.noiseFiles
        self.outputFiles = getattr(sb, "outputFiles", None)
        self.skySettings = sb.skySettings
        self.alignSettings = sb.alignSettings
        self.stackSettings = sb.stackSettings
        self.tuneSettings = sb.tuneSettings
        self.skyCard = sb.skyCard
        self.alignCard = sb.alignCard
        self.stackCard = sb.stackCard
        self.tuneCard = sb.tuneCard
        self.pushButton_newProject = sb.pushButton_newProject
        self.pushButton_openProject = sb.pushButton_openProject
        self.btn_detect_sky = sb.btn_detect_sky
        self.btn_align_stars = sb.btn_align_stars
        self.btn_stack = sb.btn_stack
        self.btn_compose = sb.btn_compose
        self.btn_save_output = sb.btn_save_output
        self.btn_pipeline = sb.btn_pipeline
        self.progress_bar = sb.progress_bar
        self.lbl_status = sb.lbl_status
        self.lbl_ops_progress = sb.lbl_ops_progress
        self.ops_progress_bar = sb.ops_progress_bar
        self._step_cards = sb._step_cards

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        if self._sidebar is not None:
            self._sidebar._collapse_other_steps(expanded_card)

    def bind(self) -> None:
        if self.sidebar is None:
            return

        if self.pushButton_newProject is not None and hasattr(self.shell, "doNewProject"):
            self.connect_signal(self.pushButton_newProject.clicked, self.shell.doNewProject)
        if self.pushButton_openProject is not None and hasattr(self.shell, "doOpenProject"):
            self.connect_signal(self.pushButton_openProject.clicked, self.shell.doOpenProject)

        # Connect FileSection actions
        signals = getSignals()
        for section in (self.starFiles, self.noiseFiles, self.outputFiles):
            if section is not None:
                self.connect_signal(signals.focusFile, section.focus_file)

        if self.starFiles is not None:
            self.connect_signal(self.starFiles.addRequested, self.select_star_files)
            self.connect_signal(self.starFiles.showFile, self.showFile)
            self.connect_signal(self.starFiles.removeFile, self.remove_star_file)
            self.connect_signal(self.starFiles.setReferenceRequested, self.set_reference_file)

        if self.noiseFiles is not None:
            self.connect_signal(self.noiseFiles.addRequested, self.select_noise_files)
            self.connect_signal(self.noiseFiles.showFile, self.showFile)
            self.connect_signal(self.noiseFiles.removeFile, self.remove_noise_file)

        if self.outputFiles is not None:
            self.connect_signal(self.outputFiles.showFile, self.showFile)
            self.connect_signal(self.outputFiles.removeFile, self.remove_output_file)

        # Connect operation actions
        if self.btn_detect_sky is not None:
            self.connect_signal(self.btn_detect_sky.clicked, self.do_detect_sky_action)
        if self.skySettings is not None:
            self.connect_signal(self.skySettings.ui.refineMask.clicked, self.do_refine_mask_action)
            self.connect_signal(self.skySettings.clearMaskRequested, self.do_clear_mask_action)
            self.connect_signal(self.skySettings.fullFrameRequested, self.do_full_frame_mask_action)
            self.connect_signal(self.skySettings.maskEditToggled, self._on_mask_edit_toggled)
            self.connect_signal(self.skySettings.brushRadiusChanged, self._on_brush_radius_changed)
        if self.btn_align_stars is not None:
            self.connect_signal(self.btn_align_stars.clicked, self.do_align_stars_action)
        if self.btn_stack is not None:
            self.connect_signal(self.btn_stack.clicked, self.do_stack_action)
        if self.btn_compose is not None:
            self.connect_signal(self.btn_compose.clicked, self.do_compose_action)
        if self.tuneSettings is not None:
            self.connect_signal(self.tuneSettings.gradientMaskToggled, self._on_gradient_mask_toggled)
            self.connect_signal(self.tuneSettings.settingsChanged, self._schedule_horizon_tuning)
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.connect_signal(self.shell.canvas_main.maskChanged, self._on_canvas_mask_changed)
            self.connect_signal(self.shell.canvas_main.brushRadiusChanged, self._on_canvas_brush_radius_changed)
        if self.btn_save_output is not None:
            self.connect_signal(self.btn_save_output.clicked, self.do_save_output_action)
        if self.btn_pipeline is not None:
            self.connect_signal(self.btn_pipeline.clicked, self.do_pipeline_action)

    def teardown(self) -> None:
        super().teardown()
        if hasattr(self, "_horizon_debounce_timer") and self._horizon_debounce_timer.isActive():
            self._horizon_debounce_timer.stop()
        if self._horizon_worker is not None:
            self._horizon_worker.cancel()
            self._horizon_worker = None
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setMaskEditMode(False)
            self.shell.canvas_main.clearHorizonOverlay()
            self.shell.canvas_main.setGradientMaskVisible(False)
        if self.sidebar is not None:
            self.sidebar.setParent(None)

    # -------------------------------------------------------------------------
    # File Management
    # -------------------------------------------------------------------------

    def select_star_files(self) -> None:
        fileNames, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Star Images",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if fileNames and hasattr(self.app.workflow, "add_star_files"):
            self.app.workflow.add_star_files(fileNames)
            self.resetProjectView()

    def remove_star_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_star_file"):
            self.app.workflow.remove_star_file(file)
            self.resetProjectView()

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        if hasattr(self.app.workflow, "set_reference_file"):
            self.app.workflow.set_reference_file(file)
            if self.alignSettings is not None:
                self.alignSettings.set_reference_file(file)
            self.resetProjectView()

    def select_noise_files(self) -> None:
        fileNames, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Dark/Noise Frames",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if fileNames and hasattr(self.app.workflow, "add_noise_files"):
            self.app.workflow.add_noise_files(fileNames)
            self.resetProjectView()

    def remove_noise_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_noise_file"):
            self.app.workflow.remove_noise_file(file)
            self.resetProjectView()


    def resetProjectView(self) -> None:
        if not hasattr(self.app.workflow, "get_star_files"):
            return
        self._horizon_debounce_timer.stop()
        self._horizon_save_debounce_timer.stop()
        if self._horizon_worker is not None and self._horizon_worker.isRunning():
            self._horizon_worker.cancel()
        if self._final_save_worker is not None and self._final_save_worker.isRunning():
            self._final_save_worker.cancel()

        stars = self.app.workflow.get_star_files()
        darks = self.app.workflow.get_noise_files()

        proj = getattr(self.app.workflow, "project", None)
        if proj and getattr(proj, "homographies", None):
            homos = proj.homographies
            for f in stars:
                p_str = str(f.path)
                p_res = str(Path(f.path).resolve())
                if p_str in homos or p_res in homos:
                    f.aligned = True

        if self.starFiles is not None:
            self.starFiles.set_files(stars)
        if self.noiseFiles is not None:
            self.noiseFiles.set_files(darks)
        if self.outputFiles is not None:
            self.outputFiles.set_files(self.app.getOutputFileList())

        if self.skySettings is not None:
            self.skySettings.set_from_project()
        if self.alignSettings is not None:
            self.alignSettings.set_from_project()
        if self.stackSettings is not None:
            self.stackSettings.set_from_project()
        if self.tuneSettings is not None:
            self.tuneSettings.set_from_project()

        self.updateReadyStates()

        ref = self.app.workflow.get_reference_file()
        if ref is not None:
            self.showFile(ref)
        elif stars:
            self.showFile(stars[0])
        else:
            self.showFile(None)

        existing_mask = self._find_existing_mask()
        if existing_mask is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setDenoiseMask(existing_mask)
            if self.skyCard is not None:
                self.skyCard.setStatus("done")

        if getattr(self.app.workflow, "project", None) and getattr(self.app.workflow.project, "homographies", None):
            if self.alignCard is not None:
                self.alignCard.setStatus("done")

        existing_comp = self._find_existing_compositor()
        if existing_comp is not None:
            self.last_compositor = existing_comp
            if self.stackCard is not None:
                self.stackCard.setStatus("done")

    def showFile(self, file: Optional[File]) -> None:
        if hasattr(self.shell, "currentFile"):
            self.shell.currentFile = file
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFile(file)
            ref = self.app.workflow.get_reference_file() if hasattr(self.app, "workflow") else None
            if (
                file is not None
                and ref is not None
                and getattr(file, "path", None) == getattr(ref, "path", None)
                and self.skySettings is not None
                and self.skySettings.ui.showMaskOverlay.isChecked()
            ):
                self.shell.canvas_main.setMaskEditMode(True)
            else:
                self.shell.canvas_main.setMaskEditMode(False)
        if hasattr(self.shell, "label_imageName") and self.shell.label_imageName is not None:
            self.shell.label_imageName.setText(file.basename if file is not None else "")
        signals = getSignals()
        if hasattr(signals, "focusFile"):
            signals.focusFile.emit(file)

    def remove_output_file(self, file: OutputFile) -> None:
        if hasattr(self.app, "removeOutputFile"):
            self.app.removeOutputFile(file)
        elif hasattr(self.app.workflow, "remove_output_file"):
            self.app.workflow.remove_output_file(file)
        if self.outputFiles is not None:
            self.outputFiles.set_files(self.app.getOutputFileList())

    def updateReadyStates(self, _=None) -> None:
        has_stars = bool(hasattr(self.app.workflow, "get_star_files") and self.app.workflow.get_star_files())
        if self.skySettings is not None:
            self.skySettings.refresh_inputs()
        if self.alignSettings is not None:
            self.alignSettings.refresh_inputs()

        has_homographies = bool(
            self.last_align_result is not None
            or (hasattr(self.app.workflow, "project") and getattr(self.app.workflow.project, "homographies", {}))
        )
        if self.stackSettings is not None:
            self.stackSettings.refresh_inputs(ready=has_homographies or has_stars)

        has_compositor = bool(self.last_compositor is not None or self._has_existing_stacks())
        if self.tuneSettings is not None:
            self.tuneSettings.refresh_inputs(ready=has_compositor)

        if self.btn_pipeline is not None:
            self.btn_pipeline.setEnabled(has_stars)
        if self.btn_save_output is not None:
            self.btn_save_output.setEnabled(has_compositor)

        if self.sidebar is not None:
            self.sidebar.set_has_compositor(has_compositor)
            self.sidebar.set_output_saved(self._output_saved)
            self.sidebar.update_operations_progress(self.app)

    def teardown(self) -> None:
        self._horizon_debounce_timer.stop()
        if self._horizon_worker is not None and self._horizon_worker.isRunning():
            self._horizon_worker.cancel()
            self._horizon_worker = None
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setMaskEditMode(False)
            self.shell.canvas_main.clearHorizonOverlay()
            self.shell.canvas_main.setGradientMaskVisible(False)
        super().teardown()
        if self._sidebar is not None:
            self._sidebar.setParent(None)

    # -------------------------------------------------------------------------
    # Denoise Step Operations
    # -------------------------------------------------------------------------
    # Denoise Step Operations & Canvas Interactions
    # -------------------------------------------------------------------------

    def _schedule_horizon_tuning(self) -> None:
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return
        self._horizon_debounce_timer.start(75)
        self._horizon_save_debounce_timer.start(1000)

    def _dispatch_async_save_final_composite(self) -> None:
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return
        vals = self.tuneSettings.values() if self.tuneSettings else {}
        params = {
            "blend": vals.get("horizon_blend_percent", 60.0),
            "blur_radius": vals.get("horizon_blur_radius", 2.0),
            "denoise_strength": vals.get("horizon_denoise_strength", 0.2),
            "denoise_enabled": vals.get("denoise_horizon_band", True),
            "enable_corrections": vals.get("enable_horizon_corrections", True),
            "color_denoise": vals.get("horizon_color_denoise_strength", 1.0),
            "value_denoise": vals.get("horizon_value_denoise_strength", 0.2),
        }
        proj = getattr(self.app.workflow, "project", None)
        if not proj or not hasattr(proj, "get_output_dir"):
            return
        out_dir = proj.get_output_dir()
        stem = self.app.workflow._get_project_stem() if hasattr(self.app.workflow, "_get_project_stem") else "project"
        final_path = out_dir / f"{stem}_final.tif"

        if self._final_save_worker is not None and self._final_save_worker.isRunning():
            self._pending_final_save = params
            self._final_save_worker.cancel()
            return

        self._pending_final_save = None
        self._final_save_request_id += 1
        self._final_save_worker = FinalCompositeSaveWorker(
            self.last_compositor,
            params,
            final_path,
            self._final_save_request_id,
            parent=self.sidebar,
        )
        self._final_save_worker.finishedSave.connect(self._on_final_save_finished)
        self._final_save_worker.finished.connect(self._on_final_save_worker_done)
        self._final_save_worker.start()

    def _on_final_save_worker_done(self) -> None:
        if self._pending_final_save is not None and self.last_compositor is not None:
            params = self._pending_final_save
            self._pending_final_save = None
            proj = getattr(self.app.workflow, "project", None)
            if not proj or not hasattr(proj, "get_output_dir"):
                return
            out_dir = proj.get_output_dir()
            stem = self.app.workflow._get_project_stem() if hasattr(self.app.workflow, "_get_project_stem") else "project"
            final_path = out_dir / f"{stem}_final.tif"

            self._final_save_request_id += 1
            self._final_save_worker = FinalCompositeSaveWorker(
                self.last_compositor,
                params,
                final_path,
                self._final_save_request_id,
                parent=self.sidebar,
            )
            self._final_save_worker.finishedSave.connect(self._on_final_save_finished)
            self._final_save_worker.finished.connect(self._on_final_save_worker_done)
            self._final_save_worker.start()

    def _on_final_save_finished(self, out_path: Any, full_img: np.ndarray, req_id: int) -> None:
        if req_id != self._final_save_request_id:
            return
        if self.app and hasattr(self.app, "workflow") and hasattr(self.app.workflow, "project"):
            self.app.workflow.project.final_output_path = str(out_path)
            self.app.workflow.save_project()
            out_files = (
                self.app.workflow.get_output_file_list()
                if hasattr(self.app.workflow, "get_output_file_list")
                else []
            )
            if self.outputFiles is not None:
                self.outputFiles.set_files(out_files)
        if self.tuneSettings and hasattr(self.tuneSettings.ui, "tuneStatus"):
            self.tuneSettings.ui.tuneStatus.setText(f"Saved: {Path(out_path).name}")
        if self.tuneCard is not None:
            self.tuneCard.setStatus("done")

    def _dispatch_horizon_tuning(self) -> None:
        if self.last_compositor is None:
            return
        vals = self.tuneSettings.values() if self.tuneSettings else {}
        params = {
            "blend": vals.get("horizon_blend_percent", 60.0),
            "blur_radius": vals.get("horizon_blur_radius", 2.0),
            "denoise_strength": vals.get("horizon_denoise_strength", 0.2),
            "denoise_enabled": vals.get("denoise_horizon_band", True),
            "enable_corrections": vals.get("enable_horizon_corrections", True),
            "color_denoise": vals.get("horizon_color_denoise_strength", 1.0),
            "value_denoise": vals.get("horizon_value_denoise_strength", 0.2),
        }
        if self._horizon_worker is not None and self._horizon_worker.isRunning():
            self._pending_horizon_params = params
            self._horizon_worker.cancel()
            return

        self._pending_horizon_params = None
        self._horizon_request_id += 1
        self._horizon_worker = HorizonOverlayWorker(
            self.last_compositor,
            params,
            self._horizon_request_id,
            parent=self.sidebar,
        )
        self._horizon_worker.finishedOverlay.connect(self._on_horizon_overlay_ready)
        self._horizon_worker.finished.connect(self._on_horizon_worker_finished)
        self._horizon_worker.start()

    def _on_horizon_worker_finished(self) -> None:
        if self._pending_horizon_params is not None and self.last_compositor is not None:
            params = self._pending_horizon_params
            self._pending_horizon_params = None
            self._horizon_request_id += 1
            self._horizon_worker = HorizonOverlayWorker(
                self.last_compositor,
                params,
                self._horizon_request_id,
                parent=self.sidebar,
            )
            self._horizon_worker.finishedOverlay.connect(self._on_horizon_overlay_ready)
            self._horizon_worker.finished.connect(self._on_horizon_worker_finished)
            self._horizon_worker.start()

    def _on_horizon_overlay_ready(
        self, roi: Optional[np.ndarray], rect: tuple[int, int, int, int], req_id: int
    ) -> None:
        if req_id == self._horizon_request_id and roi is not None:
            if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                self.shell.canvas_main.setHorizonOverlay(roi, rect)

    def _on_gradient_mask_toggled(self, checked: bool) -> None:
        if not hasattr(self.shell, "canvas_main") or self.shell.canvas_main is None:
            return
        if checked:
            mask = None
            if self.last_compositor is not None and getattr(self.last_compositor, "gradient_mask", None) is not None:
                mask = self.last_compositor.gradient_mask
            elif hasattr(self.app.workflow, "project") and getattr(self.app.workflow.project, "gradient_mask_path", None):
                p = Path(self.app.workflow.project.gradient_mask_path)
                if p.exists():
                    from startrails.lib.denoise.io.mask import MaskHandler
                    mask = MaskHandler.load_mask(p)
            if mask is not None:
                self.shell.canvas_main.setGradientMask(mask)
            self.shell.canvas_main.setGradientMaskVisible(True)
        else:
            self.shell.canvas_main.setGradientMaskVisible(False)

    def _find_existing_mask(self) -> Optional[np.ndarray]:
        proj = getattr(self.app.workflow, "project", None)
        candidates = []
        if proj:
            if getattr(proj, "mask_path", None):
                candidates.append(Path(proj.mask_path))
            if getattr(proj, "refined_mask_path", None):
                candidates.append(Path(proj.refined_mask_path))
            if hasattr(proj, "get_output_dir"):
                out_dir = proj.get_output_dir()
                candidates.append(out_dir / "mask.png")
                candidates.append(out_dir / "mask_sky.png")
                if getattr(proj, "projectFile", None):
                    p = Path(proj.projectFile)
                    candidates.append(out_dir / f"{p.stem}.mask.png")
            if getattr(proj, "projectFile", None):
                p = Path(proj.projectFile)
                candidates.append(p.parent / f"{p.stem}.mask.png")
                candidates.append(p.parent / "mask_sky.png")
                candidates.append(p.parent / "mask.png")
        ref = self.app.workflow.get_reference_file()
        if ref and getattr(ref, "path", None):
            rp = Path(ref.path)
            candidates.append(rp.parent / f"{rp.stem}.mask.png")
            candidates.append(rp.parent / "mask_sky.png")
            candidates.append(rp.parent / "mask.png")
        from startrails.lib.denoise.io.mask import MaskHandler
        for cand in candidates:
            if cand and cand.is_file():
                try:
                    m = MaskHandler.load_mask(cand)
                    if m is not None and np.any(m > 0):
                        return m
                except Exception:
                    continue
        return None

    def _has_existing_stacks(self) -> bool:
        proj = getattr(self.app.workflow, "project", None)
        if not proj or not hasattr(proj, "get_output_dir"):
            return False
        out_dir = proj.get_output_dir()
        sky_p = Path(proj.sky_stack_path) if getattr(proj, "sky_stack_path", None) else (out_dir / "sky_stack.tif")
        ground_p = Path(proj.ground_stack_path) if getattr(proj, "ground_stack_path", None) else (out_dir / "ground_stack.tif")
        return sky_p.is_file() and ground_p.is_file()

    def _find_existing_compositor(self) -> Optional[Any]:
        if not self._has_existing_stacks():
            return None
        proj = getattr(self.app.workflow, "project", None)
        out_dir = proj.get_output_dir()
        sky_p = Path(proj.sky_stack_path) if getattr(proj, "sky_stack_path", None) else (out_dir / "sky_stack.tif")
        ground_p = Path(proj.ground_stack_path) if getattr(proj, "ground_stack_path", None) else (out_dir / "ground_stack.tif")
        try:
            from startrails.lib.util import imread
            from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor
            sky_stack = imread(sky_p, to_rgb=True, as_float=True)
            ground_stack = imread(ground_p, to_rgb=True, as_float=True)
            h, w = sky_stack.shape[:2]

            mask = self._find_existing_mask()
            if mask is None:
                mask = np.ones((h, w), dtype=np.float32)

            grad_p = Path(proj.gradient_mask_path) if getattr(proj, "gradient_mask_path", None) else (out_dir / "gradient_mask.png")
            if grad_p.exists():
                from startrails.lib.denoise.io.mask import MaskHandler
                gradient_mask = MaskHandler.load_mask(grad_p)
            elif getattr(proj, "homographies", None) and mask is not None:
                try:
                    import cv2
                    coverages = []
                    for h_val in proj.homographies.values():
                        if h_val is not None:
                            H_mat = np.array(h_val, dtype=np.float64)
                            if H_mat.shape == (2, 3):
                                H_mat = np.vstack([H_mat, [0, 0, 1]])
                            if H_mat.shape == (3, 3):
                                cov = cv2.warpPerspective(np.ones((h, w), dtype=np.float32), H_mat, (w, h), flags=cv2.INTER_NEAREST)
                                coverages.append(cov)
                    if coverages:
                        from startrails.lib.denoise.io.mask import MaskHandler
                        gradient_mask = MaskHandler.compute_gradient_mask(coverages, sky_mask=mask)
                        MaskHandler.save_mask(gradient_mask, grad_p)
                        proj.gradient_mask_path = str(grad_p)
                    else:
                        gradient_mask = np.zeros((h, w), dtype=np.float32)
                except Exception:
                    gradient_mask = np.zeros((h, w), dtype=np.float32)
            else:
                gradient_mask = np.zeros((h, w), dtype=np.float32)

            cfg = self.app.workflow.get_config()
            return HorizonCompositor(
                sky_stack=sky_stack,
                ground_stack=ground_stack,
                gradient_mask=gradient_mask,
                sky_mask=mask,
                feather_radius=3.0,
                denoise_radius=getattr(cfg, "horizon_denoise_radius", 5),
                denoise_eps=getattr(cfg, "horizon_denoise_eps", 1e-3),
            )
        except Exception as e:
            print(f"Could not construct compositor from disk stacks: {e}")
            return None

    def _get_project_mask_path(self) -> Path:
        proj = getattr(self.app.workflow, "project", None)
        if proj and hasattr(proj, "get_output_dir"):
            out_dir = proj.get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            return out_dir / "mask.png"
        ref = self.app.workflow.get_reference_file()
        if ref and getattr(ref, "path", None):
            p = Path(ref.path)
            return p.parent / f"{p.stem}.mask.png"
        return Path("projects/default.denoise/mask.png")

    def _on_mask_edit_toggled(self, enabled: bool) -> None:
        if not hasattr(self.shell, "canvas_main") or self.shell.canvas_main is None:
            return
        if enabled:
            ref = self.app.workflow.get_reference_file()
            if ref is not None:
                canvas_has_ref = (
                    getattr(self.shell, "currentFile", None) == ref
                    and getattr(self.shell.canvas_main, "file", None) == ref
                    and self.shell.canvas_main.pixmap is not None
                    and not self.shell.canvas_main.pixmap.isNull()
                )
                if not canvas_has_ref:
                    self.showFile(ref)

            current_m = self.shell.canvas_main.getDenoiseMask()
            if current_m is None or not np.any(current_m > 0):
                existing_mask = self._find_existing_mask()
                if existing_mask is not None:
                    self.shell.canvas_main.setDenoiseMask(existing_mask)
                else:
                    self.shell.canvas_main.fillDenoiseMask()
                    current_mask = self.shell.canvas_main.getDenoiseMask()
                    if current_mask is not None:
                        self._save_mask_to_project(current_mask)
        self.shell.canvas_main.setMaskEditMode(enabled)

    def _on_brush_radius_changed(self, radius: int) -> None:
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setBrushRadius(radius)

    def _on_canvas_brush_radius_changed(self, radius: int) -> None:
        if self.skySettings is not None:
            with QSignalBlocker(self.skySettings.ui.brushSlider):
                self.skySettings.ui.brushSlider.setValue(radius)
            with QSignalBlocker(self.skySettings.ui.brushRadius):
                self.skySettings.ui.brushRadius.setValue(radius)

    def _on_canvas_mask_changed(self) -> None:
        if not hasattr(self.shell, "canvas_main") or self.shell.canvas_main is None:
            return
        mask = self.shell.canvas_main.getDenoiseMask()
        if mask is not None:
            self._save_mask_to_project(mask)

    def _apply_mask_to_canvas_and_project(self, mask: np.ndarray) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is not None:
            self.showFile(ref)
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setDenoiseMask(mask)
            self.shell.canvas_main.setMaskEditMode(True)
        if self.skySettings is not None:
            with QSignalBlocker(self.skySettings.ui.showMaskOverlay):
                self.skySettings.ui.showMaskOverlay.setChecked(True)
        self._save_mask_to_project(mask)

    def _on_detection_finished(self, mask: np.ndarray) -> None:
        self._apply_mask_to_canvas_and_project(mask)
        if self.skyCard is not None:
            self.skyCard.setStatus("done")
        self.updateReadyStates()

    def _save_mask_to_project(self, mask: np.ndarray) -> None:
        out_mask = self._get_project_mask_path()
        from startrails.lib.denoise.io.mask import MaskHandler
        MaskHandler.save_brush_mask(mask, out_mask)
        if hasattr(self.app.workflow, "project") and self.app.workflow.project is not None:
            self.app.workflow.project.mask_path = str(out_mask)
            if hasattr(self.app.workflow, "save_project"):
                self.app.workflow.save_project()
            elif hasattr(self.app, "saveProject"):
                self.app.saveProject()
        self.updateReadyStates()

    def do_detect_sky_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return

        # 1. Immediately ensure the canvas is showing the reference image
        self.showFile(ref)

        vals = self.skySettings.values() if self.skySettings else {}
        search_radius = vals.get("mask_search_radius")
        erosion_pixels = vals.get("mask_erosion_pixels", 5)

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Detecting sky mask...",
            )
            try:
                def on_detect_tick(total, inc, count, done, data=None):
                    progressUpdater.signals.incrementProgress.emit(
                        progressUpdater, 2, inc, 1 if done else 0, False, data
                    )

                # Step 1: Run model detection to generate coarse sky mask
                coarse_mask = self.app.workflow.do_detect_sky(
                    ref.path,
                    progressBar=on_detect_tick,
                    model_type=vals.get("auto_mask_model", "nightstack"),
                )
                if coarse_mask is None:
                    return

                # Immediately apply coarse mask to canvas and project so user sees progress
                QTimer.singleShot(
                    0,
                    self.shell,
                    lambda m=coarse_mask: self._apply_mask_to_canvas_and_project(m),
                )

                # Step 2: Run refine mask pass with current settings (search radius, erosion pixels)
                if getattr(self.shell, "label_progressBar", None):
                    QTimer.singleShot(
                        0,
                        self.shell,
                        lambda: self.shell.label_progressBar.setText("Refining detected sky mask..."),
                    )

                def on_refine_tick(total, inc, count, done, data=None):
                    progressUpdater.signals.incrementProgress.emit(
                        progressUpdater, 2, inc, 2 if done else 1, done, data
                    )

                refined_mask = self.app.workflow.do_refine_mask(
                    ref.path,
                    coarse_mask,
                    progressBar=on_refine_tick,
                    search_radius=search_radius,
                    erosion_pixels=erosion_pixels,
                )
                final_mask = refined_mask if refined_mask is not None else coarse_mask

                # Step 3: Show the final refined mask overlay on top of the reference image on the canvas
                QTimer.singleShot(
                    0,
                    self.shell,
                    lambda m=final_mask: self._on_detection_finished(m),
                )
            except Exception as err:
                print(f"Error detecting/refining sky mask: {err}")
                import traceback
                traceback.print_exc()

        self.shell.enqueue_task("detectSky", "Detect Sky", 1, "Detecting and refining sky mask...", work)

    def do_refine_mask_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return
        vals = self.skySettings.values() if self.skySettings else {}
        search_radius = vals.get("mask_search_radius")
        erosion_pixels = vals.get("mask_erosion_pixels", 5)

        self.showFile(ref)

        current_mask = None
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            current_mask = self.shell.canvas_main.getDenoiseMask()
        if current_mask is None or not np.any(current_mask > 0):
            current_mask = self._find_existing_mask()
        if current_mask is None or not np.any(current_mask > 0):
            return

        # Ensure mask overlay stays visible on canvas if toggle is checked
        if (
            self.skySettings is not None
            and self.skySettings.ui.showMaskOverlay.isChecked()
            and hasattr(self.shell, "canvas_main")
            and self.shell.canvas_main is not None
        ):
            self.shell.canvas_main.setMaskEditMode(True)

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Refining sky mask...",
            )
            try:
                refined = self.app.workflow.do_refine_mask(
                    ref.path,
                    current_mask,
                    progressBar=progressUpdater.tick,
                    search_radius=search_radius,
                    erosion_pixels=erosion_pixels,
                )
                if refined is not None:
                    QTimer.singleShot(
                        0,
                        self.shell,
                        lambda r=refined: self._on_detection_finished(r),
                    )
            except Exception as err:
                print(f"Error refining sky mask: {err}")
                import traceback
                traceback.print_exc()

        self.shell.enqueue_task("refineMask", "Refine Mask", 1, "Refining sky mask...", work)

    def do_clear_mask_action(self) -> None:
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.clearDenoiseMask()
            mask = self.shell.canvas_main.getDenoiseMask()
            if mask is not None:
                self._save_mask_to_project(mask)
        else:
            ref = self.app.workflow.get_reference_file()
            if ref is None:
                return
            from startrails.lib.denoise.reader import ImageReader
            img = ImageReader.read(ref.path).data
            h, w = img.shape[:2]
            mask = np.zeros((h, w), dtype=np.float32)
            self._save_mask_to_project(mask)
        self.updateReadyStates()

    def do_full_frame_mask_action(self) -> None:
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.fillDenoiseMask()
            mask = self.shell.canvas_main.getDenoiseMask()
            if mask is not None:
                self._save_mask_to_project(mask)
        else:
            ref = self.app.workflow.get_reference_file()
            if ref is None:
                return
            from startrails.lib.denoise.reader import ImageReader
            img = ImageReader.read(ref.path).data
            h, w = img.shape[:2]
            mask = np.ones((h, w), dtype=np.float32)
            self._save_mask_to_project(mask)
        self.updateReadyStates()

    def do_align_stars_action(self) -> None:
        stars = self.app.workflow.get_star_files()
        if not stars:
            return

        vals = self.alignSettings.values() if self.alignSettings else {}

        def work():
            n = len(stars)
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=n,
                desc="Aligning star frames...",
            )
            cfg = self.app.workflow.get_config()
            cfg.warp_frames_for_stacking = vals.get("warp_frames", True)
            cfg.use_gpu = vals.get("use_gpu", True)
            cfg.detector_type = vals.get("detector_type", "auto")
            cfg.max_stars = vals.get("max_stars", 500)

            result = self.app.workflow.do_align_stars(
                config=cfg,
                progressBar=progressUpdater.tick,
            )
            def on_align_done():
                self.last_align_result = result
                if self.alignCard is not None:
                    self.alignCard.setStatus("done")
                if self.starFiles is not None:
                    self.starFiles.set_files(self.app.workflow.get_star_files())
                self.updateReadyStates()

            QTimer.singleShot(0, self.shell, on_align_done)

        self.shell.enqueue_task("alignStars", "Align Stars", len(stars), "Aligning frames...", work)

    def do_stack_action(self) -> None:
        stars = self.app.workflow.get_star_files() if hasattr(self.app.workflow, "get_star_files") else []
        if not stars:
            return

        vals = self.stackSettings.values() if self.stackSettings else {}
        needs_align = self.last_align_result is None or not getattr(self.last_align_result, "aligned_sky_frames", None)
        n_stars = len(stars)
        total_stack_steps = n_stars + n_stars + 1
        total_steps = (n_stars + total_stack_steps) if needs_align else total_stack_steps

        def work():
            cfg = self.app.workflow.get_config()
            cfg.stack_method = vals.get("stack_method", "sigma_clipped")
            cfg.sigma_clip_threshold = vals.get("sigma_clip_threshold", 1.2)
            cfg.sigma_clip_iterations = vals.get("sigma_clip_iterations", 3)
            cfg.use_gpu = vals.get("use_gpu", True)

            if needs_align:
                align_updater = ProgressBarUpdater(
                    getattr(self.shell, "progressBar", None),
                    getattr(self.shell, "label_progressBar", None),
                    total=len(stars),
                    desc="Aligning star frames...",
                )
                align_vals = self.alignSettings.values() if self.alignSettings else {}
                cfg.warp_frames_for_stacking = align_vals.get("warp_frames", True)
                cfg.detector_type = align_vals.get("detector_type", "auto")
                cfg.max_stars = align_vals.get("max_stars", 500)

                align_result = self.app.workflow.do_align_stars(
                    config=cfg,
                    progressBar=align_updater.tick,
                )
                if align_result is None:
                    return
                self.last_align_result = align_result
                if self.alignCard is not None:
                    QTimer.singleShot(0, self.shell, lambda: self.alignCard.setStatus("done"))
                if self.starFiles is not None:
                    QTimer.singleShot(0, self.shell, lambda: self.starFiles.set_files(self.app.workflow.get_star_files()))

            n_sky = len(self.last_align_result.aligned_sky_frames) if self.last_align_result else n_stars
            n_ground = len(self.last_align_result.raw_ground_frames) if self.last_align_result else n_stars
            actual_stack_steps = n_sky + n_ground + 1

            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=actual_stack_steps,
                desc="Stacking sky and ground frames...",
            )

            compositor = self.app.workflow.do_stack_denoise(
                aligned_sky_frames=self.last_align_result.aligned_sky_frames,
                sky_coverages=self.last_align_result.sky_coverages,
                raw_ground_frames=self.last_align_result.raw_ground_frames,
                sky_mask=self.last_align_result.sky_mask,
                config=cfg,
                progressBar=progressUpdater.tick,
            )
            def on_stack_done():
                self.last_compositor = compositor
                if compositor is not None:
                    out_files = (
                        self.app.workflow.get_output_file_list()
                        if hasattr(self.app.workflow, "get_output_file_list")
                        else []
                    )
                    if self.outputFiles is not None:
                        self.outputFiles.set_files(out_files)

                    comp_path = str(cfg.output_path) if cfg.output_path else None
                    comp_file = None
                    if comp_path:
                        for f in out_files:
                            if getattr(f, "path", None) == comp_path:
                                comp_file = f
                                break
                        if comp_file is None:
                            comp_file = OutputFile(basename=Path(comp_path).name, path=comp_path, operation="Composite")

                    if comp_file is not None:
                        self.showFile(comp_file)
                        if self.outputFiles is not None:
                            self.outputFiles.setCurrentFile(comp_file)

                    if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                        self.shell.canvas_main.clearHorizonOverlay()
                        self.shell.canvas_main.setMaskEditMode(False)
                        self.shell.canvas_main.setFromNumpyArray(
                            compositor.base_composite,
                            resetZoomAndPosition=False,
                            is_bgr=False,
                        )
                        if compositor.gradient_mask is not None:
                            self.shell.canvas_main.setGradientMask(compositor.gradient_mask)
                if self.stackCard is not None:
                    self.stackCard.setStatus("done")
                if self.tuneCard is not None:
                    self.tuneCard.setExpanded(True)
                self.updateReadyStates()

            QTimer.singleShot(0, self.shell, on_stack_done)

        self.shell.enqueue_task("stackDenoise", "Stack Denoise", total_steps, "Stacking base frames...", work)

    def do_compose_action(self) -> None:
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return

        vals = self.tuneSettings.values() if self.tuneSettings else {}

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Compositing final image...",
            )
            cfg = self.app.workflow.get_config()
            cfg.enable_horizon_corrections = vals.get("enable_horizon_corrections", True)
            cfg.denoise_horizon_band = vals.get("denoise_horizon_band", True)
            cfg.horizon_blend_percent = vals.get("horizon_blend_percent", 60.0)
            cfg.horizon_blur_radius = vals.get("horizon_blur_radius", 2.0)
            cfg.horizon_denoise_radius = vals.get("horizon_denoise_radius", 5)
            cfg.horizon_denoise_strength = vals.get("horizon_denoise_strength", 0.2)
            cfg.horizon_color_denoise_strength = vals.get("horizon_color_denoise_strength", 1.0)
            cfg.horizon_value_denoise_strength = vals.get("horizon_value_denoise_strength", 0.2)

            if hasattr(self.app.workflow.project, "get_output_dir"):
                out_dir = self.app.workflow.project.get_output_dir()
                stem = self.app.workflow._get_project_stem() if hasattr(self.app.workflow, "_get_project_stem") else "project"
                cfg.output_path = out_dir / f"{stem}_final.tif"

            res = self.app.workflow.do_compose_horizon(
                self.last_compositor,
                config=cfg,
                progressBar=progressUpdater.tick,
                sky_coverages=self.last_align_result.sky_coverages if self.last_align_result else None,
            )
            def on_compose_done():
                if res and res[0] is not None:
                    out_files = (
                        self.app.workflow.get_output_file_list()
                        if hasattr(self.app.workflow, "get_output_file_list")
                        else []
                    )
                    if self.outputFiles is not None:
                        self.outputFiles.set_files(out_files)

                    comp_path = str(res[1]) if (len(res) > 1 and res[1]) else (str(cfg.output_path) if cfg.output_path else None)
                    comp_file = None
                    if comp_path:
                        for f in out_files:
                            if getattr(f, "path", None) == comp_path:
                                comp_file = f
                                break
                        if comp_file is None:
                            comp_file = OutputFile(basename=Path(comp_path).name, path=comp_path, operation="Final Composite")
                    if comp_file is not None:
                        self.showFile(comp_file)
                        if self.outputFiles is not None:
                            self.outputFiles.setCurrentFile(comp_file)

                    if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                        self.shell.canvas_main.clearHorizonOverlay()
                        self.shell.canvas_main.setMaskEditMode(False)
                        self.shell.canvas_main.setFromNumpyArray(
                            res[0],
                            resetZoomAndPosition=False,
                            is_bgr=False,
                        )
                if self.tuneSettings and hasattr(self.tuneSettings.ui, "tuneStatus"):
                    out_name = Path(res[1]).name if (len(res) > 1 and res[1]) else "final composite"
                    self.tuneSettings.ui.tuneStatus.setText(f"Saved: {out_name}")
                if self.tuneCard is not None:
                    self.tuneCard.setStatus("done")
                self.updateReadyStates()

            QTimer.singleShot(0, self.shell, on_compose_done)

        self.shell.enqueue_task("composeHorizon", "Compose Horizon", 2, "Compositing final image...", work)

    def do_save_output_action(self) -> None:
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return
        out_path, _ = QFileDialog.getSaveFileName(
            None,
            "Save Final Image",
            "final_denoise.tif",
            filter="TIFF Image (*.tif *.tiff);;JPEG Image (*.jpg *.jpeg)",
        )
        if not out_path:
            return

        vals = self.tuneSettings.values() if self.tuneSettings else {}
        cfg = self.app.workflow.get_config()
        cfg.output_path = Path(out_path)
        cfg.enable_horizon_corrections = vals.get("enable_horizon_corrections", True)
        cfg.denoise_horizon_band = vals.get("denoise_horizon_band", True)
        cfg.horizon_blend_percent = vals.get("horizon_blend_percent", 60.0)
        cfg.horizon_blur_radius = vals.get("horizon_blur_radius", 2.0)
        cfg.horizon_denoise_radius = vals.get("horizon_denoise_radius", 5)
        cfg.horizon_denoise_strength = vals.get("horizon_denoise_strength", 0.2)
        cfg.horizon_color_denoise_strength = vals.get("horizon_color_denoise_strength", 1.0)
        cfg.horizon_value_denoise_strength = vals.get("horizon_value_denoise_strength", 0.2)

        res = self.app.workflow.do_compose_horizon(
            self.last_compositor,
            config=cfg,
            sky_coverages=self.last_align_result.sky_coverages if self.last_align_result else None,
        )
        if res and res[0] is not None:
            from startrails.lib.denoise.writer import ImageWriter
            ImageWriter.write(res[0], Path(out_path))
            self._output_saved = True
            self.updateReadyStates()

    def do_pipeline_action(self) -> None:
        stars = self.app.workflow.get_star_files()
        if not stars:
            return

        def work():
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Running denoise pipeline...",
            )
            out_path = self.app.workflow.do_pipeline(progressBar=progressUpdater.tick)
            def on_pipeline_done():
                if out_path and Path(out_path).exists():
                    out_files = (
                        self.app.workflow.get_output_file_list()
                        if hasattr(self.app.workflow, "get_output_file_list")
                        else []
                    )
                    if self.outputFiles is not None:
                        self.outputFiles.set_files(out_files)
                    comp_file = OutputFile(basename=Path(out_path).name, path=str(out_path), operation="Composite")
                    self.showFile(comp_file)
                    if self.outputFiles is not None:
                        self.outputFiles.setCurrentFile(comp_file)
                    if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                        self.shell.canvas_main.clearHorizonOverlay()
                        self.shell.canvas_main.setMaskEditMode(False)
                if self.skyCard is not None:
                    self.skyCard.setStatus("done")
                if self.alignCard is not None:
                    self.alignCard.setStatus("done")
                if self.stackCard is not None:
                    self.stackCard.setStatus("done")
                if self.tuneCard is not None:
                    self.tuneCard.setStatus("done")
                self._output_saved = True
                self.updateReadyStates()

            QTimer.singleShot(0, self.shell, on_pipeline_done)

        self.shell.enqueue_task("pipeline", "Full Pipeline", len(stars), "Processing denoise pipeline...", work)
