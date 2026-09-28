from typing import Optional
from PySide6.QtGui import (QPixmap, QGuiApplication)
from PySide6.QtCore import QThreadPool, QTimer, QPoint, Qt, QObject, Slot, QSignalBlocker
from PySide6.QtWidgets import (
    QWidget,
    QFileDialog,
    QMainWindow,
    QApplication,
    QMessageBox,
)
from functools import partial
import numpy as np

from startrails.app import App
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.progress_overlay import ProgressOverlay
from startrails.ui.signals import AsyncWorker, getSignals
from startrails.ui.sidebar import Sidebar
from startrails.ui.ui_interface import Ui_MainWindow
from startrails.ui.canvasLabel import CanvasLabel
from startrails.lib.file import File, InputFile, OutputFile


class MainWindow(QMainWindow):
    def __init__(self, app: App):
        QMainWindow.__init__(self)
        self.ui = Ui_AppWindow(app)
        self.ui.setupUi(self)
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

    def closeEvent(self, event):
        self.ui.doCancelOp()
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
    currentFile: File = None

    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.op_queue = QThreadPool()
        self.op_queue.setMaxThreadCount(1)
        self.enqueued_tasks = set()
        self.current_running_task = None

        self.readyInputImages = False
        self.readyStreaksRemoved = False
        self.readyManualStreaksRemoved = False
        self.progressOverlay = None
        self.progressBar = None
        self.label_progressBar = None
        self.pushButton_cancelOp = None

        settings = app.getWindowSettings()
        if settings is not None:
            self.persistentSettings = settings

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)
        self.setParent(MainWindow)
        self.sidebar = Sidebar(self.app, self)
        self.bodySplitter.setSizes([400, 1000])
        self.bodySplitter.setStretchFactor(0, 0)
        self.bodySplitter.setStretchFactor(1, 1)

        self.inputFiles = self.sidebar.inputs
        self.outputFiles = self.sidebar.outputs
        # Keep operation bindings local to the existing controller/queue.
        self.pushButton_newProject = self.sidebar.ui.newProject
        self.pushButton_openProject = self.sidebar.ui.openProject
        self.pushButton_stackImages = self.sidebar.stack.ui.run
        self.pushButton_removeStreaks = self.sidebar.detect.ui.run
        self.pushButton_exportMasks = self.sidebar.review.ui.masks
        self.pushButton_exportTraining = self.sidebar.review.ui.training
        self.checkBox_showDeletedMasks = self.sidebar.review.ui.showDeletedMasks
        self.pushButton_fillGaps = self.sidebar.fill.ui.run

        MainWindow.setWindowTitle("StarTrails AI")

        # Set window size
        screen_resolution = QGuiApplication.primaryScreen().availableGeometry()
        width = screen_resolution.width()
        height = screen_resolution.height()

        MainWindow.resize(int(width * 0.80), int(height * 0.90))
        MainWindow.center()

        # Bind events
        self.pushButton_newProject.clicked.connect(self.doNewProject)
        self.pushButton_openProject.clicked.connect(self.doOpenProject)
        self.inputFiles.addRequested.connect(self.selectInputFiles)
        self.pushButton_stackImages.clicked.connect(self.doStack)
        self.pushButton_removeStreaks.clicked.connect(self.doDetectStreaks)
        self.pushButton_exportMasks.clicked.connect(self.doExportMasks)
        self.pushButton_exportTraining.clicked.connect(self.doExportTrainingStreaks)
        self.pushButton_fillGaps.clicked.connect(self.doFillGaps)

        self.checkBox_showDeletedMasks.stateChanged.connect(self.onShowDeletedMasksChanged)

        self.signals = getSignals()
        self.signals.startProgress.connect(self.slotStartProgress)
        self.signals.incrementProgress.connect(self.slotIncrementProgressBar)
        self.signals.finishProgress.connect(self.slotFinishProgress)
        self.signals.updateFile.connect(self.slotUpdateFile)
        self.signals.showFile.connect(self.showFile)
        self.signals.fileMetadataChanged.connect(self.slotFileIndicators)
        self.signals.refreshReadiness.connect(self.slotRefreshReadiness)
        self.signals.drawInputFileList.connect(self.slotRefreshInputs)
        self.signals.drawOutputFileList.connect(self.slotRefreshOutputs)
        self.signals.findBrightestFrame.connect(self.doFindBrightFrame)
        self.signals.updateGPUStats.connect(self.slotUpdateGPUStats)

        # Replace placeholders
        self.canvas_main: CanvasLabel = replaceWidget(
            self.canvas_main,
            CanvasLabel("", QPixmap()))

        # Floating progress overlay over canvasHost
        self.progressOverlay = ProgressOverlay(self.canvasHost)
        self.progressBar = self.progressOverlay.progressBar
        self.label_progressBar = self.progressOverlay.label_progressBar
        self.pushButton_cancelOp = self.progressOverlay.pushButton_cancelOp
        self.pushButton_cancelOp.clicked.connect(self.doCancelOp)

        self.slotUpdateGPUStats()

        for section in (self.inputFiles, self.outputFiles):
            section.showFile.connect(self.showFile)
            section.removeFile.connect(self.slotRemoveFile)
            section.excludeFile.connect(self.slotExcludeFile)
            self.signals.focusFile.connect(section.focus_file)
        self.inputFiles.model.summaryChanged.connect(self.updateReadyStates)
        self.resetProjectView()

    @Slot()
    def updateReadyStates(self, _=None):
        self.readyInputImages = bool(self.app.getInputFileList())
        self.readyStreaksRemoved = bool(self.inputFiles.model.mask_files)
        self.readyManualStreaksRemoved = bool(self.inputFiles.model.manual_files)

        self.pushButton_stackImages.setEnabled(self.readyInputImages)
        self.pushButton_removeStreaks.setEnabled(self.readyInputImages)
        self.pushButton_exportMasks.setEnabled(self.readyStreaksRemoved)
        self.pushButton_exportTraining.setEnabled(self.readyManualStreaksRemoved)
        self.sidebar.stack.set_has_masks(self.readyStreaksRemoved)
        self.sidebar.detectCard.setSubtitle("Ready to detect streaks" if self.readyInputImages else "Add input files to begin")
        self.sidebar.stackCard.setSubtitle("Ready · detection is optional" if self.readyInputImages else "Add input files to begin")
        self.updateFillEligibility()
        self.sidebar.update_operations_progress(self.app, self.currentFile)

    def updateFillEligibility(self):
        eligible = isinstance(self.currentFile, OutputFile) and self.currentFile.operation == "Stacked"
        self.pushButton_fillGaps.setEnabled(eligible)
        self.sidebar.fillCard.setSubtitle("Ready to fill gaps" if eligible else "Select a stacked output image")
        self.sidebar.fill.ui.target.setText(self.currentFile.basename if eligible else "Select a stacked output image to fill its gaps.")
        self.sidebar.update_operations_progress(self.app, self.currentFile)

    def resetProjectView(self):
        self.showFile(None)
        self.inputFiles.set_files(self.app.getInputFileList())
        self.outputFiles.set_files(self.app.getOutputFileList())
        self.sidebar.reset_settings()
        self.updateReadyStates()
        files = self.app.getInputFileList() or self.app.getOutputFileList()
        if files:
            self.showFile(files[0])

    @Slot(File)
    def slotRefreshInputs(self, focus=None):
        self.inputFiles.set_files(self.app.getInputFileList())
        self.sidebar.refresh_inputs()
        self.updateReadyStates()
        if focus is not None:
            self.showFile(focus)

    @Slot(File)
    def slotRefreshOutputs(self, focus=None):
        self.outputFiles.model.sync_files(self.app.getOutputFileList())
        if focus is not None:
            self.showFile(focus)

    @Slot(File)
    def slotFileIndicators(self, file):
        self.inputFiles.model.update_file(file)
        self.outputFiles.model.update_file(file)

    @Slot()
    def slotRefreshReadiness(self):
        # Detection sends a preview only for every twentieth file. Reconcile all
        # metadata once at completion, without changing those preview events.
        self.inputFiles.model.refresh_annotations()

    def onShowDeletedMasksChanged(self, state):
        self.canvas_main.showDeletedMasks = bool(state)
        self.canvas_main.repaint()

    def slotUpdateGPUStats(self):
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

    @Slot(File)
    def slotUpdateFile(self, file: File):
        self.app.saveProject()
        self.signals.fileMetadataChanged.emit(file)

    @Slot(File)
    def slotRemoveFile(self, file: File):
        was_current = file is self.currentFile
        if isinstance(file, InputFile):
            if file not in self.app.getInputFileList():
                return
            self.app.removeInputFile(file)
            section = self.inputFiles
        elif isinstance(file, OutputFile):
            if file not in self.app.getOutputFileList():
                return
            self.app.removeOutputFile(file)
            section = self.outputFiles
        else:
            return
        with QSignalBlocker(section.ui.files.selectionModel()):
            section.model.remove_file(file)
        if was_current:
            self.showFile(None)
        self.sidebar.refresh_inputs()
        self.updateReadyStates()

    @Slot(File)
    def slotExcludeFile(self, file: InputFile):
        if file not in self.app.getInputFileList():
            return
        self.app.toggleExcludeFromStack(file)
        self.inputFiles.model.update_file(file)

    def enqueue_task(self, task_id: str, title: str, total: int, desc: str, work_func):
        if task_id in self.enqueued_tasks:
            return False

        self.enqueued_tasks.add(task_id)

        # Show the overlay immediately on the GUI thread if no other task is already running
        if len(self.enqueued_tasks) == 1:
            self.slotStartProgress(title, total, desc)

        def run_task():
            # If we start a task, we should show the overlay
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

    def slotIncrementProgressBar(self, progressUpdater: ProgressBarUpdater, total: int, increment: int, count: int, done: bool, data: Optional[File]):
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
                        rate = fmt_dict.get('rate') or (
                            progressUpdater.n / elapsed if elapsed > 0 else 0
                        )
                        remaining = (total - progressUpdater.n) / rate if rate > 0 else 0
                    except Exception:
                        pass
                desc = getattr(progressUpdater, "desc", "")
                n = getattr(progressUpdater, "n", count)
                self.progressOverlay.update_progress(
                    n, total,
                    elapsed=elapsed,
                    remaining=remaining,
                    desc=desc
                )
        if data is not None:
            if isinstance(data, np.ndarray):
                # In-memory preview update
                self.canvas_main.setFromNumpyArray(data, resetZoomAndPosition=False)
            elif isinstance(data, File):
                if isinstance(data, OutputFile):
                    self.outputFiles.model.sync_files(self.app.getOutputFileList())
                self.slotFileIndicators(data)
                self.showFile(data)
            else:
                raise ValueError(f"Unknown data type: {type(data)}")

    def selectInputFiles(self, *, clear=True):

        QApplication.processEvents()

        # Check if there are existing files and ask user whether to clear them
        existing_files = self.app.getInputFileList()
        if existing_files and clear:
            reply = QMessageBox.question(
                None,
                "Clear existing files?",
                f"There are {len(existing_files)} files already loaded.\n\nDo you want to clear existing files before adding new ones?",
                QMessageBox.StandardButton.Yes,
                QMessageBox.StandardButton.No,
            )
            clear = reply == QMessageBox.StandardButton.Yes

        fileNames, _ = QFileDialog.getOpenFileNames(filter="Image Files (*.jpg *.jpeg *.tif *.tiff)")
        if fileNames:
            self.app.addInputFiles(fileNames, clear=clear)
            if clear and isinstance(self.currentFile, InputFile):
                self.showFile(None)
            self.slotRefreshInputs()
            self.inputFiles.setExpanded(True)
            if self.currentFile is None:
                self.showFile(self.app.getInputFileList()[0])

        self.pushButton_stackImages.setEnabled(len(self.app.getInputFileList()) > 0)
        self.pushButton_removeStreaks.setEnabled(len(self.app.getInputFileList()) > 0)
        self.updateReadyStates()

    @Slot(File)
    def showFile(self, file: Optional[File]):
        self.currentFile = file
        self.canvas_main.setFile(file)
        self.label_imageName.setText(file.basename if file is not None else "")
        self.signals.focusFile.emit(file)
        self.updateFillEligibility()

    def doFindBrightFrame(self, file, x, y):
        files = self.app.getInputFileList()
        total = len(list(files))

        def f(fileList):
            total = len(list(fileList))
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=total, desc="Finding Brightest:")
            brightFile = self.app.doFindBrightFrame(x, y, file, progressUpdater.tick)
            if brightFile is not None:
                try:
                    self.signals.showFile.emit(brightFile)
                except RuntimeError:
                    pass

        self.enqueue_task(
            "findBrightFrame",
            "Find Brightest Frame",
            total,
            "Searching brightest frame...",
            partial(f, self.app.getInputFileList())
        )

    def doFillGaps(self):
        def f():
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=1, desc="Filling Gaps:")
            fileFillGaps = self.app.doFillGaps(self.currentFile, progressUpdater.tick)
            try:
                self.signals.refreshReadiness.emit()
                self.signals.drawOutputFileList.emit(fileFillGaps)
            except RuntimeError:
                pass

        self.enqueue_task(
            "fillGaps",
            "Fill Gaps",
            1,
            "Filling gaps...",
            f
        )

    def doStack(self, _=None):
        QApplication.processEvents()
        settings = self.sidebar.stack.values()
        if settings is None:
            return
        streaksRemoved = settings.pop("streaksRemoved")

        files = self.app.getInputFileList()
        total = len(list(files))

        def f(fileList):
            total = len(list(fileList))
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=total, desc="Stacking:")
            file = self.app.doStack(streaksRemoved, progressUpdater.tick, **settings)
            try:
                self.signals.drawOutputFileList.emit(file)
            except RuntimeError:
                pass

        self.enqueue_task(
            "stack",
            "Stack Images",
            total,
            f"Processing frame 1 of {total}",
            partial(f, self.app.getInputFileList())
        )

    def doExportTrainingStreaks(self):

        reply = QMessageBox.question(
            None,
            "Export training data",
            f"This process will export manually labeled streaks, deleted streaks, and random negative examples as training data as 512x512px cropped training images and labels. You can share these samples with the project or use them to train your own models.\n\nContinue?",
            QMessageBox.StandardButton.Yes,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        folderName = QFileDialog.getExistingDirectory(caption="Choose folder to save mask files")
        if not folderName:
            return
        files = self.app.getInputFileList()
        total = len(list(files))

        def f(folderName):
            total = len(list(self.app.getInputFileList()))
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=total, desc="Exporting Training Labels:")
            self.app.doExportTrainingStreaks(folderName, progressUpdater.tick)

        self.enqueue_task(
            "exportTraining",
            "Export Training Data",
            total,
            f"Exporting sample 1 of {total}",
            partial(f, folderName)
        )

    def doDetectStreaks(self):
        settings = self.sidebar.detect.values()
        if settings is None:
            return

        files = self.app.getInputFileList()
        total = len(list(files))

        def f(fileList):
            total = len(list(fileList))
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=total, desc="Removing Streaks:")
            self.app.doDetectStreaks(progressUpdater.tick, **settings)
            try:
                self.signals.refreshReadiness.emit()
            except RuntimeError:
                pass

        self.enqueue_task(
            "detectStreaks",
            "Detect Streaks",
            total,
            f"Processing frame 1 of {total}",
            partial(f, self.app.getInputFileList())
        )

    def doNewProject(self):
        QApplication.processEvents()
        file_path, _ = QFileDialog.getSaveFileName(
            None,
            "Create a New Project",
            "projects/new_project.project.json",
            "Project Files (*.project.json)"
        )

        if file_path:
            self.app.newProject(file_path)
            self.resetProjectView()

    def doOpenProject(self):
        QApplication.processEvents()
        fileName, _ = QFileDialog.getOpenFileName(dir="projects", filter="Project Files (*.project.json)")
        if fileName:
            self.app.loadProject(fileName)
            self.resetProjectView()

    def doExportMasks(self):
        folderName = QFileDialog.getExistingDirectory(caption="Choose folder to save mask files")
        if not folderName:
            return
        files = self.app.getInputFileList()
        total = len(list(files))

        def f(folderName):
            total = len(list(self.app.getInputFileList()))
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=total, desc="Exporting Training Labels:")
            self.app.doExportMaskedImages(folderName, progressUpdater.tick)

        self.enqueue_task(
            "exportMasks",
            "Export Artifacts",
            total,
            f"Exporting mask 1 of {total}",
            partial(f, folderName)
        )

    def doCancelOp(self):
        self.app.doInterruptOperation()
        if self.progressOverlay is not None:
            self.progressOverlay.label_progressBar.setText("Cancelling...")
            self.progressOverlay.pushButton_cancelOp.setEnabled(False)


def replaceWidget(placeHolder: QWidget, newWidget: QWidget):
    parentLayout = placeHolder.parent().layout()
    newWidget.setSizePolicy(placeHolder.sizePolicy())
    newWidget.setMinimumSize(placeHolder.minimumSize())
    parentLayout.replaceWidget(placeHolder, newWidget)
    placeHolder.setParent(None)
    placeHolder.deleteLater()
    return newWidget
