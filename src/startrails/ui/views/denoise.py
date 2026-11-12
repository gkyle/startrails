"""Denoise mode sidebar view and workflow controller."""

from __future__ import annotations
import os
from concurrent.futures import CancelledError
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
from PySide6.QtCore import Slot, Qt, QTimer
from shiboken6 import isValid
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QWidget,
)

from startrails.lib.denoise.defaults import (
    DEFAULT_HORIZON_FEATHER_RADIUS,
    DEFAULT_SKY_DETECTION_DEVICE,
)
from startrails.lib.file import File, DenoiseInputFile, OutputFile
from startrails.ui.file_manager import FileSection
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.sidebar_denoise import SidebarDenoise
from startrails.ui.signals import getSignals
from startrails.ui.sky_mask_controller import SkyMaskController
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
        self.has_manual_sky_corrections: bool = False
        self.star_files = None
        self.noise_files = None
        self.output_files = None

        self.sky_settings = None
        self.align_settings = None
        self.stack_settings = None
        self.tune_settings = None
        self.export_settings = None

        self.sky_card = None
        self.align_card = None
        self.stack_card = None
        self.tune_card = None
        self.export_card = None

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
        self.mask_controller: Optional[SkyMaskController] = None

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
        self.export_settings = getattr(sb, "exportSettings", None)
        self.sky_card = sb.skyCard
        self.align_card = sb.alignCard
        self.stack_card = sb.stackCard
        self.tune_card = sb.tuneCard
        self.export_card = getattr(sb, "exportCard", None)
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

        self.bind_project_actions(self.new_project_button, self.open_project_button)

        # Connect FileSection actions
        signals = getSignals()
        for section in (self.star_files, self.noise_files, self.output_files):
            if section is not None:
                self.connect_signal(signals.focusFile, section.focus_file)

        if self.star_files is not None:
            self.connect_signal(self.star_files.addRequested, self.select_star_files)
            self.connect_signal(self.star_files.showFile, self._on_file_section_show_file)
            self.connect_signal(self.star_files.removeFile, self.remove_star_file)
            self.connect_signal(self.star_files.setReferenceRequested, self.set_reference_file)

        if self.noise_files is not None:
            self.connect_signal(self.noise_files.addRequested, self.select_noise_files)
            self.connect_signal(self.noise_files.showFile, self._on_file_section_show_file)
            self.connect_signal(self.noise_files.removeFile, self.remove_noise_file)

        if self.output_files is not None:
            self.connect_signal(self.output_files.showFile, self._on_file_section_show_file)
            self.connect_signal(self.output_files.removeFile, self.remove_output_file)

        # Connect operation actions (resolve app.workflow dynamically so opening
        # another Denoise project keeps using the active workflow).
        if self.sky_settings is not None:
            self.connect_signal(self.sky_settings.settings_changed, lambda: self.app.workflow.save_project())
            if self.mask_controller is not None:
                self.mask_controller.teardown()

            def get_source():
                return self.app.workflow.get_reference_file()

            def show_source():
                ref = self.app.workflow.get_reference_file()
                if ref is not None:
                    canvas_has_ref = (
                        getattr(self.shell, "currentFile", None) == ref
                        and getattr(self.shell.canvas_main, "file", None) == ref
                        and self.shell.canvas_main.pixmap is not None
                        and not self.shell.canvas_main.pixmap.isNull()
                    )
                    if not canvas_has_ref:
                        self.show_file(ref, expand_sections=False)

            def on_detection_finished(mask: np.ndarray) -> None:
                self.has_manual_sky_corrections = False
                if hasattr(self.app.workflow, "project") and self.app.workflow.project is not None:
                    self.app.workflow.project.has_manual_sky_corrections = False
                self.update_ready_states()

            self.mask_controller = SkyMaskController(
                shell=self.shell,
                settings_widget=self.sky_settings,
                get_source_image=get_source,
                show_source_image=show_source,
                get_saved_mask=self._find_existing_mask,
                save_mask=self._save_mask_to_project,
                detect_sky_fn=lambda *args, **kwargs: self.app.workflow.do_detect_sky(*args, **kwargs),
                refine_mask_fn=lambda *args, **kwargs: self.app.workflow.do_refine_mask(*args, **kwargs),
                enqueue_task=self._enqueue_task,
                get_post_result=lambda: (lambda gen=self._generation: lambda cb: self._post_result(gen, cb))(),
                get_result_guard=lambda: self._result_guard(self._generation),
                on_manual_edit=self._on_canvas_mask_brush_edited,
                on_detection_finished=on_detection_finished,
                sky_card=self.sky_card,
                get_device=lambda: DEFAULT_SKY_DETECTION_DEVICE if getattr(self._project, "use_gpu", True) else "cpu",
                get_detection_options=lambda: {
                    "model_path": self._project.auto_mask_path,
                    "foliage_protection": self._project.mask_foliage_protection,
                },
            )
            self.mask_controller.bind()
            self.connect_signal(self.sky_settings.export_training_requested, self.do_export_training_sky)
            self.connect_signal(self.sky_settings.contribute_requested, self.do_contribute_training_sky)
        if self.export_settings is not None:
            self.connect_signal(self.export_settings.export_training_requested, self.do_export_training_sky)
            self.connect_signal(self.export_settings.contribute_requested, self.do_contribute_training_sky)
        if self.btn_align_stars is not None:
            self.connect_signal(self.btn_align_stars.clicked, self.do_align_stars_action)
        if self.align_settings is not None:
            self.connect_signal(self.align_settings.settings_changed, self._on_alignment_settings_changed)
        if self.stack_settings is not None:
            self.connect_signal(self.stack_settings.settings_changed, self._on_stack_settings_changed)
        if self.stack_card is not None:
            self.connect_signal(self.stack_card.expanded, self._on_stack_card_expanded)
            if hasattr(self.stack_card, "before_after_toggled"):
                self.connect_signal(self.stack_card.before_after_toggled, self._on_stack_before_after)
        if self.btn_stack is not None:
            self.connect_signal(self.btn_stack.clicked, self.do_stack_action)
        if self.btn_compose is not None:
            self.connect_signal(self.btn_compose.clicked, self.do_compose_action)
        if self.tune_settings is not None:
            self.connect_signal(self.tune_settings.gradient_mask_toggled, self._on_gradient_mask_toggled)
            self.connect_signal(self.tune_settings.settings_changed, self._schedule_horizon_tuning)
        if self.tune_card is not None:
            self.connect_signal(self.tune_card.expanded, self._on_tune_card_expanded)
            if hasattr(self.tune_card, "before_after_toggled"):
                self.connect_signal(self.tune_card.before_after_toggled, self._on_tune_before_after)
        if self.btn_save_output is not None:
            self.connect_signal(self.btn_save_output.clicked, self.do_save_output_action)
        if self.btn_pipeline is not None:
            self.connect_signal(self.btn_pipeline.clicked, self.do_pipeline_action)

    # -------------------------------------------------------------------------
    # File Management
    # -------------------------------------------------------------------------

    def select_star_files(self) -> None:
        clear = self.confirm_clear_files(len(self.app.workflow.get_star_files()))
        file_names, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Star Images",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if file_names and hasattr(self.app.workflow, "add_star_files"):
            self.app.workflow.add_star_files(file_names, clear=clear)
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
        clear = self.confirm_clear_files(len(self.app.workflow.get_noise_files()))
        file_names, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Dark/Noise Frames",
            filter="Image Files (*.jpg *.jpeg *.tif *.tiff)",
        )
        if file_names and hasattr(self.app.workflow, "add_noise_files"):
            self.app.workflow.add_noise_files(file_names, clear=clear)
            self.reset_project_view()

    def remove_noise_file(self, file: File) -> None:
        if hasattr(self.app.workflow, "remove_noise_file"):
            self.app.workflow.remove_noise_file(file)
            self.reset_project_view()

    def reset_project_view(self) -> None:
        if not hasattr(self.app.workflow, "get_star_files"):
            return
        self.app.workflow.project.validate_cached_results()
        alignment_result = (
            self.last_align_result
            if (self._project is self.app.project and self.app.project.alignment_is_current())
            else None
        )
        self._generation += 1
        self._project = self.app.project
        self.last_align_result = alignment_result
        self.last_compositor = None
        final_output = getattr(self._project, "final_output_path", None)
        self._output_saved = bool(final_output and Path(final_output).is_file())
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

        self.has_manual_sky_corrections = bool(getattr(self._project, "has_manual_sky_corrections", False))

        if self.sky_settings is not None:
            self.sky_settings.set_from_project()
        if self.align_settings is not None:
            self.align_settings.set_from_project()
        if self.stack_settings is not None:
            self.stack_settings.set_from_project()
        if self.tune_settings is not None:
            self.tune_settings.set_from_project()

        self.update_ready_states()
        self._reset_preview_toggles()

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
            if (
                generation != self._generation
                or workflow.project is not self.app.project
                or revision != workflow.project.processing_revision
            ):
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
        if task_id == "exportSkyTraining":
            if message != "Cancelled":
                parent = self.shell if isinstance(self.shell, QWidget) else None
                QMessageBox.warning(parent, "Sky Training Export Failed", message)
            return
        settings = {
            "detectSky": self.sky_settings,
            "refineMask": self.sky_settings,
            "alignStars": self.align_settings,
            "stackDenoise": self.stack_settings,
            "composeHorizon": self.tune_settings,
            "exportDenoise": self.tune_settings,
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

    def _reset_preview_toggles(self, exclude: Optional[Any] = None) -> None:
        """Reset step before/after preview toggles to their default after state without emitting."""
        for card in (self.sky_card, self.stack_card, self.tune_card):
            if card is not None and card is not exclude and hasattr(card, "reset_before_after"):
                card.reset_before_after(emit=False)

    def _on_file_section_show_file(self, file: Optional[File]) -> None:
        self._reset_preview_toggles()
        self._cancel_horizon_overlay()
        self.show_file(file, preserve_view=True)

    def _focus_file_in_sections(self, file: Optional[File], *, expand: bool = True) -> None:
        if expand:
            signals = getSignals()
            if hasattr(signals, "focusFile"):
                signals.focusFile.emit(file)
            return
        for section in (self.star_files, self.noise_files, self.output_files):
            if section is not None and hasattr(section, "focus_file"):
                section.focus_file(file, expand=False)

    def show_file(
        self,
        file: Optional[File],
        preserve_view: Optional[bool] = None,
        expand_sections: bool = True,
    ) -> None:
        self._horizon_preview_id = None
        if hasattr(self.shell, "currentFile"):
            self.shell.currentFile = file
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFile(file, preserve_view=preserve_view)
            ref = self.app.workflow.get_reference_file() if hasattr(self.app, "workflow") else None
            if (
                file is not None
                and ref is not None
                and getattr(file, "path", None) == getattr(ref, "path", None)
                and self.mask_controller is not None
                and self.mask_controller.is_overlay_enabled()
            ):
                self.shell.canvas_main.set_mask_edit_mode(True)
            else:
                self.shell.canvas_main.set_mask_edit_mode(False)
        if hasattr(self.shell, "label_imageName") and self.shell.label_imageName is not None:
            self.shell.label_imageName.setText(file.basename if file is not None else "")
        self._focus_file_in_sections(file, expand=expand_sections)

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

        if self.sky_settings is not None:
            self.sky_settings.set_corrections_enabled(self.has_manual_sky_corrections)
        if self.export_settings is not None:
            self.export_settings.set_corrections_enabled(self.has_manual_sky_corrections)
        if self.export_card is not None:
            self.export_card.set_alert(self.has_manual_sky_corrections)

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
            canvas.set_denoise_mask(None)
            canvas.clear_horizon_overlay()
            canvas.set_gradient_mask_visible(False)
        if self.mask_controller is not None:
            self.mask_controller.teardown()
            self.mask_controller = None
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
            not self._disposed
            and worker is not None
            and worker.project is self.app.project
            and worker.generation == self._generation
            and request_id == latest_id
            and not worker.is_cancelled()
        )

    def _horizon_params(self) -> dict:
        vals = self.tune_settings.values() if self.tune_settings else vars(self._project)
        return {
            "blend": vals["horizon_blend_percent"],
            "blur_radius": vals["horizon_blur_radius"],
            "denoise_strength": vals["horizon_denoise_strength"],
            "denoise_enabled": vals["denoise_horizon_band"],
            "enable_corrections": vals["enable_horizon_corrections"],
            "color_denoise": vals["horizon_color_denoise_strength"],
            "value_denoise": vals["horizon_value_denoise_strength"],
        }

    def _cancel_horizon_overlay(self) -> None:
        """Stop pending live horizon overlay updates without cancelling final-output saves."""
        self._horizon_debounce_timer.stop()
        self._pending_horizon_params = None
        self._horizon_request_id += 1
        for worker in tuple(self._background_workers):
            if isinstance(worker, HorizonOverlayWorker):
                worker.cancel()

    def _has_pending_horizon_save(self) -> bool:
        return bool(
            self._horizon_debounce_timer.isActive()
            or self._horizon_save_debounce_timer.isActive()
            or self._final_save_worker is not None
            or self._pending_final_save
        )

    def _get_source_file(self) -> Optional[File]:
        if not hasattr(self.app, "workflow"):
            return None
        ref = self.app.workflow.get_reference_file() if hasattr(self.app.workflow, "get_reference_file") else None
        if ref is not None:
            return ref
        stars = self.app.workflow.get_star_files() if hasattr(self.app.workflow, "get_star_files") else []
        return stars[0] if stars else None

    def _show_source_before(self) -> None:
        """Display the clean input reference image without mask or horizon overlays."""
        source = self._get_source_file()
        if source is None:
            return
        self.show_file(source, preserve_view=True, expand_sections=False)
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            if hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                canvas.set_mask_edit_mode(False)
            canvas.set_gradient_mask_visible(False)

    def _stacked_composite_file(self) -> Optional[OutputFile]:
        for f in self.app.workflow.get_output_file_list():
            if f.operation == "Base Stack":
                return f
        return None

    def _existing_final_output_path(self) -> Optional[Path]:
        final_output = getattr(self._project, "final_output_path", None)
        if not final_output:
            return None
        candidate = Path(final_output)
        return candidate if candidate.is_file() else None

    def _set_active_file_metadata(self, file: Optional[File], *, expand_sections: bool = True) -> None:
        if hasattr(self.shell, "currentFile"):
            self.shell.currentFile = file
        if hasattr(self.shell, "label_imageName") and self.shell.label_imageName is not None:
            self.shell.label_imageName.setText(file.basename if file is not None else "")
        self._focus_file_in_sections(file, expand=expand_sections)

    def _show_stacked_composite(self) -> None:
        """Display the sky+ground stacked base composite without horizon tuning."""
        compositor = self.last_compositor
        if compositor is None:
            compositor = self._find_existing_compositor()
            if compositor is not None:
                self.last_compositor = compositor
        if compositor is not None:
            base_file = self._stacked_composite_file()
            canvas = getattr(self.shell, "canvas_main", None)
            if canvas is not None:
                has_pixmap = canvas.pixmap is not None and not canvas.pixmap.isNull()
                canvas.set_file_pixels(
                    base_file,
                    compositor.base_composite,
                    reset_zoom_and_position=not has_pixmap,
                    is_bgr=False,
                )
                canvas.set_mask_edit_mode(False)
                self._horizon_preview_id = id(compositor)
                if compositor.gradient_mask is not None:
                    canvas.set_gradient_mask(compositor.gradient_mask)
                self._resync_gradient_mask_visibility()
            self._set_active_file_metadata(base_file, expand_sections=False)

    def _show_final_composite(self) -> None:
        """Display the final horizon-tuned composite, using live tuning when uncached."""
        final_path = self._existing_final_output_path()
        if final_path is not None and not self._has_pending_horizon_save():
            final_file = OutputFile(basename=final_path.name, path=str(final_path), operation="Final Composite")
            self.show_file(final_file, preserve_view=True, expand_sections=False)
            self._resync_gradient_mask_visibility()
            return
        self._schedule_horizon_tuning(save=False)

    def _on_stack_card_expanded(self) -> None:
        self._reset_preview_toggles()
        self._cancel_horizon_overlay()
        if self.last_compositor is not None or self._has_existing_stacks():
            self._show_stacked_composite()

    def _on_stack_before_after(self, showing_before: bool) -> None:
        self._reset_preview_toggles(exclude=self.stack_card)
        self._cancel_horizon_overlay()
        if showing_before:
            self._show_source_before()
        else:
            self._show_stacked_composite()

    def _on_tune_card_expanded(self) -> None:
        self._reset_preview_toggles()
        self._show_final_composite()

    def _on_tune_before_after(self, showing_before: bool) -> None:
        self._reset_preview_toggles(exclude=self.tune_card)
        if showing_before:
            self._cancel_horizon_overlay()
            self._show_stacked_composite()
        else:
            self._show_final_composite()

    def _can_apply_horizon_patches(self) -> bool:
        if self.last_compositor is None:
            return False
        if self._horizon_preview_id is None or self._horizon_preview_id != id(self.last_compositor):
            return False
        if self.tune_card is not None and self.tune_card.is_showing_before():
            return False
        if self.stack_card is not None and (self.stack_card.is_expanded or self.stack_card.is_showing_before()):
            return False
        if self.sky_card is not None and self.sky_card.is_expanded:
            return False
        return True

    def _schedule_horizon_tuning(self, save: bool = True) -> None:
        if self._disposed:
            return
        if self.last_compositor is None:
            self.last_compositor = self._find_existing_compositor()
        if self.last_compositor is None:
            return
        self._reset_preview_toggles()
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None and self._horizon_preview_id != id(self.last_compositor):
            has_pixmap = canvas.pixmap is not None and not canvas.pixmap.isNull()
            canvas.clear_horizon_overlay()
            canvas.set_mask_edit_mode(False)
            canvas.setFromNumpyArray(
                self.last_compositor.base_composite,
                resetZoomAndPosition=not has_pixmap,
                is_bgr=False,
            )
            self._horizon_preview_id = id(self.last_compositor)
            if self.last_compositor.gradient_mask is not None:
                canvas.set_gradient_mask(self.last_compositor.gradient_mask)
            self._resync_gradient_mask_visibility()
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
            self.last_compositor,
            self._horizon_params(),
            project.get_output_dir() / f"{project.get_project_stem()}_final.tif",
            self._final_save_request_id,
            parent=self,
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

    def _on_final_save_finished(self, staged_path: Any, req_id: Any, legacy_req_id: Optional[int] = None) -> None:
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
            self.last_compositor,
            self._horizon_params(),
            self._horizon_request_id,
            parent=self,
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
        if (
            self._worker_is_current(worker, req_id, self._horizon_request_id)
            and patches is not None
            and self._can_apply_horizon_patches()
        ):
            canvas = getattr(self.shell, "canvas_main", None)
            if canvas is not None:
                canvas.set_horizon_patches(patches)

    def _on_background_error(self, message: str, req_id: int) -> None:
        worker = self.sender() or self._final_save_worker
        latest_id = (
            self._horizon_request_id
            if isinstance(worker, HorizonOverlayWorker)
            else self._final_save_request_id
        )
        if not self._worker_is_current(worker, req_id, latest_id):
            return
        if self.tune_settings is None:
            return
        err_msg = message if message.startswith("Failed:") else f"Failed: {message}"
        self._show_task_error("composeHorizon", err_msg)

    def _resync_gradient_mask_visibility(self) -> None:
        if self.tune_settings is not None:
            self._on_gradient_mask_toggled(self.tune_settings.ui.showGradientMask.isChecked())

    def _on_gradient_mask_toggled(self, checked: bool) -> None:
        if not hasattr(self.shell, "canvas_main") or self.shell.canvas_main is None:
            return
        if checked:
            mask = None
            if self.last_compositor is not None and getattr(self.last_compositor, "gradient_mask", None) is not None:
                mask = self.last_compositor.gradient_mask
            elif hasattr(self.app.workflow, "project") and getattr(
                self.app.workflow.project, "gradient_mask_path", None
            ):
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
            candidate = project.artifact_path("mask")
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
        sky_p = proj.artifact_path("sky_stack")
        ground_p = proj.artifact_path("ground_stack")
        try:
            from startrails.lib.util import imread
            from startrails.lib.denoise.stacking.horizon_compositor import HorizonCompositor

            sky_stack = imread(sky_p, to_rgb=True, as_float=True)
            ground_stack = imread(ground_p, to_rgb=True, as_float=True)
            h, w = sky_stack.shape[:2]

            mask = self._find_existing_mask()
            if mask is None:
                mask = np.ones((h, w), dtype=np.float32)

            grad_p = proj.artifact_path("gradient_mask")
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
                                cov = cv2.warpPerspective(
                                    np.ones((h, w), dtype=np.float32), H_mat, (w, h), flags=cv2.INTER_NEAREST
                                )
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
                feather_radius=DEFAULT_HORIZON_FEATHER_RADIUS,
                denoise_radius=cfg.horizon_denoise_radius,
                denoise_eps=cfg.horizon_denoise_eps,
            )
        except Exception as e:
            print(f"Could not construct compositor from disk stacks: {e}")
            return None

    def _get_project_mask_path(self) -> Path:
        proj = getattr(self.app.workflow, "project", None)
        if proj and hasattr(proj, "get_output_dir"):
            out_dir = proj.get_output_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            return proj.artifact_path("mask")
        ref = self.app.workflow.get_reference_file()
        if ref and getattr(ref, "path", None):
            p = Path(ref.path)
            return p.parent / f"{p.stem}.mask.png"
        return Path("projects/default.denoise/mask.png")

    def _on_mask_edit_toggled(self, enabled: bool) -> None:
        if self.mask_controller is not None:
            self.mask_controller.on_mask_edit_toggled(enabled)

    def _apply_mask_to_canvas_and_project(self, mask: np.ndarray) -> None:
        if self.mask_controller is not None:
            self.mask_controller.apply_mask_to_canvas(mask)
        self._save_mask_to_project(mask)

    def _on_canvas_mask_brush_edited(self) -> None:
        self.has_manual_sky_corrections = True
        if hasattr(self.app.workflow, "project") and self.app.workflow.project is not None:
            self.app.workflow.project.has_manual_sky_corrections = True
        self.update_ready_states()

    def _on_detection_finished(self, mask: np.ndarray) -> None:
        self.has_manual_sky_corrections = False
        if hasattr(self.app.workflow, "project") and self.app.workflow.project is not None:
            self.app.workflow.project.has_manual_sky_corrections = False
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
        if self.mask_controller is not None:
            self.mask_controller.do_detect_sky()

    def do_refine_mask_action(self) -> None:
        if self.mask_controller is not None:
            self.mask_controller.do_refine_mask()

    def do_clear_mask_action(self) -> None:
        if self.mask_controller is not None:
            self.mask_controller.do_clear_mask()
        self.update_ready_states()

    def do_full_frame_mask_action(self) -> None:
        if self.mask_controller is not None:
            self.mask_controller.do_full_frame_mask()
        self.update_ready_states()

    def do_export_training_sky(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return

        reply = QMessageBox.question(
            None,
            "Export Sky Training Data",
            "This process will downscale the reference image and your manual sky mask by half "
            "into 8-bit training data ('image.jpg' and 'mask.png') to protect privacy and reduce file size. "
            "You can share these samples with the project or use them to train your own models.\n\nContinue?",
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        folder = QFileDialog.getExistingDirectory(caption="Choose folder to save sky training data")
        if not folder:
            return

        if any((Path(folder) / name).exists() for name in ("image.jpg", "mask.png")):
            parent = self.shell if isinstance(self.shell, QWidget) else None
            replace = QMessageBox.question(
                parent,
                "Replace Sky Training Files?",
                "This folder already contains sky training files. Replace image.jpg and mask.png?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if replace != QMessageBox.StandardButton.Yes:
                return

        current_mask = None
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            current_mask = self.shell.canvas_main.get_denoise_mask()
        if current_mask is None:
            current_mask = self._find_existing_mask()
        if current_mask is None:
            return

        mask_to_export = current_mask.copy()

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Exporting Sky Training Data:",
            )
            self.app.workflow.doExportTrainingSky(folder, progress_updater.tick, mask=mask_to_export)

        self._enqueue_task(
            "exportSkyTraining",
            "Export Sky Training Data",
            2,
            "Exporting sky training image and mask...",
            work,
        )

    def do_contribute_training_sky(self) -> None:
        ref = self.app.workflow.get_reference_file()
        if ref is None:
            return

        current_mask = None
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            current_mask = self.shell.canvas_main.get_denoise_mask()
        if current_mask is None:
            current_mask = self._find_existing_mask()
        if current_mask is None:
            return

        from startrails.ui.contribute_dialog import ContributeCorrectionsDialog

        parent = self.shell if isinstance(self.shell, QWidget) else None
        info_text = (
            "Contribute your sky mask corrections to help improve sky detection models. "
            "What will be shared?\n"
            "* A downscaled version of the reference image. (50%, 8-bit)\n"
            "* Your corrected sky mask.\n\n"
            "Submissions are uploaded and reviewed by a human for inclusion in the next training dataset."
        )
        dialog = ContributeCorrectionsDialog(
            title="Contribute Sky Mask Corrections",
            info_text=info_text,
            parent=parent,
        )
        if dialog.exec() != ContributeCorrectionsDialog.DialogCode.Accepted:
            return

        email, comments = dialog.values()
        mask_to_export = current_mask.copy()
        generation = self._generation

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Contributing Sky Mask Corrections:",
            )
            try:
                receipt = self.app.workflow.doContributeTrainingSky(
                    progress_updater.tick,
                    user_email=email,
                    user_comments=comments,
                    mask=mask_to_export,
                )
                self._post_result(generation, lambda result=receipt: self._notify_contribution_result(result, None))
            except Exception as err:
                self._post_result(generation, lambda error=err: self._notify_contribution_result(None, error))

        self._enqueue_task(
            "contributeSkyTraining",
            "Contribute Sky Training Data",
            2,
            "Submitting sky training data...",
            work,
        )

    def _notify_contribution_result(self, receipt: dict | None, error: Exception | None):
        shell = self.shell if isinstance(self.shell, QWidget) else None
        if error is not None:
            QMessageBox.warning(
                shell,
                "Contribution Failed",
                f"Could not submit corrections:\n\n{error}",
            )
        elif receipt is not None:
            receipt_dict = receipt if isinstance(receipt, dict) else {}
            QMessageBox.information(
                shell,
                "Contribution Accepted",
                f"Thank you for contributing to StarTrails!\n\n"
                f"Your submission has been accepted for review.\n\n"
                f"Submission ID: {receipt_dict.get('submission_id', 'N/A')}\n"
                f"Files: {receipt_dict.get('file_count', 0)}\n"
                f"Size: {receipt_dict.get('size_bytes', 0):,} bytes",
            )

    doExportTrainingSky = do_export_training_sky
    doContributeTrainingSky = do_contribute_training_sky

    def do_align_stars_action(self) -> None:
        stars = self.app.workflow.get_star_files()
        if not stars:
            return
        config_snapshot = self._snapshot_config("alignStars")
        if config_snapshot is None:
            return

        vals = self.align_settings.values() if self.align_settings else vars(config_snapshot)

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
            cfg.use_gpu = vals["use_gpu"]

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

        vals = self.stack_settings.values() if self.stack_settings else vars(config_snapshot)
        has_alignment = self.app.workflow.has_cached_alignment(config_snapshot)
        needs_alignment = not has_alignment
        n_stars = len(stars)
        total_stack_steps = n_stars * 4 + 1
        total_steps = (n_stars + total_stack_steps) if needs_alignment else total_stack_steps

        prepare_description = "Aligning star frames..."
        generation = self._generation

        def work():
            cfg = config_snapshot
            cfg.stack_method = vals["stack_method"]
            cfg.sigma_clip_threshold = vals["sigma_clip_threshold"]
            cfg.sigma_clip_iterations = vals["sigma_clip_iterations"]
            cfg.compress_intermediate_tiffs = vals["compress_intermediate_tiffs"]
            cfg.use_gpu = vals["use_gpu"]

            if needs_alignment:
                align_updater = ProgressBarUpdater(
                    getattr(self.shell, "progressBar", None),
                    getattr(self.shell, "label_progressBar", None),
                    total=len(stars),
                    desc=prepare_description,
                    result_guard=self._result_guard(generation),
                )

                align_result = self.app.workflow.do_align_stars(
                    config=cfg,
                    warp_frames=False,
                    progress_bar=align_updater.tick,
                )
                if align_result is None:
                    return
                self.last_align_result = align_result
                if self.align_card is not None:
                    self._post_result(generation, lambda: self.align_card.setStatus("done"))
                if self.star_files is not None:
                    self._post_result(generation, lambda: self.star_files.set_files(self.app.workflow.get_star_files()))

            actual_stack_steps = n_stars * 4 + 1
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=actual_stack_steps,
                desc="Stacking sky and ground frames...",
                result_guard=self._result_guard(generation),
            )

            compositor = self.app.workflow.do_stack_denoise(
                config=cfg,
                sky_mask=self.last_align_result.sky_mask if self.last_align_result else None,
                progress_bar=progress_updater.tick,
            )

            if compositor is None:
                return

            def on_stack_done():
                self.last_compositor = compositor
                self._output_saved = False
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
                        self._horizon_preview_id = None
                        if hasattr(self.shell, "currentFile"):
                            self.shell.currentFile = comp_file
                        if hasattr(self.shell, "label_imageName") and self.shell.label_imageName is not None:
                            self.shell.label_imageName.setText(comp_file.basename)
                        if self.output_files is not None:
                            self.output_files.setCurrentFile(comp_file)
                        signals = getSignals()
                        if hasattr(signals, "focusFile"):
                            signals.focusFile.emit(comp_file)

                    if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
                        self.shell.canvas_main.set_file_pixels(
                            comp_file,
                            compositor.base_composite,
                            reset_zoom_and_position=False,
                            is_bgr=False,
                        )
                        self._horizon_preview_id = id(compositor)
                        if compositor.gradient_mask is not None:
                            self.shell.canvas_main.set_gradient_mask(compositor.gradient_mask)
                self._reset_preview_toggles()
                if self.stack_card is not None:
                    self.stack_card.setStatus("done")
                self.update_ready_states()
                self._schedule_horizon_tuning(save=True)

            self._post_result(generation, on_stack_done)

        self._enqueue_task("stackDenoise", "Stack for Denoise", total_steps, "Stacking base frames...", work)

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
        generation = self._generation
        self._cancel_background_jobs()

        def work():
            updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=2,
                desc="Compositing and saving final image...",
                result_guard=self._result_guard(generation),
            )
            result = workflow.do_compose_horizon(
                compositor,
                config=config,
                progress_bar=updater.tick,
            )
            if result is None:
                return

            def publish():
                self._reset_preview_toggles()
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
            None,
            "Save Final Image",
            "final_denoise.tif",
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
                if not out_path or not Path(out_path).is_file():
                    return
                self._reset_preview_toggles()
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
DenoiseView.noiseFiles = property(
    lambda self: self.noise_files, lambda self, value: setattr(self, "noise_files", value)
)
DenoiseView.outputFiles = property(
    lambda self: self.output_files, lambda self, value: setattr(self, "output_files", value)
)
DenoiseView.skySettings = property(
    lambda self: self.sky_settings, lambda self, value: setattr(self, "sky_settings", value)
)
DenoiseView.alignSettings = property(
    lambda self: self.align_settings, lambda self, value: setattr(self, "align_settings", value)
)
DenoiseView.stackSettings = property(
    lambda self: self.stack_settings, lambda self, value: setattr(self, "stack_settings", value)
)
DenoiseView.tuneSettings = property(
    lambda self: self.tune_settings, lambda self, value: setattr(self, "tune_settings", value)
)
DenoiseView.skyCard = property(lambda self: self.sky_card, lambda self, value: setattr(self, "sky_card", value))
DenoiseView.alignCard = property(lambda self: self.align_card, lambda self, value: setattr(self, "align_card", value))
DenoiseView.stackCard = property(lambda self: self.stack_card, lambda self, value: setattr(self, "stack_card", value))
DenoiseView.tuneCard = property(lambda self: self.tune_card, lambda self, value: setattr(self, "tune_card", value))
DenoiseView.pushButton_newProject = property(
    lambda self: self.new_project_button, lambda self, value: setattr(self, "new_project_button", value)
)
DenoiseView.pushButton_openProject = property(
    lambda self: self.open_project_button, lambda self, value: setattr(self, "open_project_button", value)
)
DenoiseView.exportSettings = property(
    lambda self: self.export_settings, lambda self, value: setattr(self, "export_settings", value)
)
DenoiseView.exportCard = property(
    lambda self: self.export_card, lambda self, value: setattr(self, "export_card", value)
)
DenoiseView.pushButton_contribute = property(
    lambda self: (
        getattr(self.export_settings.ui, "contribute", None)
        if self.export_settings is not None and hasattr(self.export_settings, "ui")
        else None
    )
)
DenoiseView.pushButton_exportTraining = property(
    lambda self: (
        getattr(self.export_settings.ui, "training", None)
        if self.export_settings is not None and hasattr(self.export_settings, "ui")
        else None
    )
)
