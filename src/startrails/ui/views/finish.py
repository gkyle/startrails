"""Finish mode view controller managing the sidebar and canvas interaction."""

from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from PySide6.QtCore import QSignalBlocker, QTimer
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QWidget

from startrails.lib.denoise.defaults import DEFAULT_SKY_DETECTION_DEVICE
from startrails.lib.file import File
from startrails.lib.project_finish import FinishProject
from startrails.ui.sidebar_finish import SidebarFinish
from startrails.ui.sky_mask_controller import SkyMaskController
from startrails.ui.starnet_dialog import StarNetSetupDialog, StarNetTermsDialog, choose_existing_starnet
from startrails.ui.views.base import ModeView

if TYPE_CHECKING:
    from startrails.app import App


_SOURCE_IMAGE_FILTER = (
    "Supported Images (*.jpg *.jpeg *.tif *.tiff);;TIFF (*.tif *.tiff);;JPEG (*.jpg *.jpeg);;All Files (*)"
)


class FinishView(ModeView):
    """View controller managing the Finish sidebar, source image selection, and workflow actions."""

    mode_name: str = "finish"

    def __init__(self, app: App, shell: Any):
        super().__init__(app, shell)
        self._project: FinishProject = app.project
        self.sidebar: Optional[SidebarFinish] = None
        self._displayed_source_id: Optional[str] = None
        self._generation: int = 0
        self._disposed: bool = False
        self.mask_controller: Optional[SkyMaskController] = None

    def build_sidebar(self, parent: QWidget) -> QWidget:
        """Construct and return the Finish mode sidebar widget."""
        self.sidebar = SidebarFinish(parent, app=self.app)
        self.sidebar_widget = self.sidebar
        self.outputFiles = self.sidebar.outputFiles
        self.pushButton_newProject = self.sidebar.pushButton_newProject
        self.pushButton_openProject = self.sidebar.pushButton_openProject
        return self.sidebar

    def bind(self) -> None:
        """Connect UI signals, listeners, and workflow actions."""
        if self.sidebar is None:
            return

        self.connect_signal(self.sidebar.btn_import_source.clicked, self.on_import_source)
        self.connect_signal(self.sidebar.btn_replace_source.clicked, self.on_replace_source)
        self.connect_signal(self.sidebar.btn_save_output.clicked, self.on_save_output)
        self.connect_signal(self.sidebar.outputFiles.showFile, self.showFile)

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

    def teardown(self) -> None:
        """Disconnect signals and clean up canvas and mask controller state."""
        self._disposed = True
        self._generation += 1
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

        def run():
            if not guard():
                return
            try:
                with workflow.operation_session():
                    work()
            except CancelledError:
                self._post_result(guard, lambda: self._show_task_error(task_id, "Cancelled"))
            except Exception as error:
                message = str(error)
                self._post_result(guard, lambda: self._show_task_error(task_id, f"Failed: {message}"))

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
        if self.sidebar is not None and hasattr(self.sidebar, "skySettings"):
            self.sidebar.skySettings.ui.error.setText(message)
            self.sidebar.skySettings.ui.error.show()

    def resetProjectView(self) -> None:  # noqa: N802 - ModeView interface
        """Reset sidebar view state when a new or opened project is active."""
        self._generation += 1
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
            self.sidebar.outputFiles.set_files(self.app.workflow.get_output_file_list())
            if hasattr(self.sidebar, "skySettings"):
                self.sidebar.skySettings.set_from_project(self._project)

        self.updateReadyStates()

    def showFile(self, file: Optional[File]) -> None:  # noqa: N802 - ModeView interface
        """Handle preview display on the canvas."""
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFile(file)

    def updateReadyStates(self, _=None) -> None:  # noqa: N802 - ModeView interface
        """Update button enabled states and prerequisite subtitles based on project readiness."""
        if self.sidebar is not None and isinstance(self._project, FinishProject):
            self.sidebar.update_prerequisites(self._project)

    def on_import_source(self) -> None:
        """Prompt user for a source image and import it into the project."""
        fileName, _ = QFileDialog.getOpenFileName(
            self.sidebar,
            "Import Source Image",
            dir=str(self._project.get_output_dir().parent),
            filter=_SOURCE_IMAGE_FILTER,
        )
        if fileName:
            try:
                self.app.workflow.do_import_source(fileName)
                self.resetProjectView()
            except Exception as e:
                QMessageBox.critical(self.sidebar, "Import Error", f"Failed to import source image:\n{e}")

    def on_replace_source(self) -> None:
        """Prompt user for a replacement source image."""
        fileName, _ = QFileDialog.getOpenFileName(
            self.sidebar,
            "Replace Source Image",
            dir=str(Path(self._project.source_file.path).parent) if self._project.source_file else None,
            filter=_SOURCE_IMAGE_FILTER,
        )
        if fileName:
            try:
                self.app.workflow.do_replace_source(fileName)
                self.resetProjectView()
            except Exception as e:
                QMessageBox.critical(self.sidebar, "Replace Error", f"Failed to replace source image:\n{e}")

    def on_save_output(self) -> None:
        """Export composite or current result to destination path."""
        if not getattr(self._project, "source_file", None):
            QMessageBox.information(self.sidebar, "Save Image", "Please import a source image first.")
            return

        default_export = self._project.get_default_export_path()
        filter_str = f"Image (*{default_export.suffix});;All Files (*)"
        fileName, _ = QFileDialog.getSaveFileName(
            self.sidebar,
            "Save Finished Image",
            str(default_export),
            filter_str,
        )
        if fileName:
            try:
                out = self.app.workflow.do_export_composite(output_path=fileName)
                self.resetProjectView()
                QMessageBox.information(self.sidebar, "Image Saved", f"Successfully saved:\n{out}")
            except Exception as e:
                QMessageBox.critical(self.sidebar, "Export Error", f"Failed to save image:\n{e}")

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


__all__ = ["FinishView"]
