"""Denoise mode sidebar view and workflow controller."""

from __future__ import annotations
import os
from concurrent.futures import CancelledError
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
from PySide6.QtCore import Slot, Qt, QTimer, QSignalBlocker
from shiboken6 import isValid
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
        self._project = app.project
        self._generation = 0
        self._disposed = False
        self._background_workers = set()
        self._sidebar: Optional[SidebarDenoise] = None
        self.star_files = None
        self.noise_files = None
        self.output_files = None

        self.sky_settings = None
        self.align_settings = None
        self.stack_settings = None
        self.tune_settings = None

        self.sky_card = None
        self.align_card = None
        self.stack_card = None
        self.tune_card = None

        self.new_project_button = None
        self.open_project_button = None
        self.btn_detect_sky = None
        self.btn_align_stars = None
        self.btn_stack = None
        self.btn_compose = None
        self.btn_save_output = None
        self.btn_pipeline = None

        self.lbl_ops_progress = None
        self.ops_progress_bar = None

        self._step_cards: tuple[StepCard, ...] = ()
        self._output_saved: bool = False

        self.last_compositor: Any = None
        self._horizon_preview_id: Optional[int] = None
        self.last_align_result: Any = None

        # Live horizon tuning worker & debounce state
        self._horizon_worker: Optional[HorizonOverlayWorker] = None
        self._horizon_request_id: int = 0
        self._pending_horizon_params: Optional[dict] = None
        self._horizon_debounce_timer = QTimer(self)
        self._horizon_debounce_timer.setSingleShot(True)
        self._horizon_debounce_timer.setInterval(75)
        self._horizon_debounce_timer.timeout.connect(self._dispatch_horizon_tuning)

        # Async final composite saver state
        self._final_save_worker: Optional[FinalCompositeSaveWorker] = None
        self._final_save_request_id: int = 0
        self._pending_final_save: Optional[dict] = None
        self._horizon_save_debounce_timer = QTimer(self)
        self._horizon_save_debounce_timer.setSingleShot(True)
        self._horizon_save_debounce_timer.setInterval(1000)
        self._horizon_save_debounce_timer.timeout.connect(self._dispatch_async_save_final_composite)

    @property
    def sidebar(self):
        return self._sidebar

    @sidebar.setter
    def sidebar(self, sidebar):
        if isinstance(sidebar, SidebarDenoise):
            self._sidebar = sidebar
            self._init_sidebar_refs()

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
        self.star_files = sb.starFiles
        self.noise_files = sb.noiseFiles
        self.output_files = getattr(sb, "outputFiles", None)
        self.sky_settings = sb.skySettings
        self.align_settings = sb.alignSettings
        self.stack_settings = sb.stackSettings
        self.tune_settings = sb.tuneSettings
        self.sky_card = sb.skyCard
        self.align_card = sb.alignCard
        self.stack_card = sb.stackCard
        self.tune_card = sb.tuneCard
        self.new_project_button = sb.pushButton_newProject
        self.open_project_button = sb.pushButton_openProject
        self.btn_detect_sky = sb.btn_detect_sky
        self.btn_align_stars = sb.btn_align_stars
        self.btn_stack = sb.btn_stack
        self.btn_compose = sb.btn_compose
        self.btn_save_output = sb.btn_save_output
        self.btn_pipeline = sb.btn_pipeline
        self.lbl_ops_progress = sb.lbl_ops_progress
        self.ops_progress_bar = sb.ops_progress_bar
        self._step_cards = sb._step_cards

    def _collapse_other_steps(self, expanded_card: StepCard) -> None:
        if self._sidebar is not None:
            self._sidebar._collapse_other_steps(expanded_card)

    def bind(self) -> None:
        if self.sidebar is None:
            return

        if self.new_project_button is not None and hasattr(self.shell, "doNewProject"):
            self.connect_signal(self.new_project_button.clicked, self.shell.doNewProject)
        if self.open_project_button is not None and hasattr(self.shell, "doOpenProject"):
            self.connect_signal(self.open_project_button.clicked, self.shell.doOpenProject)

        # Connect FileSection actions
        signals = getSignals()
        for section in (self.star_files, self.noise_files, self.output_files):
            if section is not None:
                self.connect_signal(signals.focusFile, section.focus_file)

        if self.star_files is not None:
            self.connect_signal(self.star_files.addRequested, self.select_star_files)
            self.connect_signal(self.star_files.showFile, self.showFile)
            self.connect_signal(self.star_files.removeFile, self.remove_star_file)
            self.connect_signal(self.star_files.setReferenceRequested, self.set_reference_file)

        if self.noise_files is not None:
            self.connect_signal(self.noise_files.addRequested, self.select_noise_files)
            self.connect_signal(self.noise_files.showFile, self.showFile)
            self.connect_signal(self.noise_files.removeFile, self.remove_noise_file)

        if self.output_files is not None:
            self.connect_signal(self.output_files.showFile, self.showFile)
            self.connect_signal(self.output_files.removeFile, self.remove_output_file)

        # Connect operation actions
        if self.btn_detect_sky is not None:
            self.connect_signal(self.btn_detect_sky.clicked, self.do_detect_sky_action)
        if self.sky_settings is not None:
            self.connect_signal(self.sky_settings.ui.refineMask.clicked, self.do_refine_mask_action)
            self.connect_signal(self.sky_settings.clear_mask_requested, self.do_clear_mask_action)
            self.connect_signal(self.sky_settings.full_frame_requested, self.do_full_frame_mask_action)
            self.connect_signal(self.sky_settings.mask_edit_toggled, self._on_mask_edit_toggled)
            self.connect_signal(self.sky_settings.brush_radius_changed, self._on_brush_radius_changed)
        if self.btn_align_stars is not None:
            self.connect_signal(self.btn_align_stars.clicked, self.do_align_stars_action)
        if self.align_settings is not None:
            self.connect_signal(self.align_settings.settings_changed, self._on_alignment_settings_changed)
        if self.stack_settings is not None:
            self.connect_signal(self.stack_settings.settings_changed, self._on_stack_settings_changed)
        if self.btn_stack is not None:
            self.connect_signal(self.btn_stack.clicked, self.do_stack_action)
        if self.btn_compose is not None:
            self.connect_signal(self.btn_compose.clicked, self.do_compose_action)
        if self.tune_settings is not None:
            self.connect_signal(self.tune_settings.gradient_mask_toggled, self._on_gradient_mask_toggled)
            self.connect_signal(self.tune_settings.settings_changed, self._schedule_horizon_tuning)
        if self.tune_card is not None:
            self.connect_signal(self.tune_card.expanded, lambda: self._schedule_horizon_tuning(save=False))
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.connect_signal(self.shell.canvas_main.mask_changed, self._on_canvas_mask_changed)
            self.connect_signal(self.shell.canvas_main.brush_radius_changed, self._on_canvas_brush_radius_changed)
        if self.btn_save_output is not None:
            self.connect_signal(self.btn_save_output.clicked, self.do_save_output_action)
        if self.btn_pipeline is not None:
            self.connect_signal(self.btn_pipeline.clicked, self.do_pipeline_action)

    # -------------------------------------------------------------------------
    # File Management
    # -------------------------------------------------------------------------

    def select_star_files(self) -> None:
        file_names, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Star Images",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if file_names and hasattr(self.app.workflow, "add_star_files"):
            self.app.workflow.add_star_files(file_names)
            self.reset_project_view()

    def remove_star_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_star_file"):
            self.app.workflow.remove_star_file(file)
            self.reset_project_view()

    def set_reference_file(self, file: DenoiseInputFile) -> None:
        if hasattr(self.app.workflow, "set_reference_file"):
            self.app.workflow.set_reference_file(file)
            if self.align_settings is not None:
                self.align_settings.set_reference_file(file)
            self.reset_project_view()

    def select_noise_files(self) -> None:
        file_names, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Dark/Noise Frames",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if file_names and hasattr(self.app.workflow, "add_noise_files"):
            self.app.workflow.add_noise_files(file_names)
            self.reset_project_view()

    def remove_noise_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_noise_file"):
            self.app.workflow.remove_noise_file(file)
            self.reset_project_view()


    def reset_project_view(self) -> None:
        if not hasattr(self.app.workflow, "get_star_files"):
            return
        self.app.workflow.project.validate_cached_results()
        alignment_result = self.last_align_result if (
            self._project is self.app.project and self.app.project.alignment_is_current()
        ) else None
        self._generation += 1
        self._project = self.app.project
        self.last_align_result = alignment_result
        self.last_compositor = None
        self._output_saved = False
        self._pending_horizon_params = None
        self._pending_final_save = None
        self._horizon_request_id += 1
        self._final_save_request_id += 1
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            canvas.set_denoise_mask(None)
            canvas.set_gradient_mask(None)
            canvas.clear_horizon_overlay()
        self._cancel_background_jobs()

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

        if self.star_files is not None:
            self.star_files.set_files(stars)
        if self.noise_files is not None:
            self.noise_files.set_files(darks)
        if self.output_files is not None:
            self.output_files.set_files(self.app.getOutputFileList())

        if self.sky_settings is not None:
            self.sky_settings.set_from_project()
        if self.align_settings is not None:
            self.align_settings.set_from_project()
        if self.stack_settings is not None:
            self.stack_settings.set_from_project()
        if self.tune_settings is not None:
            self.tune_settings.set_from_project()

        self.update_ready_states()

        ref = self.app.workflow.get_reference_file()
        if ref is not None:
            self.show_file(ref)
        elif stars:
            self.show_file(stars[0])
        else:
            self.show_file(None)

        existing_mask = self._find_existing_mask()
        if existing_mask is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.set_denoise_mask(existing_mask)
            if self.sky_card is not None:
                self.sky_card.setStatus("done")

        if getattr(self.app.workflow, "project", None) and getattr(self.app.workflow.project, "homographies", None):
            if self.align_card is not None:
                self.align_card.setStatus("done")

        existing_comp = self._find_existing_compositor()
        if existing_comp is not None:
            self.last_compositor = existing_comp
            if self.stack_card is not None:
                self.stack_card.setStatus("done")
        self.update_ready_states()

        if self.sidebar is not None:
            self.sidebar.sync_expanded_step()

    def _snapshot_config(self, task_id):
        revision = self.app.workflow.project.processing_revision
        try:
            config = self.app.workflow.get_config()
        except Exception as error:
            self._show_task_error(task_id, str(error))
            return None
        if revision != self.app.workflow.project.processing_revision:
            if not self.app.project.alignment_is_current():
                self.last_align_result = None
            self.last_compositor = None
            self._output_saved = False
            self._generation += 1
            self._cancel_background_jobs()
            self.update_ready_states()
        return config

    def _enqueue_task(self, task_id, title, total, desc, work):
        workflow = self.app.workflow
        generation = self._generation
        revision = workflow.project.processing_revision
        def run():
            if generation != self._generation or workflow.project is not self.app.project or revision != workflow.project.processing_revision:
                return
            try:
                with workflow.operation_session():
                    work()
            except CancelledError:
                self._post_result(generation, lambda: self._show_task_error(task_id, "Cancelled"))
            except Exception as error:
                message = str(error)
                self._post_result(generation, lambda: self._show_task_error(task_id, f"Failed: {message}"))
        return self.shell.enqueue_task(task_id, title, total, desc, run)

    def _show_task_error(self, task_id: str, message: str) -> None:
        settings = {
            "detectSky": self.sky_settings, "refineMask": self.sky_settings,
            "alignStars": self.align_settings, "stackDenoise": self.stack_settings,
            "composeHorizon": self.tune_settings, "exportDenoise": self.tune_settings,
            "pipeline": self.tune_settings,
        }.get(task_id)
        if settings is not None:
            settings.ui.error.setText(message)
            settings.ui.error.show()

    def _result_guard(self, generation):
        project = self._project
        return lambda: not self._disposed and generation == self._generation and project is self.app.project

    def _post_result(self, generation: int, callback) -> None:
        """Deliver only results belonging to this view's current project session."""
        def deliver():
            if not self._disposed and generation == self._generation and self._project is self.app.project:
                callback()

        QTimer.singleShot(0, self.shell, deliver)

    def show_file(self, file: Optional[File]) -> None:
        self._horizon_preview_id = None
        if hasattr(self.shell, "currentFile"):
            self.shell.currentFile = file
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFile(file)
            ref = self.app.workflow.get_reference_file() if hasattr(self.app, "workflow") else None
            if (
                file is not None
                and ref is not None
                and getattr(file, "path", None) == getattr(ref, "path", None)
                and self.sky_settings is not None
                and self.sky_settings.ui.showMaskOverlay.isChecked()
            ):
                self.shell.canvas_main.set_mask_edit_mode(True)
            else:
                self.shell.canvas_main.set_mask_edit_mode(False)
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
        if self.output_files is not None:
            self.output_files.set_files(self.app.getOutputFileList())

    def update_ready_states(self, _=None) -> None:
        has_stars = bool(hasattr(self.app.workflow, "get_star_files") and self.app.workflow.get_star_files())
        has_compositor = bool(self.last_compositor is not None or self._has_existing_stacks())
        if self.btn_pipeline is not None:
            self.btn_pipeline.setEnabled(has_stars)
        if self.btn_save_output is not None:
            self.btn_save_output.setEnabled(has_compositor)

        if self.sidebar is not None:
            self.sidebar.set_has_compositor(has_compositor)
            self.sidebar.set_output_saved(self._output_saved)
            self.sidebar.update_operations_progress(self.app)

    def _on_alignment_settings_changed(self) -> None:
        self.app.workflow.invalidate_results()
        self.reset_project_view()

    def _on_stack_settings_changed(self) -> None:
        self.app.workflow.invalidate_results(alignment=False)
        self._generation += 1
        self.last_compositor = None
        self._output_saved = False
        self._cancel_background_jobs()
        self.update_ready_states()

    def _cancel_background_jobs(self) -> None:
        self._horizon_preview_id = None
        self._horizon_debounce_timer.stop()
        self._horizon_save_debounce_timer.stop()
        self._pending_horizon_params = None
        self._pending_final_save = None
        self._horizon_request_id += 1
        self._final_save_request_id += 1
        for worker in tuple(self._background_workers):
            worker.cancel()

    def teardown(self) -> None:
        self._disposed = True
        self._generation += 1
        self._cancel_background_jobs()
        self.last_align_result = None
        self.last_compositor = None
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            canvas.set_mask_edit_mode(False)
            canvas.clear_horizon_overlay()
            canvas.set_gradient_mask_visible(False)
        super().teardown()
        if self._sidebar is not None:
            self._sidebar.setParent(None)
        if not self._background_workers:
            self._dispose_retired_view()

    def _dispose_retired_view(self) -> None:
        if self._sidebar is not None:
            self._sidebar.deleteLater()
            self._sidebar = None
        self.deleteLater()

    def wait_for_workers(self) -> None:
        """Keep QThreads alive through shutdown, including retired project jobs."""
        for worker in tuple(self._background_workers):
            worker.cancel()
            worker.wait()
            staged = getattr(worker, "staged_path", None)
            if staged is not None:
                staged.unlink(missing_ok=True)

    def _track_worker(self, worker) -> None:
        worker.project = self._project
        worker.generation = self._generation
        self._background_workers.add(worker)
        def release():
            self._background_workers.discard(worker)
            if isValid(worker):
                worker.deleteLater()
            if self._disposed and not self._background_workers and isValid(self):
                self._dispose_retired_view()
        worker.finished.connect(release)

    def _worker_is_current(self, worker, request_id: int, latest_id: int) -> bool:
        return (
            not self._disposed and worker is not None
            and worker.project is self.app.project
            and worker.generation == self._generation
            and request_id == latest_id
            and not worker.is_cancelled()
        )

    def _horizon_params(self) -> dict:
        vals = self.tune_settings.values() if self.tune_settings else {}
        return {
            "blend": vals.get("horizon_blend_percent", 60.0),
            "blur_radius": vals.get("horizon_blur_radius", 2.0),
            "denoise_strength": vals.get("horizon_denoise_strength", 0.2),
            "denoise_enabled": vals.get("denoise_horizon_band", True),
            "enable_corrections": vals.get("enable_horizon_corrections", True),
            "color_denoise": vals.get("horizon_color_denoise_strength", 1.0),
            "value_denoise": vals.get("horizon_value_denoise_strength", 0.2),
        }

    def _schedule_horizon_tuning(self, save: bool = True) -> None:
        if self._disposed:
            return
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None and self._horizon_preview_id != id(self.last_compositor):
            canvas.clear_horizon_overlay()
            canvas.set_mask_edit_mode(False)
            canvas.setFromNumpyArray(self.last_compositor.base_composite, resetZoomAndPosition=False, is_bgr=False)
            self._horizon_preview_id = id(self.last_compositor)
        # Invalidate immediately, before the debounce interval elapses.
        self._horizon_request_id += 1
        if save:
            self._final_save_request_id += 1
        for worker in tuple(self._background_workers):
            if save or isinstance(worker, HorizonOverlayWorker):
                worker.cancel()
        if self._horizon_params()["enable_corrections"]:
            self._horizon_debounce_timer.start()
        else:
            self._horizon_debounce_timer.stop()
            self._pending_horizon_params = None
            if canvas is not None:
                canvas.clear_horizon_overlay()
        if save:
            self._horizon_save_debounce_timer.start()

    def _dispatch_async_save_final_composite(self) -> None:
        if self._disposed or self._project is not self.app.project or self.last_compositor is None:
            return
        if self._final_save_worker is not None and self._final_save_worker in self._background_workers:
            self._pending_final_save = True
            return
        self._pending_final_save = None
        project = self._project
        worker = FinalCompositeSaveWorker(
            self.last_compositor, self._horizon_params(),
            project.get_output_dir() / f"{project.get_project_stem()}_final.tif",
            self._final_save_request_id, parent=self,
        )
        self._final_save_worker = worker
        self._track_worker(worker)
        worker.finished_save.connect(self._on_final_save_finished)
        worker.failed_error.connect(self._on_background_error)
        worker.finished.connect(self._on_final_save_worker_done)
        worker.start()

    def _on_final_save_worker_done(self) -> None:
        self._final_save_worker = None
        if self._pending_final_save and not self._disposed:
            self._dispatch_async_save_final_composite()

    def _on_final_save_finished(
        self, staged_path: Any, req_id: Any, legacy_req_id: Optional[int] = None
    ) -> None:
        if legacy_req_id is not None:
            req_id = legacy_req_id
        worker = self.sender() or self._final_save_worker
        staged_path = Path(staged_path)
        if not self._worker_is_current(worker, req_id, self._final_save_request_id):
            staged_path.unlink(missing_ok=True)
            return
        try:
            # Only the GUI thread can publish; project switches/settings changes
            # cannot race this final ownership check and atomic replacement.
            out_path = Path(worker.output_path)
            os.replace(staged_path, out_path)
            self._project.final_output_path = str(out_path)
            self._output_saved = True
            self.app.workflow.save_project()
            if self.tune_card is not None:
                self.tune_card.setStatus("done")
            if self.output_files is not None:
                self.output_files.set_files(self.app.workflow.get_output_file_list())
            if self.tune_settings is not None:
                self.tune_settings.ui.tuneStatus.setText(f"Saved: {out_path.name}")
            self.update_ready_states()
        except Exception as error:
            staged_path.unlink(missing_ok=True)
            self._on_background_error(str(error), req_id)

    def _dispatch_horizon_tuning(self) -> None:
        if self._disposed or self._project is not self.app.project or self.last_compositor is None:
            return
        if not self._horizon_params()["enable_corrections"]:
            return
        if self._horizon_worker is not None and self._horizon_worker in self._background_workers:
            self._pending_horizon_params = True
            return
        self._pending_horizon_params = None
        worker = HorizonOverlayWorker(
            self.last_compositor, self._horizon_params(), self._horizon_request_id, parent=self,
        )
        self._horizon_worker = worker
        self._track_worker(worker)
        worker.finished_patches.connect(self._on_horizon_patches_ready)
        worker.failed_error.connect(self._on_background_error)
        worker.finished.connect(self._on_horizon_worker_finished)
        worker.start()

    def _on_horizon_worker_finished(self) -> None:
        self._horizon_worker = None
        if self._pending_horizon_params and not self._disposed:
            self._dispatch_horizon_tuning()

    def _on_horizon_patches_ready(self, patches, req_id: int) -> None:
        worker = self.sender() or self._horizon_worker
        if self._worker_is_current(worker, req_id, self._horizon_request_id) and patches is not None:
            canvas = getattr(self.shell, "canvas_main", None)
            if canvas is not None:
                canvas.set_horizon_patches(patches)

    def _on_background_error(self, message: str, req_id: int) -> None:
        worker = self.sender()
        if worker is not None and (worker.project is not self.app.project or worker.is_cancelled() or worker.generation != self._generation):
            return
        if not self._disposed and self.tune_settings is not None:
            self.tune_settings.ui.tuneStatus.setText(f"Failed: {message}")

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
                    from startrails.lib.denoise.mask import MaskHandler
                    mask = MaskHandler.load_mask(p)
            if mask is not None:
                self.shell.canvas_main.set_gradient_mask(mask)
            self.shell.canvas_main.set_gradient_mask_visible(True)
        else:
            self.shell.canvas_main.set_gradient_mask_visible(False)

    def _find_existing_mask(self) -> Optional[np.ndarray]:
        project = self.app.workflow.project
        if project.mask_invalidated:
            return None
        path = project.mask_path
        if path is None:
            candidate = project.get_output_dir() / "mask.png"
            path = str(candidate) if candidate.is_file() else None
        if path is None or not Path(path).is_file():
            return None
        from startrails.lib.denoise.mask import MaskHandler
        return MaskHandler.load_mask(path)

    def _has_existing_stacks(self) -> bool:
        project = getattr(self.app.workflow, "project", None)
        return bool(project and project.stacks_are_current())

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
                from startrails.lib.denoise.mask import MaskHandler
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
                        from startrails.lib.denoise.mask import MaskHandler
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
                    self.show_file(ref)

            current_m = self.shell.canvas_main.get_denoise_mask()
            if current_m is None:
                existing_mask = self._find_existing_mask()
                if existing_mask is not None:
                    self.shell.canvas_main.set_denoise_mask(existing_mask)
                else:
                    self.shell.canvas_main.fill_denoise_mask()
                    current_mask = self.shell.canvas_main.get_denoise_mask()
                    if current_mask is not None:
                        self._save_mask_to_project(current_mask)
        self.shell.canvas_main.set_mask_edit_mode(enabled)

    def _on_brush_radius_changed(self, radius: int) -> None:
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.set_brush_radius(radius)

    def _on_canvas_brush_radius_changed(self, radius: int) -> None:
        if self.sky_settings is not None:
            with QSignalBlocker(self.sky_settings.ui.brushSlider):
                self.sky_settings.ui.brushSlider.setValue(radius)
            with QSignalBlocker(self.sky_settings.ui.brushRadius):
                self.sky_settings.ui.brushRadius.setValue(radius)

    def _on_canvas_mask_changed(self) -> None:
        if not hasattr(self.shell, "canvas_main") or self.shell.canvas_main is None:
            return
        mask = self.shell.canvas_main.get_denoise_mask()
        if mask is not None:
            self._save_mask_to_project(mask)

    def _apply_mask_to_canvas_and_project(self, mask: np.ndarray) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is not None:
            self.show_file(ref)
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.set_denoise_mask(mask)
            self.shell.canvas_main.set_mask_edit_mode(True)
        if self.sky_settings is not None:
            with QSignalBlocker(self.sky_settings.ui.showMaskOverlay):
                self.sky_settings.ui.showMaskOverlay.setChecked(True)
        self._save_mask_to_project(mask)

    def _on_detection_finished(self, mask: np.ndarray) -> None:
        self._apply_mask_to_canvas_and_project(mask)
        if self.sky_card is not None:
            self.sky_card.setStatus("done")
        self.update_ready_states()

    def _save_mask_to_project(self, mask: np.ndarray) -> None:
        out_mask = self._get_project_mask_path()
        from startrails.lib.denoise.mask import MaskHandler
        MaskHandler.save_brush_mask(mask, out_mask)
        if hasattr(self.app.workflow, "project") and self.app.workflow.project is not None:
            self.app.workflow.project.mask_path = str(out_mask)
            self.app.workflow.project.mask_invalidated = False
            self.app.workflow.invalidate_results()
            self.last_align_result = None
            self.last_compositor = None
            self._output_saved = False
            self._generation += 1
            self._cancel_background_jobs()
            if hasattr(self.app.workflow, "save_project"):
                self.app.workflow.save_project()
            elif hasattr(self.app, "saveProject"):
                self.app.saveProject()
        self.update_ready_states()

    def do_detect_sky_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return

        # 1. Immediately ensure the canvas is showing the reference image
        self.show_file(ref)

        vals = self.sky_settings.values() if self.sky_settings else {}
        search_radius = vals.get("mask_search_radius")
        erosion_pixels = vals.get("mask_erosion_pixels", 5)
        foliage_protection = self._project.mask_foliage_protection
        model_path = self._project.auto_mask_path
        device = "auto" if self._project.use_gpu else "cpu"

        generation = self._generation

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1000,
                desc="Detecting sky mask...",
                result_guard=self._result_guard(generation),
            )
            try:
                reported = 0

                def report_stage(offset, total, count, done, data):
                    nonlocal reported
                    target = offset + (500 if done else round(500 * count / max(total, 1)))
                    increment = max(0, target - reported)
                    reported += increment
                    progress_updater.tick(1000, increment, reported, offset == 500 and done, data)

                def on_detect_tick(total, inc, count, done, data=None):
                    report_stage(0, total, count, done, data)

                # Step 1: Run model detection to generate coarse sky mask
                coarse_mask = self.app.workflow.do_detect_sky(
                    ref.path,
                    progress_bar=on_detect_tick,
                    model_type=vals.get("auto_mask_model", "nightstack"),
                    model_path=model_path,
                    device=device,
                )
                if coarse_mask is None:
                    return

                # Step 2: Run refine mask pass with current settings (search radius, erosion pixels)
                progress_updater.tick(1000, 0, reported, False, {"desc": "Refining detected sky mask..."})

                def on_refine_tick(total, inc, count, done, data=None):
                    report_stage(500, total, count, done, data)

                refined_mask = self.app.workflow.do_refine_mask(
                    ref.path,
                    coarse_mask,
                    progress_bar=on_refine_tick,
                    search_radius=search_radius,
                    erosion_pixels=erosion_pixels,
                    foliage_protection=foliage_protection,
                )
                if refined_mask is None:
                    return
                final_mask = refined_mask

                # Step 3: Show the final refined mask overlay on top of the reference image on the canvas
                self._post_result(generation, lambda m=final_mask: self._on_detection_finished(m))
            except Exception:
                raise

        self._enqueue_task("detectSky", "Detect Sky", 1, "Detecting and refining sky mask...", work)

    def do_refine_mask_action(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return
        vals = self.sky_settings.values() if self.sky_settings else {}
        search_radius = vals.get("mask_search_radius")
        erosion_pixels = vals.get("mask_erosion_pixels", 5)
        foliage_protection = self._project.mask_foliage_protection
        model_path = self._project.auto_mask_path
        device = "auto" if self._project.use_gpu else "cpu"

        self.show_file(ref)

        current_mask = None
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            current_mask = self.shell.canvas_main.get_denoise_mask()
        if current_mask is None or not np.any(current_mask > 0):
            current_mask = self._find_existing_mask()
        if current_mask is None or not np.any(current_mask > 0):
            return

        # Ensure mask overlay stays visible on canvas if toggle is checked
        if (
            self.sky_settings is not None
            and self.sky_settings.ui.showMaskOverlay.isChecked()
            and hasattr(self.shell, "canvas_main")
            and self.shell.canvas_main is not None
        ):
            self.shell.canvas_main.set_mask_edit_mode(True)

        generation = self._generation

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Refining sky mask...",
                result_guard=self._result_guard(generation),
            )
            try:
                refined = self.app.workflow.do_refine_mask(
                    ref.path,
                    current_mask,
                    progress_bar=progress_updater.tick,
                    search_radius=search_radius,
                    erosion_pixels=erosion_pixels,
                    foliage_protection=foliage_protection,
                )
                if refined is not None:
                    self._post_result(generation, lambda r=refined: self._on_detection_finished(r))
            except Exception:
                raise

        self._enqueue_task("refineMask", "Refine Mask", 1, "Refining sky mask...", work)

    def do_clear_mask_action(self) -> None:
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.clear_denoise_mask()
            mask = self.shell.canvas_main.get_denoise_mask()
            if mask is not None:
                self._save_mask_to_project(mask)
        else:
            ref = self.app.workflow.get_reference_file()
            if ref is None:
                return
            from startrails.lib.util import imread
            img = imread(ref.path, to_rgb=True, as_float=True)
            h, w = img.shape[:2]
            mask = np.zeros((h, w), dtype=np.float32)
            self._save_mask_to_project(mask)
        self.update_ready_states()

    def do_full_frame_mask_action(self) -> None:
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.fill_denoise_mask()
            mask = self.shell.canvas_main.get_denoise_mask()
            if mask is not None:
                self._save_mask_to_project(mask)
        else:
            ref = self.app.workflow.get_reference_file()
            if ref is None:
                return
            from startrails.lib.util import imread
            img = imread(ref.path, to_rgb=True, as_float=True)
            h, w = img.shape[:2]
            mask = np.ones((h, w), dtype=np.float32)
            self._save_mask_to_project(mask)
        self.update_ready_states()

    def do_align_stars_action(self) -> None:
        stars = self.app.workflow.get_star_files()
        if not stars:
            return
        config_snapshot = self._snapshot_config("alignStars")
        if config_snapshot is None:
            return

        vals = self.align_settings.values() if self.align_settings else {}

        generation = self._generation

        def work():
            n = len(stars)
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=n,
                desc="Aligning star frames...",
                result_guard=self._result_guard(generation),
            )
            cfg = config_snapshot
            cfg.use_gpu = vals.get("use_gpu", True)

            result = self.app.workflow.do_align_stars(
                config=cfg,
                progress_bar=progress_updater.tick,
            )
            if result is None:
                return
            def on_align_done():
                self.last_align_result = result
                if self.align_card is not None:
                    self.align_card.setStatus("done")
                if self.star_files is not None:
                    self.star_files.set_files(self.app.workflow.get_star_files())
                self.update_ready_states()

            self._post_result(generation, on_align_done)

        self._enqueue_task("alignStars", "Align Stars", len(stars), "Aligning frames...", work)

    def do_stack_action(self) -> None:
        stars = self.app.workflow.get_star_files() if hasattr(self.app.workflow, "get_star_files") else []
        if not stars:
            return
        config_snapshot = self._snapshot_config("stackDenoise")
        if config_snapshot is None:
            return

        vals = self.stack_settings.values() if self.stack_settings else {}
        needs_prepare = self.last_align_result is None or not getattr(self.last_align_result, "aligned_sky_frames", None)
        n_stars = len(stars)
        total_stack_steps = n_stars + n_stars + 1
        total_steps = (n_stars + total_stack_steps) if needs_prepare else total_stack_steps

        prepare_description = (
            "Preparing aligned frames from saved transforms..."
            if self.app.workflow.has_cached_alignment(config_snapshot) else "Aligning star frames..."
        )
        generation = self._generation

        def work():
            cfg = config_snapshot
            cfg.stack_method = vals.get("stack_method", "sigma_clipped")
            cfg.sigma_clip_threshold = vals.get("sigma_clip_threshold", 1.2)
            cfg.sigma_clip_iterations = vals.get("sigma_clip_iterations", 3)
            cfg.use_gpu = vals.get("use_gpu", True)

            if needs_prepare:
                align_updater = ProgressBarUpdater(
                    getattr(self.shell, "progressBar", None),
                    getattr(self.shell, "label_progressBar", None),
                    total=len(stars),
                    desc=prepare_description,
                    result_guard=self._result_guard(generation),
                )

                align_result = self.app.workflow.do_align_stars(
                    config=cfg,
                    progress_bar=align_updater.tick,
                )
                if align_result is None:
                    return
                self.last_align_result = align_result
                if self.align_card is not None:
                    self._post_result(generation, lambda: self.align_card.setStatus("done"))
                if self.star_files is not None:
                    self._post_result(generation, lambda: self.star_files.set_files(self.app.workflow.get_star_files()))

            n_sky = len(self.last_align_result.aligned_sky_frames) if self.last_align_result else n_stars
            n_ground = len(self.last_align_result.raw_ground_frames) if self.last_align_result else n_stars
            actual_stack_steps = n_sky + n_ground + 1

            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=actual_stack_steps,
                desc="Stacking sky and ground frames...",
                result_guard=self._result_guard(generation),
            )

            compositor = self.app.workflow.do_stack_denoise(
                aligned_sky_frames=self.last_align_result.aligned_sky_frames,
                sky_coverages=self.last_align_result.sky_coverages,
                raw_ground_frames=self.last_align_result.raw_ground_frames,
                sky_mask=self.last_align_result.sky_mask,
                config=cfg,
                progress_bar=progress_updater.tick,
            )
            if compositor is None:
                return
            def on_stack_done():
                self.last_compositor = compositor
                if compositor is not None:
                    out_files = (
                        self.app.workflow.get_output_file_list()
                        if hasattr(self.app.workflow, "get_output_file_list")
                        else []
                    )
                    if self.output_files is not None:
                        self.output_files.set_files(out_files)

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
                        self.show_file(comp_file)
                        if self.output_files is not None:
                            self.output_files.setCurrentFile(comp_file)

                    if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                        self.shell.canvas_main.clear_horizon_overlay()
                        self.shell.canvas_main.set_mask_edit_mode(False)
                        self.shell.canvas_main.setFromNumpyArray(
                            compositor.base_composite,
                            resetZoomAndPosition=False,
                            is_bgr=False,
                        )
                        self._horizon_preview_id = id(compositor)
                        if compositor.gradient_mask is not None:
                            self.shell.canvas_main.set_gradient_mask(compositor.gradient_mask)
                if self.stack_card is not None:
                    self.stack_card.setStatus("done")
                self.update_ready_states()
                if self.tune_card is not None:
                    self.tune_card.setExpanded(True)

            self._post_result(generation, on_stack_done)

        self._enqueue_task("stackDenoise", "Stack Denoise", total_steps, "Stacking base frames...", work)

    def _composition_config(self, output_path):
        config = self._snapshot_config("composeHorizon")
        if config is None:
            return None
        config.output_path = Path(output_path)
        if self.tune_settings is not None:
            for name, value in self.tune_settings.values().items():
                if hasattr(config, name):
                    setattr(config, name, value)
        return config

    def _enqueue_composition(self, config, task_id: str, title: str) -> None:
        if config is None:
            return
        if self.last_compositor is None:
            self._show_task_error(task_id, "Inputs changed. Regenerate the base stacks before exporting.")
            return
        workflow = self.app.workflow
        compositor = self.last_compositor
        coverages = self.last_align_result.sky_coverages if self.last_align_result else None
        generation = self._generation
        self._cancel_background_jobs()

        def work():
            updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2, desc="Compositing and saving final image...",
                result_guard=self._result_guard(generation),
            )
            result = workflow.do_compose_horizon(
                compositor, config=config, progress_bar=updater.tick, sky_coverages=coverages,
            )
            if result is None:
                return

            def publish():
                image, output_path = result
                self._output_saved = True
                if self.output_files is not None:
                    self.output_files.set_files(workflow.get_output_file_list())
                output = OutputFile(basename=output_path.name, path=str(output_path), operation="Final Composite")
                self.show_file(output)
                canvas = getattr(self.shell, "canvas_main", None)
                if canvas is not None:
                    canvas.clear_horizon_overlay()
                    canvas.set_mask_edit_mode(False)
                    canvas.setFromNumpyArray(image, resetZoomAndPosition=False, is_bgr=False)
                if self.tune_settings is not None:
                    self.tune_settings.ui.tuneStatus.setText(f"Saved: {output_path.name}")
                self.update_ready_states()

            self._post_result(generation, publish)

        self._enqueue_task(task_id, title, 2, "Compositing final image...", work)

    def do_compose_action(self) -> None:
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return
        project = self.app.workflow.project
        output = project.get_output_dir() / f"{project.get_project_stem()}_final.tif"
        self._enqueue_composition(self._composition_config(output), "composeHorizon", "Compose Horizon")

    def do_save_output_action(self) -> None:
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return
        output, _ = QFileDialog.getSaveFileName(
            None, "Save Final Image", "final_denoise.tif",
            filter="TIFF Image (*.tif *.tiff);;JPEG Image (*.jpg *.jpeg)",
        )
        if output:
            self._enqueue_composition(self._composition_config(output), "exportDenoise", "Export Denoise")

    def do_pipeline_action(self) -> None:
        stars = self.app.workflow.get_star_files()
        if not stars:
            return
        config_snapshot = self._snapshot_config("pipeline")
        if config_snapshot is None:
            return

        generation = self._generation

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Running denoise pipeline...",
                result_guard=self._result_guard(generation),
            )
            out_path = self.app.workflow.do_pipeline(config=config_snapshot, progress_bar=progress_updater.tick)
            def on_pipeline_done():
                if out_path and Path(out_path).exists():
                    self.last_compositor = self.app.workflow.last_compositor
                    self.last_align_result = None
                    out_files = (
                        self.app.workflow.get_output_file_list()
                        if hasattr(self.app.workflow, "get_output_file_list")
                        else []
                    )
                    if self.output_files is not None:
                        self.output_files.set_files(out_files)
                    comp_file = OutputFile(basename=Path(out_path).name, path=str(out_path), operation="Composite")
                    self.show_file(comp_file)
                    if self.output_files is not None:
                        self.output_files.setCurrentFile(comp_file)
                    if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                        self.shell.canvas_main.clear_horizon_overlay()
                        self.shell.canvas_main.set_mask_edit_mode(False)
                if self.sky_card is not None:
                    self.sky_card.setStatus("done")
                if self.align_card is not None:
                    self.align_card.setStatus("done")
                if self.stack_card is not None:
                    self.stack_card.setStatus("done")
                if self.tune_card is not None:
                    self.tune_card.setStatus("done")
                self._output_saved = True
                self.update_ready_states()

            self._post_result(generation, on_pipeline_done)

        self._enqueue_task("pipeline", "Full Pipeline", len(stars), "Processing denoise pipeline...", work)

