import os
from PySide6.QtGui import (QPixmap, QGuiApplication)
from PySide6.QtCore import QThreadPool, QTimer, QPoint
from PySide6.QtWidgets import QWidget, QFileDialog, QMainWindow, QDialog, QApplication
from functools import partial

from startrails.app import App
from startrails.ui.dialog_detectStreaks import DetectStreaksDialog
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.signals import AsyncWorker, emitLater, getSignals
from startrails.ui.filestrip import FileButton, FileStrip
from startrails.ui.dialog_stackImages import FadeRadio, StackImagesDialog, StreaksRadio
from startrails.ui.ui_interface import Ui_MainWindow
from startrails.ui.canvasLabel import *
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
        self.timer.start(10000)

    def center(self):
        screen = QGuiApplication.primaryScreen().availableGeometry()
        window_size = self.geometry()
        x = (screen.width() - window_size.width()) // 2
        y = (screen.height() - window_size.height()) // 2
        self.move(QPoint(x, y))

    def resizeEvent(self, event):
        self.ui.observeResizeEvent(event)
        return super().resizeEvent(event)

    def moveEvent(self, event):
        self.ui.observeMoveEvent(event)
        return super().moveEvent(event)

    def closeEvent(self, event):
        self.timer.stop()
        event.accept()


