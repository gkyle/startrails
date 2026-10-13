from functools import partial
import logging
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING
import numpy as np
from PySide6.QtGui import (QPixmap, QGuiApplication)
from PySide6.QtCore import QThreadPool, QTimer, QPoint, Qt, QObject, Slot
from PySide6.QtWidgets import (
    QWidget,
    QFileDialog,
    QMainWindow,
    QApplication,
    QMessageBox,
)

from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.progress_overlay import ProgressOverlay
from startrails.ui.signals import AsyncWorker, getSignals
from startrails.ui.sidebar import Sidebar
from startrails.ui.ui_interface import Ui_MainWindow
from startrails.ui.canvasLabel import CanvasLabel
from startrails.ui.theme import system_theme, theme_palette
from startrails.lib.file import File, InputFile, OutputFile
from startrails.lib.project_type import (
    STARTRAILS_EXT,
    DENOISE_EXT,
    LEGACY_STARTRAILS_EXT,
    detect_project_type,
)
from startrails.ui.views.base import ModeView
from startrails.ui.views.startrails import StarTrailsView
from startrails.ui.views.denoise import DenoiseView

from startrails.app import App

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self, app: "App"):
        QMainWindow.__init__(self)
        theme = system_theme()
        self.ui = Ui_AppWindow(app)
        self.ui.setupUi(self)
        self.ui.canvasHost.setProperty("themeFixed", True)
        self.ui.canvasHost.setPalette(theme_palette(True))
        self.ui.canvas_main.setPalette(theme_palette(True))
        theme.register(self)
        self.show()

        # timer for updating GPU stats
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.ui.slotUpdateGPUStats)
        self.timer.start(5000)

    def center(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(QPoint(x, y))

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape and getattr(self.ui, "canvas_main", None) is not None:
            if getattr(self.ui.canvas_main, "findBrightestMode", False):
                self.ui.canvas_main.setFindBrightestMode(False)
                event.accept()
                return
        super().keyPressEvent(event)

    def closeEvent(self, event):
        self.ui.doCancelOp()
        if hasattr(self.ui, "active_view") and self.ui.active_view is not None:
            self.ui.active_view.teardown()
        if self.ui.op_queue is not None and hasattr(self.ui.op_queue, "clear"):
            self.ui.op_queue.clear()
            self.ui.op_queue.waitForDone(1000)
        self.ui.enqueued_tasks.clear()
        self.timer.stop()
        event.accept()


class Ui_AppWindow(QObject, Ui_MainWindow):
    app = None
    op_queue = None
    persistentSettings = {}
    currentFile: Optional[File] = None
    pushButton_findBrightest = None

    def __init__(self, app: "App"):
        super().__init__()
        self.app = app
        self.mainWindow: Optional[MainWindow] = None
        self.active_view: Optional[ModeView] = None
        self.current_project_token = object()
        self.op_queue = QThreadPool()
        self.op_queue.setMaxThreadCount(1)
        self.enqueued_tasks = set()
        self.current_running_task = None
        self.sourceLookupSession = None

        self.readyInputImages = False
        self.readyStreaksRemoved = False
        self.readyManualStreaksRemoved = False
        self.progressOverlay = None
        self.progressBar = None
        self.label_progressBar = None
        self.pushButton_cancelOp = None
        self.pushButton_findBrightest = None

        # Determine initial active view
        mode_name = "startrails"
        if hasattr(app, "workflow") and getattr(app.workflow, "mode_name", None):
            mode_name = app.workflow.mode_name
        elif hasattr(app, "project") and getattr(app, "project", None) is not None:
            try:
                mode_name = detect_project_type(app.project)
            except Exception:
                mode_name = "startrails"

        if mode_name == "denoise":
            self.active_view = DenoiseView(app, self)
        else:
            self.active_view = StarTrailsView(app, self)

        settings = getattr(app, "getWindowSettings", lambda: None)()
        if settings is not None:
            self.persistentSettings = settings

    def __setattr__(self, name: str, value: Any) -> None:
        super().__setattr__(name, value)
        if name == "sidebar" and hasattr(self, "active_view") and self.active_view is not None:
            if hasattr(self.active_view, "sidebar"):
                self.active_view.sidebar = value
        elif name == "inputFiles" and hasattr(self, "active_view") and self.active_view is not None:
            if hasattr(self.active_view, "inputFiles"):
                self.active_view.inputFiles = value
        elif name == "outputFiles" and hasattr(self, "active_view") and self.active_view is not None:
            if hasattr(self.active_view, "outputFiles"):
                self.active_view.outputFiles = value

    def __getattr__(self, name: str) -> Any:
        # Check active_view first for mode-specific widgets or methods
        view = self.__dict__.get("active_view")
        if view is not None and hasattr(view, name):
            return getattr(view, name)

        sidebar = self.__dict__.get("sidebar")
        if sidebar is None and view is not None:
            sidebar = getattr(view, "sidebar", None)

        if sidebar is not None:
            if hasattr(sidebar.ui, name):
                return getattr(sidebar.ui, name)
            if hasattr(sidebar, name):
                return getattr(sidebar, name)

            sections = [
                getattr(sidebar, "detect", None),
                getattr(sidebar, "stack", None),
                getattr(sidebar, "review", None),
                getattr(sidebar, "fill", None),
                getattr(sidebar, "tools", None),
                getattr(sidebar, "inputs", None),
                getattr(sidebar, "outputs", None),
                getattr(sidebar, "detectCard", None),
                getattr(sidebar, "stackCard", None),
                getattr(sidebar, "reviewCard", None),
                getattr(sidebar, "fillCard", None),
                getattr(sidebar, "toolsCard", None),
            ]
            for s in sections:
                if s is not None:
                    if hasattr(s, "ui") and hasattr(s.ui, name):
                        return getattr(s.ui, name)
                    if hasattr(s, name):
                        return getattr(s, name)

            prefix_map = [
                ("inputFiles", getattr(sidebar, "inputs", None)),
                ("outputFiles", getattr(sidebar, "outputs", None)),
                ("stepDetect", getattr(sidebar, "detectCard", None)),
                ("stepStack", getattr(sidebar, "stackCard", None)),
                ("stepReview", getattr(sidebar, "reviewCard", None)),
                ("stepFill", getattr(sidebar, "fillCard", None)),
                ("additionalTools", getattr(sidebar, "toolsCard", None)),
                ("detect", getattr(sidebar, "detect", None)),
                ("stack", getattr(sidebar, "stack", None)),
                ("review", getattr(sidebar, "review", None)),
                ("fill", getattr(sidebar, "fill", None)),
            ]
            for prefix, target in prefix_map:
                if target is not None and name.startswith(prefix):
                    remainder = name[len(prefix):]
                    if remainder:
                        cand = remainder[0].lower() + remainder[1:]
                        if hasattr(target, "ui"):
                            if hasattr(target.ui, cand):
                                return getattr(target.ui, cand)
                            if hasattr(target.ui, name):
                                return getattr(target.ui, name)
                        if hasattr(target, cand):
                            return getattr(target, cand)
                        if hasattr(target, name):
                            return getattr(target, name)

        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.setParent(MainWindow)
        self.mainWindow = MainWindow

        # Replace placeholders
        self.canvas_main: CanvasLabel = replaceWidget(
            self.canvas_main,
            CanvasLabel("", QPixmap()),
        )

        # Floating progress overlay over canvasHost
        self.progressOverlay = ProgressOverlay(self.canvasHost)
        self.progressBar = self.progressOverlay.progressBar
        self.label_progressBar = self.progressOverlay.label_progressBar
        self.pushButton_cancelOp = self.progressOverlay.pushButton_cancelOp
        self.pushButton_cancelOp.clicked.connect(self.doCancelOp)

        # Connect shared shell signals
        self.signals = getSignals()
        self.signals.startProgress.connect(self.slotStartProgress)
        self.signals.incrementProgress.connect(self.slotIncrementProgressBar)
        self.signals.finishProgress.connect(self.slotFinishProgress)
        self.signals.updateFile.connect(self.slotUpdateFile)
        self.signals.showFile.connect(self.showFile)
        self.signals.updateGPUStats.connect(self.slotUpdateGPUStats)

        # Set window size
        screen_resolution = QGuiApplication.primaryScreen().availableGeometry()
        width = screen_resolution.width()
        height = screen_resolution.height()
        MainWindow.resize(int(width * 0.80), int(height * 0.90))
        MainWindow.center()

        self.switch_to_project_mode()
        self.slotUpdateGPUStats()

    def set_view(self, mode_name: str, force: bool = False) -> None:
        """Switch active ModeView, reconstruct sidebar in bodySplitter, and rebind."""
        needs_rebuild = (
            force
            or (self.active_view is None)
            or (getattr(self.active_view, "sidebar_widget", None) is None)
            or (self.active_view.mode_name != mode_name)
        )
        if not needs_rebuild:
            self.active_view.resetProjectView()
            self._update_window_title(mode_name)
            return

        if self.active_view is not None:
            self.active_view.teardown()

        # Remove existing sidebar widget from splitter index 0 if switching modes
        if hasattr(self, "bodySplitter") and self.bodySplitter is not None:
            if self.bodySplitter.count() > 1:
                old_widget = self.bodySplitter.widget(0)
                if old_widget is not None and old_widget is not self.canvasHost:
                    if mode_name == "denoise" or not isinstance(old_widget, Sidebar):
                        old_widget.setParent(None)

        if mode_name == "denoise":
            self.active_view = DenoiseView(self.app, self)
        else:
            self.active_view = StarTrailsView(self.app, self)
        self.active_view.setParent(self)

        if hasattr(self, "bodySplitter") and self.bodySplitter is not None:
            sidebar_widget = self.active_view.build_sidebar(self.bodySplitter)
            if self.bodySplitter.indexOf(sidebar_widget) != 0:
                self.bodySplitter.insertWidget(0, sidebar_widget)
            self.sidebar = sidebar_widget
            self.inputFiles = getattr(self.active_view, "inputFiles", None)
            self.outputFiles = getattr(self.active_view, "outputFiles", None)
            self.pushButton_newProject = getattr(self.active_view, "pushButton_newProject", None)
            self.pushButton_openProject = getattr(self.active_view, "pushButton_openProject", None)
            self.pushButton_stackImages = getattr(self.active_view, "pushButton_stackImages", None)
            self.pushButton_removeStreaks = getattr(self.active_view, "pushButton_removeStreaks", None)
            self.pushButton_exportMasks = getattr(self.active_view, "pushButton_exportMasks", None)
            self.pushButton_exportTraining = getattr(self.active_view, "pushButton_exportTraining", None)
            self.checkBox_showDeletedMasks = getattr(self.active_view, "checkBox_showDeletedMasks", None)
            self.pushButton_findBrightest = getattr(self.active_view, "pushButton_findBrightest", None)
            self.pushButton_fillGaps = getattr(self.active_view, "pushButton_fillGaps", None)
            if mode_name == "denoise":
                sidebar_width = 370
                sidebar_widget.setMinimumSize(350, 0)
                sidebar_widget.setMaximumSize(450, 16777215)
                self.bodySplitter.setHandleWidth(4)
                self.bodySplitter.setSizes([sidebar_width, 1000])
                self.bodySplitter.setStretchFactor(0, 0)
                self.bodySplitter.setStretchFactor(1, 1)
                handle = self.bodySplitter.handle(1)
                if handle is not None:
                    handle.setEnabled(True)
            else:
                sidebar_widget.setMinimumSize(320, 0)
                sidebar_widget.setMaximumSize(320, 16777215)
                self.bodySplitter.setHandleWidth(0)
                self.bodySplitter.setSizes([320, 1000])
                self.bodySplitter.setStretchFactor(0, 0)
                self.bodySplitter.setStretchFactor(1, 1)
                handle = self.bodySplitter.handle(1)
                if handle is not None:
                    handle.setEnabled(False)

        self.active_view.bind()
        self.active_view.resetProjectView()
        self._update_window_title(mode_name)

    def _update_window_title(self, mode_name: str) -> None:
        title = "StarTrails AI — Denoise" if mode_name == "denoise" else "StarTrails AI"
        if self.mainWindow is not None:
            self.mainWindow.setWindowTitle(title)
        if hasattr(self, "label_4") and self.label_4 is not None:
            self.label_4.setText(title)

    def switch_to_project_mode(self) -> None:
        """Inspect app.workflow or app.project and configure the appropriate mode view."""
        self.current_project_token = object()
        mode_name = "startrails"
        if hasattr(self.app, "workflow") and getattr(self.app.workflow, "mode_name", None):
            mode_name = self.app.workflow.mode_name
        elif hasattr(self.app, "project") and getattr(self.app, "project", None) is not None:
            try:
                mode_name = detect_project_type(self.app.project)
            except Exception:
                mode_name = "startrails"
        self.set_view(mode_name)

    # -------------------------------------------------------------------------
    # Shared Task Queue & Progress Lifecycle
    # -------------------------------------------------------------------------

    def enqueue_task(self, task_id: str, title: str, total: int, desc: str, work_func):
        if task_id in self.enqueued_tasks:
            return False

        self.enqueued_tasks.add(task_id)
        task_token = self.current_project_token

        # Show the overlay immediately on the GUI thread if no other task is already running
        if len(self.enqueued_tasks) == 1:
            self.slotStartProgress(title, total, desc)

        def run_task():
            # Discard stale result if project changed prior to worker starting
            if task_token != self.current_project_token:
                self.enqueued_tasks.discard(task_id)
                return

            if hasattr(self.signals, "startProgress"):
                try:
                    self.signals.startProgress.emit(title, total, desc)
                except RuntimeError:
                    pass
            self.current_running_task = task_id
            try:
                work_func()
            finally:
                if self.current_running_task == task_id:
                    self.current_running_task = None
                self.enqueued_tasks.discard(task_id)

        worker = AsyncWorker(run_task)
        self.op_queue.start(worker)
        return True

    @Slot(object, object, object)
    def slotStartProgress(self, *args, **kwargs):
        title = kwargs.get("title", "Processing")
        total = kwargs.get("total", 0)
        desc = kwargs.get("desc", "")

        if len(args) == 1:
            if isinstance(args[0], int):
                total = args[0]
            else:
                desc = str(args[0])
        elif len(args) == 2:
            if isinstance(args[0], int):
                total = args[0]
                desc = str(args[1])
            else:
                title = str(args[0])
                if isinstance(args[1], int):
                    total = args[1]
                else:
                    desc = str(args[1])
        elif len(args) >= 3:
            title = str(args[0])
            total = int(args[1]) if args[1] is not None else 0
            desc = str(args[2])

        if self.progressOverlay is not None:
            self.progressOverlay.start(title=title, total=total, desc=desc)
        elif self.progressBar is not None:
            self.progressBar.setRange(0, total)
            self.progressBar.setValue(0)
            if self.label_progressBar is not None:
                self.label_progressBar.setText(desc)

    @Slot()
    def slotFinishProgress(self):
        if self.progressOverlay is not None:
            self.progressOverlay.finish()

    def slotIncrementProgressBar(
        self,
        progressUpdater: ProgressBarUpdater,
        total: int,
        increment: int,
        count: int,
        done: bool,
        data: Optional[File],
    ):
        progressUpdater.total = total
        progressUpdater.update(increment)
        if self.progressOverlay is not None:
            if done or (total > 0 and count >= total):
                self.progressOverlay.finish()
            else:
                elapsed = None
                remaining = None
                if hasattr(progressUpdater, "_time") and hasattr(progressUpdater, "start_t"):
                    try:
                        elapsed = progressUpdater._time() - progressUpdater.start_t
                        fmt_dict = getattr(progressUpdater, "format_dict", {}) or {}
                        rate = fmt_dict.get("rate") or (
                            progressUpdater.n / elapsed if elapsed > 0 else 0
                        )
                        remaining = (total - progressUpdater.n) / rate if rate > 0 else 0
                    except Exception:
                        pass
                desc = getattr(progressUpdater, "desc", "")
                n = getattr(progressUpdater, "n", count)
                self.progressOverlay.update_progress(
                    n, total, elapsed=elapsed, remaining=remaining, desc=desc
                )
        if data is not None:
            if isinstance(data, np.ndarray):
                # In-memory preview update
                if hasattr(self, "canvas_main") and self.canvas_main is not None:
                    self.canvas_main.setFromNumpyArray(data, resetZoomAndPosition=False)
            elif isinstance(data, File):
                output_files = getattr(self, "outputFiles", None)
                if output_files is not None and hasattr(output_files, "model"):
                    output_files.model.sync_files(self.app.getOutputFileList())
                self.slotFileIndicators(data)
                self.showFile(data)
            else:
                raise ValueError(f"Unknown data type: {type(data)}")

    def doCancelOp(self):
        if hasattr(self.app, "doInterruptOperation"):
            self.app.doInterruptOperation()
        if self.progressOverlay is not None:
            self.progressOverlay.label_progressBar.setText("Cancelling...")
            self.progressOverlay.pushButton_cancelOp.setEnabled(False)

    # -------------------------------------------------------------------------
    # Project File Operations
    # -------------------------------------------------------------------------

    def doNewProject(self):
        if self.enqueued_tasks or self.current_running_task is not None:
            QMessageBox.warning(
                None,
                "Operation in Progress",
                "Cannot create a new project while an operation is in progress. Please cancel or wait for it to complete.",
            )
            return

        QApplication.processEvents()
        filter_str = (
            f"StarTrails Project (*{STARTRAILS_EXT});;"
            f"Denoise Project (*{DENOISE_EXT});;"
            f"Legacy Project (*{LEGACY_STARTRAILS_EXT})"
        )
        file_path, selected_filter = QFileDialog.getSaveFileName(
            None,
            "Create a New Project",
            f"projects/new_project{STARTRAILS_EXT}",
            filter_str,
        )

        if file_path:
            path = Path(file_path)
            if not path.suffix:
                if DENOISE_EXT in selected_filter:
                    file_path = str(path.with_suffix(DENOISE_EXT))
                elif LEGACY_STARTRAILS_EXT in selected_filter:
                    file_path = str(path) + LEGACY_STARTRAILS_EXT
                else:
                    file_path = str(path.with_suffix(STARTRAILS_EXT))

            self.app.newProject(file_path)
            self.switch_to_project_mode()

    def doOpenProject(self):
        if self.enqueued_tasks or self.current_running_task is not None:
            QMessageBox.warning(
                None,
                "Operation in Progress",
                "Cannot open a project while an operation is in progress. Please cancel or wait for it to complete.",
            )
            return

        QApplication.processEvents()
        filter_str = (
            f"Supported Projects (*{STARTRAILS_EXT} *{DENOISE_EXT} *{LEGACY_STARTRAILS_EXT});;"
            f"StarTrails Project (*{STARTRAILS_EXT});;"
            f"Denoise Project (*{DENOISE_EXT});;"
            f"Legacy Project (*{LEGACY_STARTRAILS_EXT});;"
            "All Files (*)"
        )
        fileName, _ = QFileDialog.getOpenFileName(
            None,
            "Open Project",
            dir="projects",
            filter=filter_str,
        )
        if fileName:
            try:
                self.app.loadProject(fileName)
                self.switch_to_project_mode()
            except Exception as e:
                logger.error(f"Failed to open project {fileName}: {e}")
                QMessageBox.warning(None, "Open Project", f"Could not open project:\n{e}")

    # -------------------------------------------------------------------------
    # Shared File & View Delegations
    # -------------------------------------------------------------------------

    @Slot(File)
    def showFile(self, file: Optional[File]):
        self.currentFile = file
        if self.active_view is not None:
            self.active_view.showFile(file)
        else:
            if hasattr(self, "canvas_main") and self.canvas_main is not None:
                self.canvas_main.setFile(file)
            if hasattr(self, "label_imageName") and self.label_imageName is not None:
                self.label_imageName.setText(file.basename if file is not None else "")

    def resetProjectView(self):
        if self.active_view is not None:
            self.active_view.resetProjectView()

    @Slot()
    def updateReadyStates(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "updateReadyStates"):
            res = self.active_view.updateReadyStates(*args, **kwargs)
            self.readyInputImages = getattr(self.active_view, "readyInputImages", False)
            self.readyStreaksRemoved = getattr(self.active_view, "readyStreaksRemoved", False)
            self.readyManualStreaksRemoved = getattr(self.active_view, "readyManualStreaksRemoved", False)
            return res

    def updateFillEligibility(self):
        if self.active_view is not None and hasattr(self.active_view, "updateFillEligibility"):
            self.active_view.updateFillEligibility()

    @Slot(File)
    def slotUpdateFile(self, file: File):
        if hasattr(self.app, "saveProject"):
            self.app.saveProject()
        self.signals.fileMetadataChanged.emit(file)

    @Slot(File)
    def slotRefreshInputs(self, focus=None):
        if self.active_view is not None and hasattr(self.active_view, "slotRefreshInputs"):
            self.active_view.slotRefreshInputs(focus)

    @Slot(str, str)
    def slotSortInputFiles(self, sortBy: str, sortOrder: str):
        if self.active_view is not None and hasattr(self.active_view, "slotSortInputFiles"):
            self.active_view.slotSortInputFiles(sortBy, sortOrder)

    @Slot(File)
    def slotRefreshOutputs(self, focus=None):
        if self.active_view is not None and hasattr(self.active_view, "slotRefreshOutputs"):
            self.active_view.slotRefreshOutputs(focus)

    @Slot(File)
    def slotFileIndicators(self, file: File):
        if self.active_view is not None and hasattr(self.active_view, "slotFileIndicators"):
            self.active_view.slotFileIndicators(file)

    @Slot()
    def slotRefreshReadiness(self):
        if self.active_view is not None and hasattr(self.active_view, "slotRefreshReadiness"):
            self.active_view.slotRefreshReadiness()

    @Slot(File)
    def slotRemoveFile(self, file: File):
        if self.active_view is not None and hasattr(self.active_view, "slotRemoveFile"):
            self.active_view.slotRemoveFile(file)

    @Slot(File)
    def slotExcludeFile(self, file: InputFile):
        if self.active_view is not None and hasattr(self.active_view, "slotExcludeFile"):
            self.active_view.slotExcludeFile(file)

    def selectInputFiles(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "selectInputFiles"):
            return self.active_view.selectInputFiles(*args, **kwargs)

    def onShowDeletedMasksChanged(self, state):
        if self.active_view is not None and hasattr(self.active_view, "onShowDeletedMasksChanged"):
            self.active_view.onShowDeletedMasksChanged(state)
        elif hasattr(self, "canvas_main") and self.canvas_main is not None:
            self.canvas_main.showDeletedMasks = bool(state)
            self.canvas_main.repaint()

    # -------------------------------------------------------------------------
    # GPU Stats
    # -------------------------------------------------------------------------

    def slotUpdateGPUStats(self):
        if not hasattr(self.app, "gpuInfo") or self.app.gpuInfo is None:
            return
        gpu_data_available = self.app.gpuInfo.getGpuPresent()
        if gpu_data_available:
            self.frame_gpu_label.setVisible(False)
            gpu_utilization = self.app.gpuInfo.getGpuUtilization()
            if gpu_utilization is None:
                self.frame_gpu_util.setVisible(False)
            else:
                self.frame_gpu_util.setVisible(True)
                self.progressBar_gpu_util.setValue(gpu_utilization * 100)
                self.progressBar_gpu_util.setFormat(
                    "GPU: {:.0f}%".format(gpu_utilization * 100)
                )

            gpu_mem_total = self.app.gpuInfo.getGpuMemeoryTotal()
            gpu_mem_available = self.app.gpuInfo.getGpuMemoryAvailable()
            if gpu_mem_total is None:
                self.frame_gpu_mem.setVisible(False)
            else:
                mem_util = (gpu_mem_total - gpu_mem_available) / gpu_mem_total
                self.progressBar_gpu_mem.setValue(mem_util * 100)
                self.progressBar_gpu_mem.setFormat(
                    "GPU Mem: {:.0f}%  {:.1f}GB / {:.1f}GB".format(
                        mem_util * 100, (gpu_mem_total - gpu_mem_available), gpu_mem_total
                    )
                )

            gpu_data_available = (gpu_utilization is not None) or (gpu_mem_total is not None)

        if not gpu_data_available:
            self.frame_gpu_label.setVisible(True)
            self.frame_gpu_util.setVisible(False)
            self.frame_gpu_mem.setVisible(False)
            self.label_gpu.setText("NO GPU")

    # -------------------------------------------------------------------------
    # Forwarded Mode Operations & Review Sessions
    # -------------------------------------------------------------------------

    def doFillGaps(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "doFillGaps"):
            return self.active_view.doFillGaps(*args, **kwargs)

    def doStack(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "doStack"):
            return self.active_view.doStack(*args, **kwargs)

    def doExportTrainingStreaks(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "doExportTrainingStreaks"):
            return self.active_view.doExportTrainingStreaks(*args, **kwargs)

    def doDetectStreaks(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "doDetectStreaks"):
            return self.active_view.doDetectStreaks(*args, **kwargs)

    def doExportMasks(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "doExportMasks"):
            return self.active_view.doExportMasks(*args, **kwargs)

    def doFindBrightFrame(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "doFindBrightFrame"):
            return self.active_view.doFindBrightFrame(*args, **kwargs)

    def clearSourceLookup(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "clearSourceLookup"):
            return self.active_view.clearSourceLookup(*args, **kwargs)

    def slotSourceLookupReady(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "slotSourceLookupReady"):
            return self.active_view.slotSourceLookupReady(*args, **kwargs)

    def showSourceCandidate(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "showSourceCandidate"):
            return self.active_view.showSourceCandidate(*args, **kwargs)

    def restoreSourceView(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "restoreSourceView"):
            return self.active_view.restoreSourceView(*args, **kwargs)

    def nextSourceCandidate(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "nextSourceCandidate"):
            return self.active_view.nextSourceCandidate(*args, **kwargs)

    def backToSourceStack(self, *args, **kwargs):
        if self.active_view is not None and hasattr(self.active_view, "backToSourceStack"):
            return self.active_view.backToSourceStack(*args, **kwargs)


def replaceWidget(placeHolder: QWidget, newWidget: QWidget):
    parentLayout = placeHolder.parent().layout()
    newWidget.setSizePolicy(placeHolder.sizePolicy())
    newWidget.setMinimumSize(placeHolder.minimumSize())
    parentLayout.replaceWidget(placeHolder, newWidget)
    placeHolder.setParent(None)
    placeHolder.deleteLater()
    return newWidget