# Compatibility with the shared legacy app shell.
DenoiseView.resetProjectView = DenoiseView.reset_project_view

# Compatibility with the shared legacy app shell.
DenoiseView.showFile = DenoiseView.show_file

# Compatibility with the shared legacy app shell.
DenoiseView.updateReadyStates = DenoiseView.update_ready_states

DenoiseView.starFiles = property(lambda self: self.star_files, lambda self, value: setattr(self, "star_files", value))
DenoiseView.noiseFiles = property(lambda self: self.noise_files, lambda self, value: setattr(self, "noise_files", value))
DenoiseView.outputFiles = property(lambda self: self.output_files, lambda self, value: setattr(self, "output_files", value))
DenoiseView.skySettings = property(lambda self: self.sky_settings, lambda self, value: setattr(self, "sky_settings", value))
DenoiseView.alignSettings = property(lambda self: self.align_settings, lambda self, value: setattr(self, "align_settings", value))
DenoiseView.stackSettings = property(lambda self: self.stack_settings, lambda self, value: setattr(self, "stack_settings", value))
DenoiseView.tuneSettings = property(lambda self: self.tune_settings, lambda self, value: setattr(self, "tune_settings", value))
DenoiseView.skyCard = property(lambda self: self.sky_card, lambda self, value: setattr(self, "sky_card", value))
DenoiseView.alignCard = property(lambda self: self.align_card, lambda self, value: setattr(self, "align_card", value))
DenoiseView.stackCard = property(lambda self: self.stack_card, lambda self, value: setattr(self, "stack_card", value))
DenoiseView.tuneCard = property(lambda self: self.tune_card, lambda self, value: setattr(self, "tune_card", value))
DenoiseView.pushButton_newProject = property(lambda self: self.new_project_button, lambda self, value: setattr(self, "new_project_button", value))
DenoiseView.pushButton_openProject = property(lambda self: self.open_project_button, lambda self, value: setattr(self, "open_project_button", value))
