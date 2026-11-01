"""Finish mode view controller managing the sidebar and canvas interaction."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from startrails.lib.file import File
from startrails.lib.project_finish import FinishProject
from startrails.ui.sidebar_finish import SidebarFinish
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

    def resetProjectView(self) -> None:  # noqa: N802 - ModeView interface
        """Reset sidebar view state when a new or opened project is active."""
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
            else:
                canvas.setFile(None)
                self._displayed_source_id = None

        if self.sidebar is not None:
            self.sidebar.update_from_project(self._project, dimensions)
            self.sidebar.outputFiles.set_files(self.app.workflow.get_output_file_list())

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


__all__ = ["FinishView"]
