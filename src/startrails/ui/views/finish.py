"""Finish mode view controller managing the sidebar and canvas interaction."""

from __future__ import annotations

from concurrent.futures import CancelledError
from dataclasses import replace
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from PySide6.QtCore import QSignalBlocker, QTimer
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from startrails.lib.denoise.defaults import DEFAULT_SKY_DETECTION_DEVICE
from startrails.lib.file import File, OutputFile
from startrails.lib.finish.defaults import (
    DEFAULT_BLEND_MODE,
    DEFAULT_DENOISE_SCOPE,
    DEFAULT_DENOISE_STRENGTH_PERCENT,
    DEFAULT_DETAIL_AMOUNT_PERCENT,
    DEFAULT_GLOW_STAR_COUNT,
    DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT,
    DEFAULT_ROUND_STARS_AMOUNT_PERCENT,
    DEFAULT_ROUND_STARS_ENABLED,
    DEFAULT_STAR_AMOUNT_PERCENT,
    DEFAULT_STAR_COUNT_CUTOFF,
    DEFAULT_STAR_GLOW_AMOUNT_PERCENT,
    DEFAULT_STAR_GLOW_ENABLED,
    DEFAULT_STAR_GLOW_RADIUS_PX,
    DEFAULT_STRUCTURE_AMOUNT_PERCENT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_FINISHED_STARS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
)
from startrails.lib.project_finish import FinishProject
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.sidebar_finish import SidebarFinish
from startrails.ui.sky_mask_controller import SkyMaskController
from startrails.ui.starnet_dialog import StarNetSetupDialog, StarNetTermsDialog, choose_existing_starnet
from startrails.ui.views.base import ModeView
from startrails.workflow.finish import SEPARATION_PROGRESS_TOTAL

if TYPE_CHECKING:
    from startrails.app import App


_SOURCE_IMAGE_FILTER = (
    "Supported Images (*.jpg *.jpeg *.tif *.tiff);;TIFF (*.tif *.tiff);;JPEG (*.jpg *.jpeg);;All Files (*)"
)

logger = logging.getLogger(__name__)