class Ui_AppWindow(Ui_MainWindow):
    app = None
    op_queue = None
    persistentSettings = {}
    currentFile: File = None

    def __init__(self, app: App):
        super().__init__()
        self.app = app
        self.op_queue = QThreadPool()
        self.op_queue.setMaxThreadCount(1)

        self.readyInputImages = False
        self.readyStreaksRemoved = False
        self.readyManualStreaksRemoved = False

        settings = app.getWindowSettings()
        if settings is not None:
            self.persistentSettings = settings

    def setupUi(self, MainWindow):
        super().setupUi(MainWindow)

        MainWindow.setWindowTitle("StarStack AI")

        # Set window size
        screen_resolution = QGuiApplication.primaryScreen().availableGeometry()
        width = screen_resolution.width()
        height = screen_resolution.height()
        if "windowSize" in self.persistentSettings and self.persistentSettings["windowSize"] is not None:
            MainWindow.resize(self.persistentSettings["windowSize"])
            if "windowPosition" in self.persistentSettings:
                MainWindow.move(self.persistentSettings["windowPosition"])
            else:
                MainWindow.center()
        else:
            if width > 2000 and height > 1200:
                MainWindow.resize(width*0.6, height*0.6)
            else:
                MainWindow.resize(width*0.90, height*0.90)
            MainWindow.center()

        # Bind events
        self.frame_main.setStyleSheet("background-color:gray;")
        self.pushButton_newProject.clicked.connect(self.doNewProject)
        self.pushButton_openProject.clicked.connect(self.doOpenProject)
        self.pushButton_selectFiles.clicked.connect(self.selectInputFiles)
        self.pushButton_stackImages.clicked.connect(partial(self.doStack))
        self.pushButton_removeStreaks.clicked.connect(self.doDetectStreaks)
        self.pushButton_exportMasks.clicked.connect(self.doExportMasks)
        self.pushButton_exportTraining.clicked.connect(self.doExportTrainingStreaks)
        self.pushButton_fillGaps.clicked.connect(self.doFillGaps)

        self.signals = getSignals()
        self.signals.startProgress.connect(self.slotStartProgress)
        self.signals.incrementProgress.connect(self.slotIncrementProgressBar)
        self.signals.updateFile.connect(self.slotUpdateFile)
        self.signals.removeFile.connect(self.slotRemoveFile)
        self.signals.excludeFile.connect(self.slotExcludeFile)
        self.signals.showFile.connect(self.showFile)
        self.signals.updateFileButton.connect(self.updateReadyStates)
        self.signals.findBrightestFrame.connect(self.doFindBrightFrame)
        self.signals.updateGPUStats.connect(self.slotUpdateGPUStats)

        # Replace placeholders
        self.canvas_main: CanvasLabel = replaceWidget(
            self.canvas_main,
            CanvasLabel("", QPixmap()))

        self.slotUpdateGPUStats()

        self.inputFileStrip = FileStrip(self.frame_inputFiles, self.frame_inputFilesContainer, self.app.getInputFileList(),
                                        self.signals.drawInputFileList)
        self.outputFileStrip = FileStrip(self.frame_outputFiles, self.frame_outputFilesContainer, self.app.getOutputFileList(),
                                         self.signals.drawOutputFileList, maxVisibleButtons=3)
        self.signals.updateFileButton.connect(self.inputFileStrip.update)
        self.signals.updateFileButton.connect(self.outputFileStrip.update)

        self.updateReadyStates()

    def updateReadyStates(self, _=None):
        self.readyInputImages = False
        self.readyStreaksRemoved = False
        self.readyManualStreaksRemoved = False

        if len(self.app.getInputFileList()) > 0:
            self.readyInputImages = True

        for file in self.app.getInputFileList():
            if len(file.streaksMasks+file.streaksManualMasks) > 0:
                self.readyStreaksRemoved = True
            if len(file.streaksManualMasks) > 0:
                self.readyManualStreaksRemoved = True
                break

        self.pushButton_stackImages.setEnabled(self.readyInputImages)
        self.pushButton_removeStreaks.setEnabled(self.readyInputImages)
        self.pushButton_exportMasks.setEnabled(self.readyStreaksRemoved)
        self.pushButton_exportTraining.setEnabled(self.readyManualStreaksRemoved)

    def slotUpdateGPUStats(self):
        cudaStats = self.app.getGPUStats()
        if cudaStats is None:
            self.label_cuda.setText("NO GPU")
        else:
            self.label_cuda.setText("GPU: Free: {}GB | Total: {}GB".format(*cudaStats))

    def slotUpdateFile(self, file: File):
        self.app.saveProject()
        self.signals.updateFileButton.emit(file)

    def slotRemoveFile(self, file: File, button: FileButton):
        if isinstance(file, InputFile):
            self.app.removeInputFile(file)
            self.inputFileStrip.removeButton(file)
        elif isinstance(file, OutputFile):
            self.app.removeOutputFile(file)
            self.outputFileStrip.removeButton(file)
        self.app.saveProject()

    def slotExcludeFile(self, file: InputFile, button: FileButton):
        self.app.toggleExcludeFromStack(file)
        button.updateIndicators()
        self.app.saveProject()

    def slotStartProgress(self, total, text):
        self.progressBar.setRange(0, total)
        self.progressBar.setValue(0)
        self.label_progressBar.setText(text)

    def slotIncrementProgressBar(self, progressUpdater: ProgressBarUpdater, total: int, increment: int, count: int, done: bool, data: Optional[File]):
        progressUpdater.total = total
        progressUpdater.update(increment)
        if data is not None:
            if isinstance(data, File):
                self.showFile(data)
                self.inputFileStrip.update(data)
            else:
                raise ValueError("Unknown data type")

    def selectInputFiles(self, *, clear=True):
        QApplication.processEvents()
        fileNames, _ = QFileDialog.getOpenFileNames(filter="Image Files (*.jpg *.jpeg *.tif *.tiff)")
        if fileNames:
            if clear:
                self.app.clearInputFileList()
            fileNames = sorted(fileNames)
            for filepath in fileNames:
                basename = os.path.basename(filepath)
                self.app.appendInputFile(basename, filepath)
            self.inputFileStrip.setFileList(self.app.getInputFileList())

        self.pushButton_stackImages.setEnabled(len(self.app.getInputFileList()) > 0)
        self.pushButton_removeStreaks.setEnabled(len(self.app.getInputFileList()) > 0)
        self.updateReadyStates()

    def showFile(self, file: File):
        self.currentFile = file
        self.canvas_main.setFile(file)
        self.label_imageName.setText(file.basename)
        self.signals.focusFile.emit(file)

        fillGapsEligible = isinstance(file, OutputFile) and file.operation == "Stacked"
        self.pushButton_fillGaps.setEnabled(fillGapsEligible)

    def doFindBrightFrame(self, file, x, y):
        def f(fileList):
            total = len(list(fileList))
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=total, desc="Finding Brightest:")
            brightFile = self.app.doFindBrightFrame(x, y, file, progressUpdater.tick)
            if brightFile is not None:
                self.signals.showFile.emit(brightFile)

        worker = AsyncWorker(partial(f, self.app.getInputFileList()))
        self.op_queue.start(worker)

    def doFillGaps(self):
        def f():
            progressUpdater = ProgressBarUpdater(
                self.progressBar, self.label_progressBar, total=1, desc="Filling Gaps:")
            fileFillGaps = self.app.doFillGaps(self.currentFile, progressUpdater.tick)
            self.updateReadyStates()
            self.signals.drawOutputFileList.emit(fileFillGaps)

        worker = AsyncWorker(f)
        self.op_queue.start(worker)

    def doStack(self, _=None):
        dialog = StackImagesDialog(self.app, self.readyStreaksRemoved)
        result = dialog.exec()
        if result == QDialog.Accepted:
            streaksRemoved = dialog.ui.getStreaksRemoved() == StreaksRadio.REMOVE.value
            fade = dialog.ui.getFade() != FadeRadio.NONE.value
            fadeStart, fadeEnd = dialog.ui.getFadeAmount()
            batchSize = int(dialog.ui.lineEdit_batchSize.text())
            useGpu = dialog.ui.getUseGPU()

            def f(fileList):
                total = len(list(fileList))
                progressUpdater = ProgressBarUpdater(
                    self.progressBar, self.label_progressBar, total=total, desc="Stacking:")
                file = self.app.doStack(streaksRemoved, progressUpdater.tick, fade=fade,
                                        fadeAmount=(fadeStart / 100, fadeEnd / 100), batchSize=batchSize, useGPU=useGpu)
                self.signals.drawOutputFileList.emit(file)

            worker = AsyncWorker(partial(f, self.app.getInputFileList()))
            self.op_queue.start(worker)

    def doExportTrainingStreaks(self):
        def f(folderName):
            if folderName:
                total = len(list(self.app.getInputFileList()))
                progressUpdater = ProgressBarUpdater(
                    self.progressBar, self.label_progressBar, total=total, desc="Exporting Training Labels:")
                self.app.doExportTrainingStreaks(folderName, progressUpdater.tick)

        folderName = QFileDialog.getExistingDirectory(caption="Choose folder to save mask files")
        worker = AsyncWorker(partial(f, folderName))
        self.op_queue.start(worker)

    def doDetectStreaks(self):
        dialog = DetectStreaksDialog(self.app)
        result = dialog.exec()
        if result == QDialog.Accepted:
            mergeMethod = dialog.ui.getMergeMethod()
            useGPU = dialog.ui.getUseGPU()
            confThreshold = float(dialog.ui.lineEdit_confThreshold.text())
            mergeThreshold = float(dialog.ui.lineEdit_mergeThreshold.text())

            def f(fileList):
                total = len(list(fileList))
                progressUpdater = ProgressBarUpdater(
                    self.progressBar, self.label_progressBar, total=total, desc="Removing Streaks:")
                self.app.doDetectStreaks(progressUpdater.tick, useGPU=useGPU, confThreshold=confThreshold,
                                         mergeThreshold=mergeThreshold, mergeMethod=mergeMethod)
                self.updateReadyStates()

            worker = AsyncWorker(partial(f, self.app.getInputFileList()))
            self.op_queue.start(worker)

    def observeResizeEvent(self, event):
        self.persistentSettings["windowSize"] = event.size()
        self.app.updateWindowSettings(self.persistentSettings)

    def observeMoveEvent(self, event):
        self.persistentSettings["windowPosition"] = event.pos()
        self.app.updateWindowSettings(self.persistentSettings)

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
            self.canvas_main.setFile(None)
            self.inputFileStrip.setFileList(self.app.getInputFileList())
            self.outputFileStrip.setFileList(self.app.getOutputFileList())
            self.updateReadyStates()

    def doOpenProject(self):
        QApplication.processEvents()
        fileName, _ = QFileDialog.getOpenFileName(dir="projects", filter="Project Files (*.project.json)")
        if fileName:
            self.app.loadProject(fileName)
            self.canvas_main.setFile(None)
            self.inputFileStrip.setFileList(self.app.getInputFileList())
            self.outputFileStrip.setFileList(self.app.getOutputFileList())
            self.updateReadyStates()

    def doExportMasks(self):
        def f(folderName):
            if folderName:
                total = len(list(self.app.getInputFileList()))
                progressUpdater = ProgressBarUpdater(
                    self.progressBar, self.label_progressBar, total=total, desc="Exporting Training Labels:")
                self.app.doExportMaskedImages(folderName, progressUpdater.tick)

        folderName = QFileDialog.getExistingDirectory(caption="Choose folder to save mask files")
        worker = AsyncWorker(partial(f, folderName))
        self.op_queue.start(worker)


def replaceWidget(placeHolder: QWidget, newWidget: QWidget):
    parentLayout = placeHolder.parent().layout()
    placeHolder.setParent(None)
    placeHolder.deleteLater
    parentLayout.addWidget(newWidget)
    return newWidget
