"""Finish mode view controller managing the sidebar and canvas interaction."""

from __future__ import annotations

from concurrent.futures import CancelledError
from dataclasses import replace
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Final, Optional

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from startrails.lib.denoise.defaults import DEFAULT_SKY_DETECTION_DEVICE
from startrails.lib.file import File, OutputFile
from startrails.lib.finish.defaults import (
    DEFAULT_BLEND_MODE,
    DEFAULT_STAR_AMOUNT_PERCENT,
    ROLE_DENOISE_ENDPOINT,
    ROLE_DENOISED_STARLESS,
    ROLE_FINISHED_COMPOSITE,
    ROLE_FINISHED_STARLESS,
    ROLE_SEPARATED_STARLESS,
    ROLE_SEPARATED_STARS,
    ROLE_SKY_MASK,
)
from startrails.lib.project_finish import FinishProject
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.sidebar_finish import SidebarFinish
from startrails.ui.sky_mask_controller import SkyMaskController
from startrails.ui.views.base import ModeView
from startrails.workflow.finish import SEPARATION_PROGRESS_TOTAL

if TYPE_CHECKING:
    from startrails.app import App


_SOURCE_IMAGE_FILTER = (
    "Supported Images (*.jpg *.jpeg *.tif *.tiff);;TIFF (*.tif *.tiff);;JPEG (*.jpg *.jpeg);;All Files (*)"
)
FINISH_SLIDER_DEBOUNCE_MS: Final[int] = 200

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
        self._recombine_timer: Optional[QTimer] = None
        self._last_output_file: Optional[OutputFile] = None
        self._retained_starless_outputs: dict[str, Path] = {}

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
        if hasattr(self.sidebar, "btn_export_layers"):
            self.connect_signal(self.sidebar.btn_export_layers.clicked, self.on_export_layers)

        self.connect_signal(self.sidebar.inputFiles.addRequested, self.on_import_source)
        self.connect_signal(self.sidebar.inputFiles.showFile, self._on_file_section_show_file)
        self.connect_signal(self.sidebar.inputFiles.removeFile, self.on_remove_source)
        self.connect_signal(self.sidebar.outputFiles.showFile, self._on_file_section_show_file)

        self.bind_project_actions(self.sidebar.pushButton_newProject, self.sidebar.pushButton_openProject)

        # Wire reusable sky masking controller (resolve app.workflow dynamically so
        # replacing/opening a Finish project keeps using the active workflow).
        if hasattr(self.sidebar, "skySettings"):
            self.connect_signal(self.sidebar.skySettings.settings_changed, lambda: self.app.workflow.save_project())
            self.mask_controller = SkyMaskController(
                shell=self.shell,
                settings_widget=self.sidebar.skySettings,
                get_source_image=lambda: self._project.source_file if self._project.source_is_current() else None,
                show_source_image=lambda: self.showFile(
                    self._project.source_file, preserve_view=True, expand_sections=False
                ),
                get_saved_mask=lambda: self.app.workflow.get_current_mask(),
                save_mask=self._save_mask_to_project,
                detect_sky_fn=lambda *args, **kwargs: self.app.workflow.do_detect_sky(*args, **kwargs),
                refine_mask_fn=lambda *args, **kwargs: self.app.workflow.do_refine_mask(*args, **kwargs),
                enqueue_task=self._enqueue_task,
                get_post_result=self._get_post_result,
                get_result_guard=self._result_guard,
                on_manual_edit=self._on_manual_mask_edit,
                on_detection_finished=self._on_mask_detection_finished,
                sky_card=self.sidebar.skyCard,
                get_device=lambda: DEFAULT_SKY_DETECTION_DEVICE,
                get_detection_options=lambda: {
                    "model_path": self._project.auto_mask_path,
                    "foliage_protection": self._project.mask_foliage_protection,
                },
            )
            self.mask_controller.bind()

        if hasattr(self.sidebar, "separateSettings"):
            self.connect_signal(self.sidebar.separateSettings.run_separation_requested, self.on_run_separation)
            self.connect_signal(self.sidebar.separateSettings.stride_changed, self.on_nox_stride_changed)
            self.connect_signal(
                self.sidebar.separateSettings.chroma_postfilter_changed, self.on_chroma_postfilter_changed
            )

        if hasattr(self.sidebar, "separateCard"):
            self.connect_signal(self.sidebar.separateCard.expanded, self._on_separate_card_expanded)
            if hasattr(self.sidebar.separateCard, "before_after_toggled"):
                self.connect_signal(self.sidebar.separateCard.before_after_toggled, self._on_separate_before_after)

        if hasattr(self.sidebar, "starlessSettings"):
            if hasattr(self.sidebar.starlessSettings, "enable_denoise_changed"):
                self.connect_signal(
                    self.sidebar.starlessSettings.enable_denoise_changed, self.on_enable_denoise_changed
                )
            if hasattr(self.sidebar.starlessSettings, "enable_sharpen_changed"):
                self.connect_signal(
                    self.sidebar.starlessSettings.enable_sharpen_changed, self.on_enable_sharpen_changed
                )
            self.connect_signal(self.sidebar.starlessSettings.run_denoise_requested, self.on_run_denoise)
            self.connect_signal(
                self.sidebar.starlessSettings.denoise_strength_changed, self.on_denoise_strength_changed
            )
            self.connect_signal(self.sidebar.starlessSettings.denoise_scope_changed, self.on_denoise_scope_changed)
            self.connect_signal(
                self.sidebar.starlessSettings.structure_amount_changed, self.on_structure_amount_changed
            )
            self.connect_signal(self.sidebar.starlessSettings.detail_amount_changed, self.on_detail_amount_changed)
            self.connect_signal(self.sidebar.starlessSettings.slider_dragging, self._on_starless_slider_dragging)

        if hasattr(self.sidebar, "starlessCard"):
            self.connect_signal(self.sidebar.starlessCard.expanded, self._on_starless_card_expanded)
            if hasattr(self.sidebar.starlessCard, "before_after_toggled"):
                self.connect_signal(self.sidebar.starlessCard.before_after_toggled, self._on_starless_before_after)

        if hasattr(self.sidebar, "recombineSettings"):
            self.connect_signal(self.sidebar.recombineSettings.star_amount_changed, self.on_star_amount_changed)
            self.connect_signal(self.sidebar.recombineSettings.star_threshold_changed, self.on_star_threshold_changed)
            self.connect_signal(self.sidebar.recombineSettings.blend_mode_changed, self.on_blend_mode_changed)
            self.connect_signal(self.sidebar.recombineSettings.slider_dragging, self._on_recombine_slider_dragging)

        if hasattr(self.sidebar, "recombineCard"):
            self.connect_signal(self.sidebar.recombineCard.expanded, self._on_recombine_card_expanded)
            if hasattr(self.sidebar.recombineCard, "before_after_toggled"):
                self.connect_signal(self.sidebar.recombineCard.before_after_toggled, self._on_recombine_before_after)

    def teardown(self) -> None:
        """Disconnect signals and clean up canvas and mask controller state."""
        self._disposed = True
        self._generation += 1
        if self._denoise_timer is not None:
            self._denoise_timer.stop()
            self._denoise_timer = None
        if self._recombine_timer is not None:
            self._recombine_timer.stop()
            self._recombine_timer = None
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
            "finish_recombine_preview": self._debounce_recombine,
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
        elif task_id in (
            "finish_recombine",
            "finish_recombine_preview",
            "finish_save_export",
            "finish_export_layers",
        ):
            if self.sidebar is not None and hasattr(self.sidebar, "recombineSettings"):
                if hasattr(self.sidebar.recombineSettings, "lbl_status"):
                    self.sidebar.recombineSettings.lbl_status.setText(message)
                    self.sidebar.recombineSettings.lbl_status.show()
        elif self.sidebar is not None and hasattr(self.sidebar, "skySettings"):
            self.sidebar.skySettings.ui.error.setText(message)
            self.sidebar.skySettings.ui.error.show()

    def resetProjectView(self) -> None:  # noqa: N802 - ModeView interface
        """Reset sidebar view state when a new or opened project is active."""
        self._generation += 1
        self._last_output_file = None
        self._retained_starless_outputs.clear()
        if self._denoise_timer is not None and self._denoise_timer.isActive():
            self._denoise_timer.stop()
        if self._recombine_timer is not None and self._recombine_timer.isActive():
            self._recombine_timer.stop()
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
                else:
                    canvas.set_denoise_mask(None)
                    canvas.set_mask_edit_mode(False)
            else:
                canvas.setFile(None)
                canvas.set_denoise_mask(None)
                canvas.set_mask_edit_mode(False)
                self._displayed_source_id = None

        if self.sidebar is not None:
            self.sidebar.update_from_project(self._project, dimensions)
            self.sidebar.inputFiles.set_files(self.app.workflow.getInputFileList())
            self.sidebar.outputFiles.set_files(self._build_output_files())
            self.sidebar.lock_output_files_height()
            if self._project.source_is_current() and self._project.source_file is not None:
                self.sidebar.inputFiles.focus_file(self._project.source_file)
            if hasattr(self.sidebar, "skySettings"):
                self.sidebar.skySettings.set_from_project(self._project)

        self.updateReadyStates()
        self._reset_preview_toggles()

    def _reset_preview_toggles(self, exclude: Optional[Any] = None) -> None:
        """Reset step before/after preview toggles to their default after state without emitting."""
        if self.sidebar is None:
            return
        for card_name in ("skyCard", "separateCard", "starlessCard", "recombineCard"):
            card = getattr(self.sidebar, card_name, None)
            if card is not None and card is not exclude and hasattr(card, "reset_before_after"):
                card.reset_before_after(emit=False)

    def _on_file_section_show_file(self, file: Optional[File]) -> None:
        """Show a file selected from the Input or Output FileSection, preserving zoom/pan."""
        self._reset_preview_toggles()
        self.showFile(file, preserve_view=True)

    def showFile(  # noqa: N802 - ModeView interface
        self,
        file: Optional[File],
        preserve_view: Optional[bool] = None,
        reload: bool = False,
        expand_sections: bool = True,
    ) -> None:
        """Handle preview display on the canvas.

        preserve_view=None keeps the canvas's same-file behavior; True keeps
        zoom/pan while switching files. reload re-reads pixels, which is
        required after the displayed file has been rewritten.
        """
        if hasattr(self.shell, "currentFile"):
            self.shell.currentFile = file
        if hasattr(self.shell, "label_imageName") and self.shell.label_imageName is not None:
            self.shell.label_imageName.setText(file.basename if file is not None else "")

        if self.sidebar is not None:
            if file is not None:
                target_input = next(
                    (
                        f
                        for f in self.sidebar.inputFiles.model.files
                        if getattr(f, "path", None) == getattr(file, "path", None)
                    ),
                    None,
                )
                target_output = next(
                    (
                        f
                        for f in self.sidebar.outputFiles.model.files
                        if getattr(f, "path", None) == getattr(file, "path", None)
                    ),
                    None,
                )
                self.sidebar.inputFiles.focus_file(
                    target_input if target_input is not None else file, expand=expand_sections
                )
                self.sidebar.outputFiles.focus_file(
                    target_output if target_output is not None else file, expand=expand_sections
                )

            if isinstance(file, OutputFile):
                self._last_output_file = file

        canvas = getattr(self.shell, "canvas_main", None)
        if canvas is not None:
            if isinstance(file, OutputFile):
                if hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                    canvas.set_mask_edit_mode(False)

            canvas.setFile(file, reload=reload, preserve_view=preserve_view)

            if (
                file is not None
                and getattr(self._project, "source_file", None) is not None
                and getattr(file, "path", None) == self._project.source_file.path
            ):
                show_overlay = (
                    self.mask_controller.is_overlay_enabled()
                    if self.mask_controller is not None
                    else bool(
                        self.sidebar is not None
                        and hasattr(self.sidebar, "skyCard")
                        and self.sidebar.skyCard.is_expanded
                        and not self.sidebar.skyCard.is_showing_before()
                    )
                )
                if show_overlay:
                    if hasattr(canvas, "set_mask_edit_mode"):
                        canvas.set_mask_edit_mode(True)
                elif hasattr(canvas, "set_mask_edit_mode") and canvas.is_mask_edit_mode():
                    canvas.set_mask_edit_mode(False)

    def _build_output_files(self) -> list[OutputFile]:
        """Return project outputs plus retained starless outputs awaiting recomputation."""
        outputs = list(self.app.workflow.get_output_file_list())
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None and self._retained_starless_outputs:
            present = {f.operation for f in outputs}
            retained_specs = (
                (ROLE_DENOISED_STARLESS, "Denoised Starless"),
                (ROLE_FINISHED_STARLESS, "Finished Starless"),
            )
            insert_at = sum(1 for f in outputs if f.operation in ("Starless", "Stars"))
            for role, label in retained_specs:
                path = self._retained_starless_outputs.get(role)
                if path is not None and label not in present and path.is_file():
                    outputs.insert(insert_at, OutputFile(basename=path.name, path=str(path), operation=label))
                    insert_at += 1
        else:
            self._retained_starless_outputs.clear()
        return outputs

    def updateReadyStates(self, _=None) -> None:  # noqa: N802 - ModeView interface
        """Update file sections and step prerequisites based on project readiness."""
        if self.sidebar is not None and isinstance(self._project, FinishProject):
            self.app.workflow.invalidate_if_separation_changed()
            if hasattr(self.app.workflow, "invalidate_if_graxpert_changed"):
                self.app.workflow.invalidate_if_graxpert_changed()
            if hasattr(self.app.workflow, "invalidate_if_starless_filter_changed"):
                self.app.workflow.invalidate_if_starless_filter_changed()
            self.sidebar.inputFiles.set_files(self.app.workflow.getInputFileList())
            self.sidebar.outputFiles.set_files(self._build_output_files())
            self.sidebar.lock_output_files_height()
            self.sidebar.update_prerequisites(self._project)
            # If the canvas is showing a file that is no longer available, fall
            # back cleanly without unnecessarily reverting to source.
            canvas = getattr(self.shell, "canvas_main", None)
            current_file = getattr(canvas, "file", None) if canvas is not None else None
            if current_file is not None:
                current_path = getattr(current_file, "path", None)
                available = {
                    getattr(f, "path", None)
                    for f in self.sidebar.inputFiles.model.files + self.sidebar.outputFiles.model.files
                }
                if current_path not in available:
                    curr_p = None
                    try:
                        if current_path:
                            curr_p = Path(current_path).resolve()
                    except Exception:
                        pass

                    separated_starless_path = self._project.current_artifact_path(ROLE_SEPARATED_STARLESS)
                    has_separated_starless = separated_starless_path is not None

                    is_fin_starless = False
                    is_comp = False
                    is_starless_artifact = False
                    try:
                        if curr_p is not None:
                            fin_starless_p = self._project.artifact_path(ROLE_FINISHED_STARLESS).resolve()
                            comp_p = self._project.artifact_path(ROLE_FINISHED_COMPOSITE).resolve()
                            denoised_starless_p = self._project.artifact_path(ROLE_DENOISED_STARLESS).resolve()
                            sep_starless_p = self._project.artifact_path(ROLE_SEPARATED_STARLESS).resolve()

                            is_fin_starless = (
                                curr_p == fin_starless_p
                                or curr_p
                                == self._project.artifact_path(ROLE_FINISHED_STARLESS, for_write=True).resolve()
                                or curr_p.name == "finished_starless.tif"
                            )
                            is_comp = (
                                curr_p == comp_p
                                or curr_p
                                == self._project.artifact_path(ROLE_FINISHED_COMPOSITE, for_write=True).resolve()
                                or curr_p.name == "composite.tif"
                            )
                            is_starless_artifact = (
                                is_fin_starless
                                or is_comp
                                or curr_p in (denoised_starless_p, sep_starless_p)
                                or curr_p.name in ("denoised_starless.tif", "starless.tif")
                            )
                    except Exception:
                        pass

                    file_exists = curr_p.exists() if curr_p is not None else False

                    if is_starless_artifact and file_exists and has_separated_starless:
                        # Leave the current starless or composite image on the canvas while updating
                        pass
                    elif is_starless_artifact and not file_exists:
                        if has_separated_starless:
                            starless_file = OutputFile(
                                basename=separated_starless_path.name,
                                path=str(separated_starless_path),
                                operation="Starless",
                            )
                            self.sidebar.outputFiles.focus_file(starless_file)
                            self.showFile(starless_file, preserve_view=True)
                        elif self._project.source_is_current():
                            self.showFile(self._project.source_file, preserve_view=True)
                    elif self._project.source_is_current():
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

    def _starless_finishing_needs_recompute(self) -> bool:
        """Check if starless AI finishing artifacts need recomputation before export."""
        if not self._project or not self._project.source_is_current():
            return False
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None:
            return False
        settings = self._project.get_settings()
        graxpert_status = (
            self.app.workflow.get_graxpert_status() if hasattr(self.app.workflow, "get_graxpert_status") else {}
        )
        graxpert_ready = bool(graxpert_status.get("configured", graxpert_status.get("model_ready", False)))
        has_endpoint = (
            self._project.current_artifact_path(ROLE_DENOISE_ENDPOINT) is not None
            or self._project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        )
        needs_denoise = (
            settings.enable_starless_denoise
            and self._project.current_artifact_path(ROLE_DENOISED_STARLESS) is None
            and (has_endpoint or settings.denoise_strength == 0.0 or graxpert_ready)
        )
        needs_sharpen = (
            settings.enable_starless_sharpen
            and (settings.structure_amount > 0 or settings.detail_amount > 0)
            and self._project.current_artifact_path(ROLE_FINISHED_STARLESS) is None
        )
        return bool(needs_denoise or needs_sharpen)

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

        if (
            self.sidebar is not None
            and hasattr(self.sidebar, "recombineSettings")
            and hasattr(self.sidebar.recombineSettings, "lbl_status")
        ):
            self.sidebar.recombineSettings.lbl_status.hide()

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done(out_path: Any):
            self.updateReadyStates()
            self._reset_preview_toggles()
            comp_path = self._project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
            if comp_path is not None:
                comp_file = OutputFile(basename=comp_path.name, path=str(comp_path), operation="Composite")
                self.showFile(comp_file, preserve_view=True, reload=True)
            elif out_path is not None and Path(out_path).exists():
                p = Path(out_path)
                out_file = OutputFile(basename=p.name, path=str(p), operation="Export")
                self.showFile(out_file, preserve_view=True, reload=True)
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
            if self._starless_finishing_needs_recompute():
                if workflow.do_denoise_starless(progress_bar=progress_updater.tick) is None:
                    deliver_result(on_cancelled)
                    return

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

    def on_export_layers(self) -> None:
        """Export separated and finished layers to directory chosen by user."""
        if not getattr(self._project, "source_file", None):
            QMessageBox.information(self.sidebar, "Export Layers", "Please import a source image first.")
            return
        if not (
            self._project.current_artifact_path(ROLE_SEPARATED_STARLESS)
            and self._project.current_artifact_path(ROLE_SEPARATED_STARS)
        ):
            QMessageBox.information(
                self.sidebar,
                "Export Layers",
                "Separate stars before exporting layers.",
            )
            return

        start_dir = str(self._project.get_output_dir())
        selected_dir = QFileDialog.getExistingDirectory(self.sidebar, "Export Layers", start_dir)
        if not selected_dir:
            return

        if (
            self.sidebar is not None
            and hasattr(self.sidebar, "recombineSettings")
            and hasattr(self.sidebar.recombineSettings, "lbl_status")
        ):
            self.sidebar.recombineSettings.lbl_status.hide()

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done(exported: dict[str, Path]):
            self.updateReadyStates()
            names = "\n".join(f"- {p.name}" for p in exported.values())
            QMessageBox.information(
                self.sidebar,
                "Layers Exported",
                f"Successfully exported layers to:\n{selected_dir}\n\n{names}",
            )

        def on_cancelled():
            pass

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Exporting layers...",
                result_guard=result_guard,
            )
            if self._starless_finishing_needs_recompute():
                if workflow.do_denoise_starless(progress_bar=progress_updater.tick) is None:
                    deliver_result(on_cancelled)
                    return

            exported = workflow.do_export_layers(output_dir=selected_dir, progress_bar=progress_updater.tick)
            if exported:
                deliver_result(lambda: on_done(exported))
            else:
                deliver_result(on_cancelled)

        self._enqueue_task(
            task_id="finish_export_layers",
            title="Exporting Layers",
            total=100,
            desc="Exporting layers...",
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
        chroma_postfilter = self.sidebar.separateSettings.get_chroma_postfilter()
        self._retained_starless_outputs.clear()
        if hasattr(self.sidebar.separateSettings, "lbl_status"):
            self.sidebar.separateSettings.lbl_status.hide()

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done():
            # Same-project completion: refresh file sections and prerequisites
            # without resetting the full project view (which would lose zoom/pan).
            self.updateReadyStates()
            self._reset_preview_toggles()
            p = self._project.current_artifact_path(ROLE_SEPARATED_STARLESS)
            if p:
                starless_file = OutputFile(basename=p.name, path=str(p), operation="Starless")
                self.sidebar.outputFiles.focus_file(starless_file)
                # The job just rewrote this file; re-read its pixels.
                self.showFile(starless_file, preserve_view=True, reload=True)

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
            result = workflow.do_separate_stars(
                stride=stride,
                chroma_postfilter=chroma_postfilter,
                progress_bar=progress_updater.tick,
            )
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

    def on_nox_stride_changed(self, stride: int) -> None:
        """Persist the project-owned separation stride without discarding cached layers."""
        settings = self._project.get_settings()
        self._project.update_settings(replace(settings, nox_stride=stride))
        self.app.workflow.save_project()
        self.updateReadyStates()

    def on_chroma_postfilter_changed(self, enabled: bool) -> None:
        """Persist the project-owned chroma postfilter setting."""
        settings = self._project.get_settings()
        self._project.update_settings(replace(settings, chroma_postfilter=bool(enabled)))
        self.app.workflow.save_project()
        self.updateReadyStates()

    def _show_source_before(self) -> None:
        """Display clean source input image on canvas (mask overlay disabled) for before preview."""
        if not self._project or not self._project.source_is_current():
            return
        source = self._project.source_file
        if source is not None:
            self.showFile(source, preserve_view=True, expand_sections=False)
            canvas = getattr(self.shell, "canvas_main", None)
            if canvas is not None and hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                canvas.set_mask_edit_mode(False)

    def _show_separated_starless(self, require_stars: bool = True, expand_sections: bool = True) -> None:
        """Display Step 2 separated starless image on canvas when available."""
        if not self._project or not self._project.source_is_current():
            return
        starless_path = self._project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        stars_path = self._project.current_artifact_path(ROLE_SEPARATED_STARS) if require_stars else True
        if starless_path is not None and stars_path is not None and starless_path.exists():
            starless_file = OutputFile(basename=starless_path.name, path=str(starless_path), operation="Starless")
            self.sidebar.outputFiles.focus_file(starless_file, expand=expand_sections)
            self.showFile(starless_file, preserve_view=True, expand_sections=expand_sections)

    def _on_separate_before_after(self, showing_before: bool) -> None:
        """Handle Step 2 before/after toggle between input image (before) and starless (after)."""
        if not self._project or not self._project.source_is_current():
            return
        self._reset_preview_toggles(exclude=getattr(self.sidebar, "separateCard", None))
        if showing_before:
            self._show_source_before()
        else:
            self._show_separated_starless(expand_sections=False)

    def _on_separate_card_expanded(self) -> None:
        """When Separate Stars card is expanded, display the separated starless image if present."""
        self._reset_preview_toggles()
        self._show_separated_starless()

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

        has_endpoint = (
            self._project.current_artifact_path(ROLE_DENOISE_ENDPOINT) is not None
            or self._project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        )

        if hasattr(self.sidebar, "starlessSettings"):
            strength = self.sidebar.starlessSettings.get_strength()
            scope = self.sidebar.starlessSettings.get_scope()
            structure = self.sidebar.starlessSettings.get_structure()
            detail = self.sidebar.starlessSettings.get_detail()
            status = self.app.workflow.get_graxpert_status()
            is_ready = bool(status.get("configured", status.get("model_ready", False)))
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
            self._retained_starless_outputs.clear()
            self.updateReadyStates()
            self._reset_preview_toggles()
            active_file = self._active_starless_output_file()
            if active_file is not None and Path(active_file.path).exists():
                self._last_output_file = active_file
                self.sidebar.outputFiles.focus_file(active_file)
                self.showFile(active_file, preserve_view=True, reload=True)

        def on_cancelled():
            self._retained_starless_outputs.clear()
            self.updateReadyStates()
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

    def _mark_starless_outputs_pending(self) -> None:
        """Keep previously built starless outputs visible in the UI while recomputing."""
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None:
            return
        for role in (ROLE_DENOISED_STARLESS, ROLE_FINISHED_STARLESS):
            path = self._project.current_artifact_path(role)
            if path is not None and path.is_file():
                self._retained_starless_outputs[role] = path

    def on_denoise_strength_changed(self, value: float) -> None:
        """Update denoise strength setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.denoise_strength == value:
            return
        self._mark_starless_outputs_pending()
        self._project.update_settings(replace(settings, denoise_strength=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        if settings.enable_starless_denoise:
            self._debounce_denoise_preview()

    def on_denoise_scope_changed(self, scope: str) -> None:
        """Update denoise scope setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.denoise_scope == scope:
            return
        self._mark_starless_outputs_pending()
        self._project.update_settings(replace(settings, denoise_scope=scope))
        self.app.workflow.save_project()
        self.updateReadyStates()
        if settings.enable_starless_denoise:
            self._debounce_denoise_preview()

    def on_structure_amount_changed(self, value: float) -> None:
        """Update structure amount setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.structure_amount == value:
            return
        self._mark_starless_outputs_pending()
        self._project.update_settings(replace(settings, structure_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        if settings.enable_starless_sharpen:
            self._debounce_denoise_preview()

    def on_detail_amount_changed(self, value: float) -> None:
        """Update detail amount setting and trigger debounced preview recomposition."""
        settings = self._project.get_settings()
        if settings.detail_amount == value:
            return
        self._mark_starless_outputs_pending()
        self._project.update_settings(replace(settings, detail_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        if settings.enable_starless_sharpen:
            self._debounce_denoise_preview()

    def _active_starless_output_file(self) -> Optional[OutputFile]:
        """Return the OutputFile that matches the active denoise and sharpen toggle state with fallback."""
        if not self._project:
            return None
        sep_p = self._project.current_artifact_path(ROLE_SEPARATED_STARLESS)
        if sep_p is None:
            return None

        settings = self._project.get_settings()
        plate_path = self.app.workflow._starless_plate_path(settings, sep_p)

        if plate_path is None or not plate_path.exists():
            return None

        finished_p = self._project.current_artifact_path(ROLE_FINISHED_STARLESS)
        denoised_p = self._project.current_artifact_path(ROLE_DENOISED_STARLESS)
        if finished_p is not None and plate_path.resolve() == finished_p.resolve():
            return OutputFile(basename=plate_path.name, path=str(plate_path), operation="Finished Starless")
        if denoised_p is not None and plate_path.resolve() == denoised_p.resolve():
            return OutputFile(basename=plate_path.name, path=str(plate_path), operation="Denoised Starless")
        return OutputFile(basename=plate_path.name, path=str(plate_path), operation="Starless")

    def _intended_starless_output_missing_and_ready(self) -> bool:
        """Return True if the intended starless role artifact is unbuilt and ready to compute."""
        if not self._project or not self._project.source_is_current():
            return False
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None:
            return False

        settings = self._project.get_settings()
        if not settings.enable_starless_denoise:
            return False

        intended_role = self.app.workflow.active_starless_role(settings)
        intended_path = self._project.current_artifact_path(intended_role)
        if intended_path is not None and intended_path.exists():
            return False

        graxpert_status = (
            self.app.workflow.get_graxpert_status() if hasattr(self.app.workflow, "get_graxpert_status") else {}
        )
        graxpert_ready = bool(graxpert_status.get("configured", graxpert_status.get("model_ready", False)))
        has_endpoint = (
            self._project.current_artifact_path(ROLE_DENOISE_ENDPOINT) is not None
            or self._project.current_artifact_path(ROLE_DENOISED_STARLESS) is not None
        )
        return bool(graxpert_ready or has_endpoint or settings.denoise_strength == 0.0)

    def on_enable_denoise_changed(self, enabled: bool) -> None:
        """Toggle starless denoising and switch canvas preview without recomputation when current."""
        settings = self._project.get_settings()
        self._project.update_settings(replace(settings, enable_starless_denoise=enabled))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._reset_preview_toggles()
        self._show_starless_preview(False)

        if enabled and self._intended_starless_output_missing_and_ready():
            self._debounce_denoise_preview()

    def on_enable_sharpen_changed(self, enabled: bool) -> None:
        """Toggle starless sharpening and switch canvas preview without recomputation when current."""
        settings = self._project.get_settings()
        self._project.update_settings(replace(settings, enable_starless_sharpen=enabled))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._reset_preview_toggles()
        self._show_starless_preview(False)

        if enabled and self._intended_starless_output_missing_and_ready():
            self._debounce_denoise_preview()

    def on_enable_starless_changed(self, enabled: bool) -> None:
        """Compatibility handler for enable_starless_changed signal."""
        self.on_enable_denoise_changed(enabled)

    def _show_starless_preview(self, showing_before: bool, expand_sections: bool = True) -> None:
        """Display either Step 2 starless plate (before) or active finished starless plate (after)."""
        if not self._project or not self._project.source_is_current():
            return
        if showing_before:
            self._show_separated_starless(require_stars=False, expand_sections=expand_sections)
            return

        active_file = self._active_starless_output_file()
        if active_file is not None and Path(active_file.path).exists():
            self._last_output_file = active_file
            self.sidebar.outputFiles.focus_file(active_file, expand=expand_sections)
            self.showFile(active_file, preserve_view=True, expand_sections=expand_sections)

    def _on_starless_before_after(self, showing_before: bool) -> None:
        """Handle Step 3 before/after preview chip toggles."""
        self._reset_preview_toggles(exclude=getattr(self.sidebar, "starlessCard", None))
        self._show_starless_preview(showing_before, expand_sections=False)

    def _on_starless_card_expanded(self) -> None:
        """When Starless card is expanded, ensure active starless output is displayed or computed."""
        self._reset_preview_toggles()
        if not self._project or not self._project.source_is_current():
            return
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None:
            return

        self._show_starless_preview(False)

        if self._intended_starless_output_missing_and_ready():
            self._debounce_denoise_preview()

    def _debounce_denoise_preview(self) -> None:
        """Debounce rapid slider interactions before updating blend and composite."""
        if self._denoise_timer is None:
            self._denoise_timer = QTimer(self.sidebar)
            self._denoise_timer.setSingleShot(True)
            self._denoise_timer.timeout.connect(self._apply_interactive_denoise)
        self._denoise_timer.start(FINISH_SLIDER_DEBOUNCE_MS)

    def _apply_interactive_denoise(self) -> None:
        """Apply strength/scope blending from cached endpoint and recompose preview."""
        if self._is_starless_slider_down():
            self._debounce_denoise_preview()
            return
        if not self._result_guard()():
            return
        if not self._project or not self._project.source_is_current():
            return
        if self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None:
            return

        settings = self._project.get_settings()
        endpoint = self._project.current_artifact_path(ROLE_DENOISE_ENDPOINT) or self._project.current_artifact_path(
            ROLE_DENOISED_STARLESS
        )
        graxpert_status = (
            self.app.workflow.get_graxpert_status() if hasattr(self.app.workflow, "get_graxpert_status") else {}
        )
        graxpert_ready = bool(graxpert_status.get("configured", graxpert_status.get("model_ready", False)))
        if not settings.enable_starless_denoise:
            return
        if not (endpoint is not None or settings.denoise_strength == 0.0 or graxpert_ready):
            return

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done():
            self._retained_starless_outputs.clear()
            self.updateReadyStates()
            self._reset_preview_toggles()
            active_file = self._active_starless_output_file()
            if active_file is not None and Path(active_file.path).exists():
                self._last_output_file = active_file
                canvas = getattr(self.shell, "canvas_main", None)
                if canvas is not None and hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                    return
                self.sidebar.outputFiles.focus_file(active_file)
                self.showFile(active_file, preserve_view=True, reload=True)

        def on_cancelled():
            self._retained_starless_outputs.clear()
            self.updateReadyStates()

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
            self._debounce_denoise_preview()

    def on_star_amount_changed(self, value: float) -> None:
        """Update Stars Amount and trigger debounced preview recombination."""
        settings = self._project.get_settings()
        if settings.star_amount == value:
            return
        self._project.update_settings(replace(settings, star_amount=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._debounce_recombine()

    def on_star_threshold_changed(self, value: float) -> None:
        """Update Star Threshold and trigger debounced preview recombination."""
        settings = self._project.get_settings()
        if settings.star_threshold == value:
            return
        self._project.update_settings(replace(settings, star_threshold=value))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._debounce_recombine()

    def on_blend_mode_changed(self, mode: str) -> None:
        """Update the star-layer blend mode and trigger debounced recombination."""
        settings = self._project.get_settings()
        if settings.blend_mode == mode:
            return
        self._project.update_settings(replace(settings, blend_mode=mode))
        self.app.workflow.save_project()
        self.updateReadyStates()
        self._debounce_recombine()

    def _is_starless_slider_down(self) -> bool:
        if self.sidebar and hasattr(self.sidebar, "starlessSettings"):
            return self.sidebar.starlessSettings.is_slider_down()
        return False

    def _is_recombine_slider_down(self) -> bool:
        if self.sidebar and hasattr(self.sidebar, "recombineSettings"):
            return self.sidebar.recombineSettings.is_slider_down()
        return False

    def _on_starless_slider_dragging(self) -> None:
        if self._denoise_timer is not None and self._denoise_timer.isActive():
            self._denoise_timer.start(FINISH_SLIDER_DEBOUNCE_MS)

    def _on_recombine_slider_dragging(self) -> None:
        if self._recombine_timer is not None and self._recombine_timer.isActive():
            self._recombine_timer.start(FINISH_SLIDER_DEBOUNCE_MS)

    def _show_composite_file(
        self,
        composite_path: Path,
        respect_mask_edit_mode: bool = False,
        expand_sections: bool = True,
    ) -> None:
        composite_file = OutputFile(
            basename=composite_path.name, path=str(composite_path), operation="Composite"
        )
        self._last_output_file = composite_file
        self.sidebar.outputFiles.focus_file(composite_file, expand=expand_sections)
        if respect_mask_edit_mode:
            canvas = getattr(self.shell, "canvas_main", None)
            if canvas is not None and hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                return
        self.showFile(composite_file, preserve_view=True, expand_sections=expand_sections)

    def _on_recombine_before_after(self, showing_before: bool) -> None:
        """Handle Step 4 before/after preview chip toggles between input image and composite."""
        if not self._project or not self._project.source_is_current():
            return
        self._reset_preview_toggles(exclude=getattr(self.sidebar, "recombineCard", None))
        if showing_before:
            self._show_source_before()
            return

        composite_path = self._project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
        if composite_path is not None and composite_path.exists():
            self._show_composite_file(composite_path, expand_sections=False)
            return

        export_path = self._project.current_export_path()
        if export_path is not None and export_path.exists():
            export_file = OutputFile(basename=export_path.name, path=str(export_path), operation="Export")
            self._last_output_file = export_file
            self.showFile(export_file, preserve_view=True, expand_sections=False)
            return

        has_starless = self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None
        has_stars = self._project.current_artifact_path(ROLE_SEPARATED_STARS) is not None
        if has_starless and has_stars:
            self._debounce_recombine()

    def _on_recombine_card_expanded(self) -> None:
        """When Recombine card is expanded, ensure composite is built and displayed."""
        self._reset_preview_toggles()
        if not self._project or not self._project.source_is_current():
            return
        has_starless = self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is not None
        has_stars = self._project.current_artifact_path(ROLE_SEPARATED_STARS) is not None
        composite_path = self._project.current_artifact_path(ROLE_FINISHED_COMPOSITE)

        if has_starless and has_stars:
            if composite_path is None:
                self._debounce_recombine()
            else:
                self._show_composite_file(composite_path, respect_mask_edit_mode=True)

    def _debounce_recombine(self) -> None:
        """Debounce rapid slider interactions before updating recombine composite."""
        if self._disposed or self.sidebar is None:
            return
        if self._recombine_timer is None:
            self._recombine_timer = QTimer(self.sidebar)
            self._recombine_timer.setSingleShot(True)
            self._recombine_timer.timeout.connect(self._apply_interactive_recombine)
        self._recombine_timer.start(FINISH_SLIDER_DEBOUNCE_MS)

    def _apply_interactive_recombine(self) -> None:
        """Execute fullres layer recombination outside GUI thread and update composite preview."""
        if self._is_recombine_slider_down():
            self._debounce_recombine()
            return
        if not self._result_guard()():
            return
        if not self._project or not self._project.source_is_current():
            return
        if (
            self._project.current_artifact_path(ROLE_SEPARATED_STARLESS) is None
            or self._project.current_artifact_path(ROLE_SEPARATED_STARS) is None
        ):
            return

        deliver_result = self._get_post_result()
        result_guard = self._result_guard()
        workflow = self.app.workflow

        def on_done():
            self.updateReadyStates()
            self._reset_preview_toggles()
            p = self._project.current_artifact_path(ROLE_FINISHED_COMPOSITE)
            if p:
                composite_file = OutputFile(basename=p.name, path=str(p), operation="Composite")
                self._last_output_file = composite_file
                self.sidebar.outputFiles.focus_file(composite_file)
                canvas = getattr(self.shell, "canvas_main", None)
                if canvas is not None and hasattr(canvas, "is_mask_edit_mode") and canvas.is_mask_edit_mode():
                    return
                self.showFile(composite_file, preserve_view=True, reload=True)

        def on_cancelled():
            pass

        def work():
            progress_updater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=100,
                desc="Recombining star and starless layers...",
                result_guard=result_guard,
            )
            result = workflow.do_recombine(progress_bar=progress_updater.tick)
            if result is not None:
                deliver_result(on_done)
            else:
                deliver_result(on_cancelled)

        accepted = self._enqueue_task(
            task_id="finish_recombine_preview",
            title="Recombine Layers",
            total=100,
            desc="Recombining star and starless layers...",
            work=work,
        )
        if not accepted:
            self._debounce_recombine()


__all__ = ["FinishView"]