class FinishView(ModeView):
    """View controller managing the Finish sidebar, file sections, and workflow actions."""

    mode_name: str = "finish"

    def __init__(self, app: App, shell: Any):
        super().__init__(app, shell)
        self._project: FinishProject = app.project
        self.sidebar: Optional[SidebarFinish] = None
        self._displayed_source_id: Optional[str] = None
        self._generation: int = 0
        self._disposed: bool = False
        self.mask_controller: Optional[SkyMaskController] = None
        self._denoise_timer: Optional[QTimer] = None
        self._stars_timer: Optional[QTimer] = None
        self._prepare_timer: Optional[QTimer] = None
        self._is_comparing: bool = False
        self._pending_stars_action: str = "none"

    def build_sidebar(self, parent: QWidget) -> QWidget:
        """Construct and return the Finish mode sidebar widget."""
        self.sidebar = SidebarFinish(parent, app=self.app)
        self.sidebar_widget = self.sidebar
        self.inputFiles = self.sidebar.inputFiles
        self.outputFiles = self.sidebar.outputFiles
        self.pushButton_newProject = self.sidebar.pushButton_newProject
        self.pushButton_openProject = self.sidebar.pushButton_openProject
        return self.sidebar

    def bind(self) -> None:
        """Connect UI signals, listeners, and workflow actions."""
        if self.sidebar is None:
            return

        self.connect_signal(self.sidebar.btn_save_output.clicked, self.on_save_output)

        self.connect_signal(self.sidebar.inputFiles.addRequested, self.on_import_source)
        self.connect_signal(self.sidebar.inputFiles.showFile, self._on_file_section_show_file)
        self.connect_signal(self.sidebar.inputFiles.removeFile, self.on_remove_source)
        self.connect_signal(self.sidebar.outputFiles.showFile, self._on_file_section_show_file)

        if hasattr(self.shell, "doCreateNewFinishProject"):
            self.connect_signal(self.sidebar.pushButton_newProject.clicked, self.shell.doCreateNewFinishProject)
        if hasattr(self.shell, "doOpenFinishProject"):
            self.connect_signal(self.sidebar.pushButton_openProject.clicked, self.shell.doOpenFinishProject)

        # Wire reusable sky masking controller
        if hasattr(self.sidebar, "skySettings"):
            self.connect_signal(self.sidebar.skySettings.settings_changed, self.app.workflow.save_project)
            self.mask_controller = SkyMaskController(
                shell=self.shell,
                settings_widget=self.sidebar.skySettings,
                get_source_image=lambda: self._project.source_file if self._project.source_is_current() else None,
                show_source_image=lambda: self.showFile(self._project.source_file),
                get_saved_mask=self.app.workflow.get_current_mask,
                save_mask=self._save_mask_to_project,
                detect_sky_fn=self.app.workflow.do_detect_sky,
                refine_mask_fn=self.app.workflow.do_refine_mask,
                enqueue_task=self._enqueue_task,
                get_post_result=self._get_post_result,
                get_result_guard=self._result_guard,
                on_manual_edit=self._on_manual_mask_edit,
                on_detection_finished=self._on_mask_detection_finished,
                sky_card=self.sidebar.skyCard,
                get_device=lambda: DEFAULT_SKY_DETECTION_DEVICE,
            )
            self.mask_controller.bind()

        if hasattr(self.sidebar, "separateSettings"):
            self.connect_signal(self.sidebar.separateSettings.setup_requested, self.on_setup_starnet)
            self.connect_signal(self.sidebar.separateSettings.browse_requested, self.on_browse_starnet)
            self.connect_signal(self.sidebar.separateSettings.repair_requested, self.on_repair_starnet)
            self.connect_signal(self.sidebar.separateSettings.change_requested, self.on_browse_starnet)
            self.connect_signal(self.sidebar.separateSettings.run_separation_requested, self.on_run_separation)
            self.connect_signal(self.sidebar.separateSettings.stride_changed, self.on_starnet_stride_changed)

        if hasattr(self.sidebar, "starlessSettings"):
            self.connect_signal(self.sidebar.starlessSettings.run_denoise_requested, self.on_run_denoise)
            self.connect_signal(
                self.sidebar.starlessSettings.denoise_strength_changed, self.on_denoise_strength_changed
            )
            self.connect_signal(self.sidebar.starlessSettings.denoise_scope_changed, self.on_denoise_scope_changed)
            self.connect_signal(
                self.sidebar.starlessSettings.structure_amount_changed, self.on_structure_amount_changed
            )
            self.connect_signal(self.sidebar.starlessSettings.detail_amount_changed, self.on_detail_amount_changed)
            self.connect_signal(self.sidebar.starlessSettings.reset_requested, self.on_reset_starless)

        if hasattr(self.sidebar, "starsSettings"):
            self.connect_signal(self.sidebar.starsSettings.star_count_cutoff_changed, self.on_star_count_cutoff_changed)
            self.connect_signal(
                self.sidebar.starsSettings.round_stars_enabled_changed, self.on_round_stars_enabled_changed
            )
            self.connect_signal(
                self.sidebar.starsSettings.round_stars_amount_changed, self.on_round_stars_amount_changed
            )
            self.connect_signal(self.sidebar.starsSettings.star_glow_enabled_changed, self.on_star_glow_enabled_changed)
            self.connect_signal(self.sidebar.starsSettings.glow_star_count_changed, self.on_glow_star_count_changed)
            self.connect_signal(self.sidebar.starsSettings.star_glow_amount_changed, self.on_star_glow_amount_changed)
            self.connect_signal(
                self.sidebar.starsSettings.star_glow_radius_px_changed, self.on_star_glow_radius_px_changed
            )
            self.connect_signal(self.sidebar.starsSettings.reset_requested, self.on_reset_stars)
            self.connect_signal(self.sidebar.starsSettings.preview_layer_changed, self.on_stars_preview_layer_changed)
            self.connect_signal(self.sidebar.starsSettings.compare_pressed, self.on_compare_pressed)
            self.connect_signal(self.sidebar.starsSettings.compare_released, self.on_compare_released)

        if hasattr(self.sidebar, "recombineSettings"):
            self.connect_signal(self.sidebar.recombineSettings.star_amount_changed, self.on_star_amount_changed)
            self.connect_signal(self.sidebar.recombineSettings.blend_mode_changed, self.on_blend_mode_changed)
            self.connect_signal(
                self.sidebar.recombineSettings.original_stars_amount_changed, self.on_original_stars_amount_changed
            )
            self.connect_signal(
                self.sidebar.recombineSettings.original_stars_blend_mode_changed,
                self.on_original_stars_blend_mode_changed,
            )

    def teardown(self) -> None:
        """Disconnect signals and clean up canvas and mask controller state."""
        self._disposed = True
        self._generation += 1
        if self._denoise_timer is not None:
            self._denoise_timer.stop()
            self._denoise_timer = None
        if self._stars_timer is not None:
            self._stars_timer.stop()
            self._stars_timer = None
        if self._prepare_timer is not None:
            self._prepare_timer.stop()
            self._prepare_timer = None
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            canvas.set_mask_edit_mode(False)
            canvas.set_denoise_mask(None)
        if self.mask_controller is not None:
            self.mask_controller.teardown()
            self.mask_controller = None
        super().teardown()

    def _save_mask_to_project(self, mask: Any) -> None:
        self.app.workflow.save_mask(mask)
        self.sidebar.inputFiles.set_files(self.app.workflow.getInputFileList())
        self.sidebar.outputFiles.set_files(self.app.workflow.get_output_file_list())
        self.updateReadyStates()

    def _on_manual_mask_edit(self) -> None:
        self._project.has_manual_sky_corrections = True
        self.updateReadyStates()

    def _on_mask_detection_finished(self, mask: Any) -> None:
        self._project.has_manual_sky_corrections = False
        self.updateReadyStates()

    def _enqueue_task(self, task_id: str, title: str, total: int, desc: str, work: Callable) -> bool:
        workflow = self.app.workflow
        guard = self._result_guard()
        project = self._project
        generation = self._generation
        revision = project.processing_revision
        retry_preview = {
            "finish_denoise_preview": self._debounce_denoise_preview,
            "finish_stars_preview": self._debounce_stars_preview,
            "finish_stars_prepare": self._debounce_star_endpoint_preparation,
        }.get(task_id)

        def retry_if_stale():
            if (
                not self._disposed
                and generation == self._generation
                and project is self.app.project
                and revision != project.processing_revision
                and project.source_is_current()
            ):
                retry_preview()

        def run():
            try:
                if not guard():
                    return
                with workflow.operation_session():
                    work()
            except CancelledError:
                self._post_result(guard, lambda: self._show_task_error(task_id, "Cancelled"))
            except Exception as error:
                message = str(error)
                self._post_result(guard, lambda: self._show_task_error(task_id, f"Failed: {message}"))
            finally:
                # Either finishing card can stale the other card's queued or
                # running preview. Retain that pending edit as well as the edit
                # that caused the revision change; retries remain coalesced.
                if retry_preview is not None:
                    QTimer.singleShot(0, self.shell, retry_if_stale)

        return self.shell.enqueue_task(task_id, title, total, desc, run)

    def _result_guard(self) -> Callable[[], bool]:
        project = self._project
        generation = self._generation
        revision = project.processing_revision
        return lambda: (
            not self._disposed
            and generation == self._generation
            and project is self.app.project
            and revision == project.processing_revision
            and project.source_is_current()
        )

    def _get_post_result(self) -> Callable[[Callable], None]:
        guard = self._result_guard()
        return lambda callback: self._post_result(guard, callback)

    def _post_result(self, guard: Callable[[], bool], callback: Callable) -> None:
        def deliver():
            if guard():
                callback()

        QTimer.singleShot(0, self.shell, deliver)

    def _show_task_error(self, task_id: str, message: str) -> None:
        if task_id == "finish_separation":
            if self.sidebar is not None and hasattr(self.sidebar, "separateSettings"):
                self.sidebar.separateSettings.lbl_status.setText(message)
                self.sidebar.separateSettings.lbl_status.show()
        elif task_id in ("finish_denoise", "finish_denoise_preview"):
            if self.sidebar is not None and hasattr(self.sidebar, "starlessSettings"):
                self.sidebar.starlessSettings.lbl_status.setText(message)
                self.sidebar.starlessSettings.lbl_status.show()
        elif task_id in ("finish_stars", "finish_stars_preview", "finish_stars_prepare", "finish_save_export"):
            self._show_stars_status(message, is_error=True)
        elif self.sidebar is not None and hasattr(self.sidebar, "skySettings"):
            self.sidebar.skySettings.ui.error.setText(message)
            self.sidebar.skySettings.ui.error.show()

    def resetProjectView(self) -> None:  # noqa: N802 - ModeView interface
        """Reset sidebar view state when a new or opened project is active."""
        self._generation += 1
        if self._denoise_timer is not None and self._denoise_timer.isActive():
            self._denoise_timer.stop()
        if self._stars_timer is not None and self._stars_timer.isActive():
            self._stars_timer.stop()
        self._project = self.app.project
        if not isinstance(self._project, FinishProject):
            return
        dimensions = None
        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            if self._project.source_is_current():
                source = self._project.source_file
                canvas.setFile(source, reload=source.sourceId != self._displayed_source_id)
                self._displayed_source_id = source.sourceId
                if canvas.pixmap is not None and not canvas.pixmap.isNull():
                    dimensions = (canvas.pixmap.width(), canvas.pixmap.height())

                existing_mask = self.app.workflow.get_current_mask()
                if existing_mask is not None:
                    canvas.set_denoise_mask(existing_mask)
                    is_expanded = bool(self.sidebar and self.sidebar.skyCard.is_expanded)
                    canvas.set_mask_edit_mode(is_expanded)
                    if self.sidebar and hasattr(self.sidebar, "skySettings"):
                        with QSignalBlocker(self.sidebar.skySettings.ui.showMaskOverlay):
                            self.sidebar.skySettings.ui.showMaskOverlay.setChecked(is_expanded)
                else:
                    canvas.set_denoise_mask(None)
                    canvas.set_mask_edit_mode(False)
                    if self.sidebar and hasattr(self.sidebar, "skySettings"):
                        with QSignalBlocker(self.sidebar.skySettings.ui.showMaskOverlay):
                            self.sidebar.skySettings.ui.showMaskOverlay.setChecked(False)
            else:
                canvas.setFile(None)
                canvas.set_denoise_mask(None)
                canvas.set_mask_edit_mode(False)
                self._displayed_source_id = None
                if self.sidebar and hasattr(self.sidebar, "skySettings"):
                    with QSignalBlocker(self.sidebar.skySettings.ui.showMaskOverlay):
                        self.sidebar.skySettings.ui.showMaskOverlay.setChecked(False)

        if self.sidebar is not None:
            self.sidebar.update_from_project(self._project, dimensions)
            self.sidebar.inputFiles.set_files(self.app.workflow.getInputFileList())
            self.sidebar.outputFiles.set_files(self.app.workflow.get_output_file_list())
            if self._project.source_is_current() and self._project.source_file is not None:
                self.sidebar.inputFiles.focus_file(self._project.source_file)
            if hasattr(self.sidebar, "skySettings"):
                self.sidebar.skySettings.set_from_project(self._project)

        self._is_comparing = False
        self.updateReadyStates()
        self._update_cutoff_display()

        if self._project.source_is_current() and self._project.current_artifact_path(ROLE_SEPARATED_STARS) is not None:
            workflow = getattr(self.app, "workflow", None)
            if workflow is not None and hasattr(workflow, "get_star_preview_status"):
                status = workflow.get_star_preview_status()
                if status in ("cold", "stale"):
                    self._show_stars_status("Preparing star finish preview...", is_error=False)
                    self._enqueue_star_endpoint_preparation()

    def _enqueue_star_endpoint_preparation(self) -> None:
        """Enqueue background preparation of persisted star catalog and preview endpoints on reopen."""
        if not self._result_guard()():
            return
        if not self._project or not self._project.source_is_current():
            return
        if self._project.current_artifact_path(ROLE_SEPARATED_STARS) is None:
            return

        workflow = getattr(self.app, "workflow", None)
        if workflow is None or not hasattr(workflow, "prepare_star_endpoints"):
            return

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()

        def on_done():
            self.updateReadyStates()
            self._update_cutoff_display()
            canvas = getattr(self.shell, "canvas_main", None)
            if canvas is not None and hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                return
            self._render_immediate_preview()

        def on_cancelled():
            pass

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Preparing star finishing...",
                result_guard=result_guard,
            )
            state = workflow.prepare_star_endpoints(progress_bar=progress_updater.tick)
            if state is not None:
                deliver_result(on_done)
            else:
                deliver_result(on_cancelled)

        accepted = self._enqueue_task(
            task_id="finish_stars_prepare",
            title="Prepare Stars",
            total=100,
            desc="Preparing star finishing...",
            work=work,
        )
        if not accepted:
            self._debounce_star_endpoint_preparation()

    def _debounce_star_endpoint_preparation(self) -> None:
        """Debounce star endpoint preparation retry."""
        if self._disposed or self.sidebar is None:
            return
        if self._prepare_timer is None:
            self._prepare_timer = QTimer(self.sidebar)
            self._prepare_timer.setSingleShot(True)
            self._prepare_timer.timeout.connect(self._enqueue_star_endpoint_preparation)
        self._prepare_timer.start(100)

    def _on_file_section_show_file(self, file: Optional[File]) -> None:
        """Show a file selected from the Input or Output FileSection, preserving zoom/pan."""
        self.showFile(file, preserve_view=True)

    def showFile(  # noqa: N802 - ModeView interface
        self,
        file: Optional[File],
        preserve_view: Optional[bool] = None,
        reload: bool = False,
    ) -> None:
        """Handle preview display on the canvas.

        preserve_view=None keeps the canvas's same-file behavior; True keeps
        zoom/pan while switching files. reload re-reads pixels, which is
        required after the displayed file has been rewritten.
        """
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFile(file, reload=reload, preserve_view=preserve_view)

    def updateReadyStates(self, _=None) -> None:  # noqa: N802 - ModeView interface
        """Update file sections and step prerequisites based on project readiness."""
        if self.sidebar is not None and isinstance(self._project, FinishProject):
            self.app.workflow.invalidate_if_starnet_changed()
            if hasattr(self.app.workflow, "invalidate_if_graxpert_changed"):
                self.app.workflow.invalidate_if_graxpert_changed()
            if hasattr(self.app.workflow, "invalidate_if_starless_filter_changed"):
                self.app.workflow.invalidate_if_starless_filter_changed()
            if hasattr(self.app.workflow, "invalidate_if_star_effects_changed"):
                self.app.workflow.invalidate_if_star_effects_changed()
            self.sidebar.inputFiles.set_files(self.app.workflow.getInputFileList())
            self.sidebar.outputFiles.set_files(self.app.workflow.get_output_file_list())
            self.sidebar.update_prerequisites(self._project)
            self._update_cutoff_display()
            # If the canvas is showing a file that is no longer available, fall
            # back to the source so the user isn't left on a stale preview.
            canvas = getattr(self.shell, "canvas_main", None)
            current_file = getattr(canvas, "file", None) if canvas is not None else None
            if current_file is not None:
                current_path = getattr(current_file, "path", None)
                available = {
                    getattr(f, "path", None)
                    for f in self.sidebar.inputFiles.model.files + self.sidebar.outputFiles.model.files
                }
                if current_path not in available and self._project.source_is_current():
                    self.showFile(self._project.source_file, preserve_view=True)

    def on_import_source(self) -> None:
        """Prompt user for a source image and import/replace it in the project."""
        has_source = self._project.source_file is not None
        title = "Replace Source Image" if has_source else "Import Source Image"
        start_dir = str(self._project.get_output_dir().parent)
        if has_source and self._project.source_file.path:
            start_dir = str(Path(self._project.source_file.path).parent)
        fileName, _ = QFileDialog.getOpenFileName(
            self.sidebar,
            title,
            dir=start_dir,
            filter=_SOURCE_IMAGE_FILTER,
        )
        if fileName:
            try:
                self.app.workflow.do_import_source(fileName)
                self.resetProjectView()
            except Exception as e:
                QMessageBox.critical(self.sidebar, "Import Error", f"Failed to import source image:\n{e}")

    def on_remove_source(self, file: File) -> None:
        """Remove the current source image from the project via the workflow API."""
        if not self._project.source_file or getattr(file, "path", None) != self._project.source_file.path:
            return
        reply = QMessageBox.question(
            self.sidebar,
            "Remove Source Image",
            "Remove the source image from this project?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self.app.workflow.do_clear_source()
            self.resetProjectView()
        except Exception as e:
            QMessageBox.critical(self.sidebar, "Remove Error", f"Failed to remove source image:\n{e}")

    def on_save_output(self) -> None:
        """Export composite to destination path, recombining if needed in worker."""
        if not getattr(self._project, "source_file", None):
            QMessageBox.information(self.sidebar, "Save Image", "Please import a source image first.")
            return
        if not (
            self._project.current_artifact_path(ROLE_SEPARATED_STARLESS)
            and self._project.current_artifact_path(ROLE_SEPARATED_STARS)
        ):
            QMessageBox.information(
                self.sidebar,
                "Save Image",
                "Separate stars before saving a finished image.",
            )
            return

        default_export = self._project.get_default_export_path()
        filter_str = f"Image (*{default_export.suffix});;All Files (*)"
        fileName, _ = QFileDialog.getSaveFileName(
            self.sidebar,
            "Save Finished Image",
            str(default_export),
            filter_str,
        )
        if not fileName:
            return

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done(out_path: Any):
            self.sidebar.outputFiles.set_files(self.app.workflow.get_output_file_list())
            self.updateReadyStates()
            QMessageBox.information(self.sidebar, "Image Saved", f"Successfully saved:\n{out_path}")

        def on_cancelled():
            pass

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Saving finished image...",
                result_guard=result_guard,
            )
            if self._project.current_artifact_path(ROLE_FINISHED_COMPOSITE) is None:
                recombine_res = workflow.do_recombine(progress_bar=progress_updater.tick)
                if recombine_res is None:
                    deliver_result(on_cancelled)
                    return

            out = workflow.do_export_composite(output_path=fileName)
            if out is not None:
                deliver_result(lambda: on_done(out))
            else:
                deliver_result(on_cancelled)

        self._enqueue_task(
            task_id="finish_save_export",
            title="Saving Image",
            total=100,
            desc="Saving finished image...",
            work=work,
        )

    def on_run_separation(self) -> None:
        """Execute star separation workflow in background task."""
        if not self._project or not self._project.source_is_current():
            QMessageBox.warning(self.sidebar, "Source Required", "Please import a source image first.")
            return
        if self.app.workflow.get_current_mask() is None:
            QMessageBox.warning(
                self.sidebar, "Sky Mask Required", "Please define a sky region before separating stars."
            )
            return

        stride = self.sidebar.separateSettings.get_stride()
        if hasattr(self.sidebar.separateSettings, "lbl_status"):
            self.sidebar.separateSettings.lbl_status.hide()

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done():
            # Same-project completion: refresh file sections and prerequisites
            # without resetting the full project view (which would lose zoom/pan).
            self.updateReadyStates()
            p = self._project.current_artifact_path(ROLE_SEPARATED_STARLESS)
            if p:
                starless_file = OutputFile(basename=p.name, path=str(p), operation="Starless")
                self.sidebar.outputFiles.focus_file(starless_file)
                # The job just rewrote this file; re-read its pixels.
                self.showFile(starless_file, preserve_view=True, reload=True)
            # Prepare star finish endpoints outside UI so controls are ready
            self._pending_stars_action = "effects"
            self._debounce_stars_preview()

        def on_cancelled():
            self._show_task_error("finish_separation", "Cancelled")

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=SEPARATION_PROGRESS_TOTAL,
                desc="Separating stars from sky background...",
                result_guard=result_guard,
            )
            result = workflow.do_separate_stars(stride=stride, progress_bar=progress_updater.tick)
            if result is not None:
                deliver_result(on_done)
            else:
                deliver_result(on_cancelled)

        self._enqueue_task(
            task_id="finish_separation",
            title="Separating Stars",
            total=SEPARATION_PROGRESS_TOTAL,
            desc="Separating stars from sky background...",
            work=work,
        )

    def on_starnet_stride_changed(self, stride: int) -> None:
        """Persist the project-owned StarNet stride and invalidate old separation outputs."""
        settings = self._project.get_settings()
        self._project.update_settings(replace(settings, starnet_stride=stride))
        self.app.workflow.save_project()
        self.updateReadyStates()

    def on_setup_starnet(self) -> None:
        """Handle user request to download and set up managed StarNet."""
        status = self.app.workflow.get_starnet_status()
        if not status.get("terms_accepted", False):
            terms_dlg = StarNetTermsDialog(self.sidebar)
            if terms_dlg.exec() != QDialog.DialogCode.Accepted:
                return
            self.app.workflow.accept_starnet_terms()

        setup_dlg = StarNetSetupDialog(self.sidebar)
        setup_dlg.start()
        if setup_dlg.exec() == QDialog.DialogCode.Accepted and setup_dlg.installation:
            self.app.workflow.set_starnet_installation(setup_dlg.installation, managed=True, terms_accepted=True)
            self.updateReadyStates()
            QMessageBox.information(
                self.sidebar,
                "StarNet2 Setup Complete",
                "StarNet2 was successfully installed, verified, and is ready for star separation.",
            )

    def on_browse_starnet(self) -> None:
        """Handle user request to discover and validate an existing StarNet installation."""
        choose_existing_starnet(
            self.sidebar,
            self.app.state,
            on_installed=lambda inst: self.app.workflow.set_starnet_installation(
                inst, managed=False, terms_accepted=True
            ),
        )
        self.updateReadyStates()

    def on_repair_starnet(self) -> None:
        """Handle user request to repair or re-probe the active StarNet installation."""
        status = self.app.workflow.get_starnet_status()
        if not status["terms_accepted"]:
            terms = StarNetTermsDialog(self.sidebar)
            if terms.exec() != QDialog.DialogCode.Accepted:
                return
            self.app.workflow.accept_starnet_terms()
        workflow = self.app.workflow
        setup = StarNetSetupDialog(self.sidebar, operation=workflow.do_repair_starnet)
        setup.start()
        if setup.exec() == QDialog.DialogCode.Accepted and setup.installation is not None:
            workflow.set_starnet_installation(setup.installation, managed=status["managed"], terms_accepted=True)
        self.updateReadyStates()

    def on_run_denoise(self) -> None:
        """Execute GraXpert AI denoising on the separated starless plate."""
        if not self._project or not self._project.source_is_current():
            QMessageBox.warning(self.sidebar, "Source Required", "Please import a source image first.")
            return
        if self.app.workflow.get_current_mask() is None:
            QMessageBox.warning(
                self.sidebar, "Sky Mask Required", "Please define a sky region before finishing starless."
            )
            return
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None:
            QMessageBox.warning(self.sidebar, "Separation Required", "Please separate stars before running denoising.")
            return

        if self._denoise_timer is not None and self._denoise_timer.isActive():
            self._denoise_timer.stop()

        has_endpoint = self._project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None

        if hasattr(self.sidebar, "starlessSettings"):
            strength = self.sidebar.starlessSettings.get_strength()
            scope = self.sidebar.starlessSettings.get_scope()
            structure = self.sidebar.starlessSettings.get_structure()
            detail = self.sidebar.starlessSettings.get_detail()
            status = self.app.workflow.get_graxpert_status()
            policy = status.get("policy")
            model_ready = status.get("model_ready", False)
            is_ready = bool(model_ready and policy and policy.get("verified", False))
            if strength > 0 and not is_ready and not has_endpoint:
                msg = status.get("setup_error") or "GraXpert AI model is unavailable or setup is incomplete."
                QMessageBox.warning(self.sidebar, "GraXpert Unavailable", msg)
                return
            settings = self._project.get_settings()
            self._project.update_settings(
                replace(
                    settings,
                    denoise_strength=strength,
                    denoise_scope=scope,
                    structure_amount=structure,
                    detail_amount=detail,
                )
            )
            self.app.workflow.save_project()
            if hasattr(self.sidebar.starlessSettings, "lbl_status"):
                self.sidebar.starlessSettings.lbl_status.hide()

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done():
            self.updateReadyStates()
            p = self._project.current_artifact_path(ROLE_FINISHED_STARLESS) or self._project.current_artifact_path(
                ROLE_DENOISED_STARLESS
            )
            if p:
                denoised_file = OutputFile(basename=p.name, path=str(p), operation="Finished Starless")
                self.sidebar.outputFiles.focus_file(denoised_file)
                self.showFile(denoised_file, preserve_view=True, reload=True)

        def on_cancelled():
            self._show_task_error("finish_denoise", "Cancelled")

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Denoising starless layer with GraXpert...",
                result_guard=result_guard,
            )
            result = workflow.do_denoise_starless(progress_bar=progress_updater.tick)
            if result is not None:
                workflow.do_recombine()
                deliver_result(on_done)
            else:
                deliver_result(on_cancelled)

        self._enqueue_task(
            task_id="finish_denoise",
            title="Denoising Starless",
            total=100,
            desc="Denoising starless layer with GraXpert...",
            work=work,
        )

    def on_denoise_strength_changed(self, value: float) -> None:
        """Update denoise strength setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.denoise_strength == value:
            return
        self._project.update_settings(replace(settings, denoise_strength=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        endpoint = self._project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if endpoint is not None or value == 0.0:
            self._debounce_denoise_preview()

    def on_denoise_scope_changed(self, scope: str) -> None:
        """Update denoise scope setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.denoise_scope == scope:
            return
        self._project.update_settings(replace(settings, denoise_scope=scope))
        self.app.workflow.save_project()
        self.updateReadyStates()
        endpoint = self._project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if endpoint is not None or settings.denoise_strength == 0.0:
            self._debounce_denoise_preview()

    def on_structure_amount_changed(self, value: float) -> None:
        """Update structure amount setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.structure_amount == value:
            return
        self._project.update_settings(replace(settings, structure_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        endpoint = self._project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if endpoint is not None or settings.denoise_strength == 0.0:
            self._debounce_denoise_preview()

    def on_detail_amount_changed(self, value: float) -> None:
        """Update detail amount setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.detail_amount == value:
            return
        self._project.update_settings(replace(settings, detail_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        endpoint = self._project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if endpoint is not None or settings.denoise_strength == 0.0:
            self._debounce_denoise_preview()

    def on_reset_starless(self) -> None:
        """Reset starless finishing settings to their defaults."""
        settings = self._project.get_settings()
        self._project.update_settings(
            replace(
                settings,
                denoise_strength=DEFAULT_DENOISE_STRENGTH_PERCENT,
                denoise_scope=DEFAULT_DENOISE_SCOPE,
                structure_amount=DEFAULT_STRUCTURE_AMOUNT_PERCENT,
                detail_amount=DEFAULT_DETAIL_AMOUNT_PERCENT,
            )
        )
        self.app.workflow.save_project()
        if hasattr(self.sidebar, "starlessSettings"):
            self.sidebar.starlessSettings.set_from_project(self._project)
        self.updateReadyStates()
        endpoint = self._project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if endpoint is not None:
            self._debounce_denoise_preview()

    def _debounce_denoise_preview(self) -> None:
        """Debounce rapid slider interactions before updating blend and composite."""
        if self._denoise_timer is None:
            self._denoise_timer = QTimer(self.sidebar)
            self._denoise_timer.setSingleShot(True)
            self._denoise_timer.timeout.connect(self._apply_interactive_denoise)
        self._denoise_timer.start(100)

    def _apply_interactive_denoise(self) -> None:
        """Apply strength/scope blending from cached endpoint and recompose preview."""
        if not self._result_guard()():
            return
        if not self._project or not self._project.source_is_current():
            return
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None:
            return

        endpoint = self._project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if endpoint is None and self._project.get_settings().denoise_strength > 0.0:
            return

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done():
            self.updateReadyStates()
            p = self._project.current_artifact_path(ROLE_FINISHED_STARLESS) or self._project.current_artifact_path(
                ROLE_DENOISED_STARLESS
            )
            if p:
                denoised_file = OutputFile(basename=p.name, path=str(p), operation="Finished Starless")
                self.sidebar.outputFiles.focus_file(denoised_file)
                self.showFile(denoised_file, preserve_view=True, reload=True)

        def on_cancelled():
            pass

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Updating starless finishing...",
                result_guard=result_guard,
            )
            result = workflow.do_denoise_starless(progress_bar=progress_updater.tick)
            if result is not None:
                workflow.do_recombine()
                deliver_result(on_done)
            else:
                deliver_result(on_cancelled)

        accepted = self._enqueue_task(
            task_id="finish_denoise_preview",
            title="Finish Starless",
            total=100,
            desc="Updating starless finishing...",
            work=work,
        )
        if not accepted:
            # The shared queue rejects duplicate task IDs, including a stale
            # preview still running after these settings changed. Keep one
            # pending update so the latest settings run when that job exits.
            self._debounce_denoise_preview()

    def _update_cutoff_display(self) -> None:
        """Update N of M stars and cutoff score in Step 4 card using public summary."""
        if not self.sidebar or not hasattr(self.sidebar, "starsSettings"):
            return
        workflow = getattr(self.app, "workflow", None)
        if workflow is None or not hasattr(workflow, "get_star_catalog_summary"):
            self.sidebar.starsSettings.set_cutoff_display(None, None, None)
            return
        summary = workflow.get_star_catalog_summary()
        if summary is not None:
            self.sidebar.starsSettings.set_cutoff_display(
                summary["included_count"],
                summary["total_count"],
                summary.get("cutoff_score"),
            )
        else:
            self.sidebar.starsSettings.set_cutoff_display(None, None, None)

    def _show_stars_status(self, message: str, is_error: bool = True) -> None:
        """Show error or preparation status message in Step 4 card."""
        if self.sidebar is not None and hasattr(self.sidebar, "starsSettings"):
            style = (
                "color: #b91c1c; font-size: 11px;"
                if is_error
                else "color: #64748b; font-size: 11px; font-style: italic;"
            )
            self.sidebar.starsSettings.lbl_status.setStyleSheet(style)
            self.sidebar.starsSettings.lbl_status.setText(message)
            self.sidebar.starsSettings.lbl_status.show()

    def _hide_stars_status(self) -> None:
        """Hide status message in Step 4 card."""
        if self.sidebar is not None and hasattr(self.sidebar, "starsSettings"):
            self.sidebar.starsSettings.lbl_status.hide()

    def _render_immediate_preview(self) -> bool:
        """Perform immediate synchronous cached-layer composition without a worker job."""
        if not self._result_guard()():
            return False
        if not self._project or not self._project.source_is_current():
            return False
        if self._project.current_artifact_path(ROLE_SEPARATED_STARS) is None:
            return False

        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None and hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
            return False

        workflow = getattr(self.app, "workflow", None)
        if workflow is None or not hasattr(workflow, "render_star_preview"):
            return False

        active_layer = (
            self.sidebar.starsSettings.get_preview_layer()
            if self.sidebar and hasattr(self.sidebar, "starsSettings")
            else "composite"
        )
        req_layer = "finished_stars" if self._is_comparing else active_layer
        compare_flag = self._is_comparing

        try:
            preview = workflow.render_star_preview(
                layer=req_layer,
                compare=compare_flag,
            )
        except Exception as error:
            logger.warning("Failed to render star preview: %s", error)
            self._show_stars_status(f"Preview unavailable: {error}", is_error=True)
            return False

        if preview is not None:
            source_dims = self._project.get_source_dimensions()
            if source_dims is not None and (source_dims[0] > preview.shape[0] or source_dims[1] > preview.shape[1]):
                self._show_stars_status("Reduced-resolution preview; saved image uses full resolution.", is_error=False)
            else:
                self._hide_stars_status()
            if canvas is not None:
                canvas.setFromNumpyArray(preview, resetZoomAndPosition=False)
            self._update_output_file_focus(active_layer)
            return True

        self._show_stars_status("Star effects layers are preparing or unavailable.", is_error=False)
        return False

    def _update_output_file_focus(self, active_layer: str) -> None:
        """Update focused file in sidebar OutputFiles section to reflect active layer."""
        if not self.sidebar or not hasattr(self.sidebar, "outputFiles"):
            return
        p = None
        op_label = "Composite"
        if active_layer == "finished_stars":
            p = self._project.current_artifact_path(ROLE_FINISHED_STARS) or self._project.current_artifact_path(
                ROLE_SEPARATED_STARS
            )
            op_label = "Finished Stars" if p == self._project.current_artifact_path(ROLE_FINISHED_STARS) else "Stars"
        elif active_layer == "original_stars":
            p = self._project.current_artifact_path(ROLE_SEPARATED_STARS)
            op_label = "Stars"
        elif active_layer == "composite":
            p = self._project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
            op_label = "Composite"
        if p:
            f = OutputFile(basename=p.name, path=str(p), operation=op_label)
            self.sidebar.outputFiles.focus_file(f)

    def on_star_amount_changed(self, value: float) -> None:
        """Update finished star amount setting; immediate composition only."""
        settings = self._project.get_settings()
        if settings.star_amount == value:
            return
        self._project.update_settings(replace(settings, star_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_blend_mode_changed(self, mode: str) -> None:
        """Update finished stars blend mode; immediate composition only."""
        settings = self._project.get_settings()
        if settings.blend_mode == mode:
            return
        self._project.update_settings(replace(settings, blend_mode=mode))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_original_stars_amount_changed(self, value: float) -> None:
        """Update original star amount setting; immediate composition only."""
        settings = self._project.get_settings()
        if settings.original_stars_amount == value:
            return
        self._project.update_settings(replace(settings, original_stars_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_original_stars_blend_mode_changed(self, mode: str) -> None:
        """Update original stars blend mode; immediate composition only."""
        settings = self._project.get_settings()
        if settings.original_stars_blend_mode == mode:
            return
        self._project.update_settings(replace(settings, original_stars_blend_mode=mode))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_round_stars_enabled_changed(self, value: bool) -> None:
        """Update round stars enabled setting; immediate composition only."""
        settings = self._project.get_settings()
        if settings.round_stars_enabled == value:
            return
        self._project.update_settings(replace(settings, round_stars_enabled=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_round_stars_amount_changed(self, value: float) -> None:
        """Update round stars correction amount; immediate composition only."""
        settings = self._project.get_settings()
        if settings.round_stars_amount == value:
            return
        self._project.update_settings(replace(settings, round_stars_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_star_glow_enabled_changed(self, value: bool) -> None:
        """Update star glow enabled setting; immediate composition only."""
        settings = self._project.get_settings()
        if settings.star_glow_enabled == value:
            return
        self._project.update_settings(replace(settings, star_glow_enabled=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_star_glow_amount_changed(self, value: float) -> None:
        """Update star glow amount setting; immediate composition only."""
        settings = self._project.get_settings()
        if settings.star_glow_amount == value:
            return
        self._project.update_settings(replace(settings, star_glow_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._render_immediate_preview()

    def on_glow_star_count_changed(self, count: int) -> None:
        """Update glow subset count and schedule Glow-only recalculation."""
        settings = self._project.get_settings()
        if settings.glow_star_count == count:
            return
        self._project.update_settings(replace(settings, glow_star_count=count))
        self.app.workflow.save_project()
        self.updateReadyStates()
        if self._pending_stars_action != "effects":
            self._pending_stars_action = "glow"
        self._debounce_stars_preview()

    def on_star_glow_radius_px_changed(self, value: float) -> None:
        """Update star glow radius and schedule Glow-only recalculation."""
        settings = self._project.get_settings()
        if settings.star_glow_radius_px == value:
            return
        self._project.update_settings(replace(settings, star_glow_radius_px=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        if self._pending_stars_action != "effects":
            self._pending_stars_action = "glow"
        self._debounce_stars_preview()

    def on_star_count_cutoff_changed(self, cutoff: Optional[int]) -> None:
        """Update star count cutoff and schedule incremental measurement & effects recalculation."""
        settings = self._project.get_settings()
        if settings.star_count_cutoff == cutoff:
            return
        self._project.update_settings(replace(settings, star_count_cutoff=cutoff))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._update_cutoff_display()
        self._pending_stars_action = "effects"
        self._debounce_stars_preview()

    def on_stars_preview_layer_changed(self, layer: str) -> None:
        """Switch preview layer choice; immediate composition with zoom/pan preserved."""
        if not self._project or not self._project.source_is_current():
            return
        self._render_immediate_preview()

    def on_compare_pressed(self) -> None:
        """Hold-to-compare pressed: view S_inc without cosmetic effects without mutating settings."""
        self._is_comparing = True
        self._render_immediate_preview()

    def on_compare_released(self) -> None:
        """Hold-to-compare released: restore normal preview without mutating settings."""
        self._is_comparing = False
        self._render_immediate_preview()

    def on_reset_stars(self) -> None:
        """Reset star finishing and recombination settings to defaults."""
        settings = self._project.get_settings()
        self._project.update_settings(
            replace(
                settings,
                star_count_cutoff=DEFAULT_STAR_COUNT_CUTOFF,
                round_stars_enabled=DEFAULT_ROUND_STARS_ENABLED,
                round_stars_amount=DEFAULT_ROUND_STARS_AMOUNT_PERCENT,
                star_glow_enabled=DEFAULT_STAR_GLOW_ENABLED,
                glow_star_count=DEFAULT_GLOW_STAR_COUNT,
                star_glow_amount=DEFAULT_STAR_GLOW_AMOUNT_PERCENT,
                star_glow_radius_px=DEFAULT_STAR_GLOW_RADIUS_PX,
                star_amount=DEFAULT_STAR_AMOUNT_PERCENT,
                original_stars_amount=DEFAULT_ORIGINAL_STARS_AMOUNT_PERCENT,
                original_stars_blend_mode=DEFAULT_BLEND_MODE,
                blend_mode=DEFAULT_BLEND_MODE,
            )
        )
        self.app.workflow.save_project()
        if hasattr(self.sidebar, "starsSettings"):
            self.sidebar.starsSettings.set_from_project(self._project)
        if hasattr(self.sidebar, "recombineSettings"):
            self.sidebar.recombineSettings.set_from_project(self._project)
        self.updateReadyStates()
        self._update_cutoff_display()
        self._pending_stars_action = "effects"
        self._debounce_stars_preview()

    def _debounce_stars_preview(self) -> None:
        """Debounce rapid interactions before updating star layers or composite."""
        if self._stars_timer is None:
            self._stars_timer = QTimer(self.sidebar)
            self._stars_timer.setSingleShot(True)
            self._stars_timer.timeout.connect(self._apply_interactive_stars)
        self._stars_timer.start(100)

    def _apply_interactive_stars(self) -> None:
        """Apply star effects in worker job when action is effects or glow."""
        if not self._result_guard()():
            return
        if not self._project or not self._project.source_is_current():
            return
        if self._project.current_artifact_path(ROLE_SEPARATED_STARS) is None:
            return
        if self._project.current_artifact_path(ROLE_SKY_MASK) is None:
            return

        action = self._pending_stars_action
        if action not in ("effects", "glow"):
            # Composition action must return without any worker
            if not self._render_immediate_preview():
                self._show_stars_status("Star effects layers are preparing or unavailable.", is_error=False)
            return

        # Snapshot action and revision when launching worker job
        job_revision = self._project.processing_revision
        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        self._hide_stars_status()

        def on_done():
            # Only reset pending action if no newer edits arrived while job was running
            if self._project.processing_revision == job_revision:
                self._pending_stars_action = "none"
            self.updateReadyStates()
            self._update_cutoff_display()
            canvas = getattr(self.shell, "canvas_main", None)
            if canvas is not None and hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                return
            if not self._render_immediate_preview():
                self._show_stars_status("Star preview could not be composed.", is_error=True)

        def on_cancelled():
            if self._project.processing_revision == job_revision:
                self._pending_stars_action = "none"

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Updating star finishing...",
                result_guard=result_guard,
            )
            stars_out = workflow.do_finish_stars(progress_bar=progress_updater.tick)
            if stars_out is None:
                deliver_result(on_cancelled)
                return

            recombine_res = workflow.do_recombine()
            if recombine_res is not None:
                deliver_result(on_done)
            else:
                deliver_result(on_cancelled)

        accepted = self._enqueue_task(
            task_id="finish_stars_preview",
            title="Finish Stars",
            total=100,
            desc="Updating star finishing...",
            work=work,
        )
        if not accepted:
            self._debounce_stars_preview()


__all__ = ["FinishView"]
