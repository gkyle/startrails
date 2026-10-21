"""StarTrails mode sidebar view and workflow controller."""

from __future__ import annotations
from functools import partial
import os
from typing import TYPE_CHECKING, Any, Optional
import numpy as np
from PySide6.QtCore import Slot, QSignalBlocker
from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget

from startrails.lib.file import File, InputFile, OutputFile
from startrails.lib.source_map import SourceLookup, SourceMapError
from startrails.ui.progress import ProgressBarUpdater
from startrails.ui.signals import getSignals
from startrails.ui.sidebar import Sidebar
from startrails.ui.views.base import ModeView

if TYPE_CHECKING:
    from startrails.app import App
    from startrails.ui.ui_wrap import Ui_AppWindow


class StarTrailsView(ModeView):
    """View controller managing the StarTrails sidebar, file lists, and stacking steps."""

    mode_name: str = "startrails"

    def __init__(self, app: App, shell: Any):
        super().__init__(app, shell)
        self._sidebar: Optional[Sidebar] = None
        self._inputFiles = None
        self._outputFiles = None

        self._pushButton_newProject = None
        self._pushButton_openProject = None
        self._pushButton_stackImages = None
        self._pushButton_removeStreaks = None
        self._pushButton_exportMasks = None
        self._pushButton_exportTraining = None
        self._checkBox_showDeletedMasks = None
        self._pushButton_findBrightest = None
        self._pushButton_fillGaps = None

        self.readyInputImages = False
        self.readyStreaksRemoved = False
        self.readyManualStreaksRemoved = False
        self.sourceLookupSession = None

    def _from_shell(self, name: str) -> Any:
        shell = getattr(self, "shell", None)
        if shell is not None and hasattr(shell, "__dict__"):
            return shell.__dict__.get(name)
        return None

    @property
    def sidebar(self) -> Optional[Sidebar]:
        if self._sidebar is not None:
            return self._sidebar
        return self._from_shell("sidebar")

    @sidebar.setter
    def sidebar(self, value: Optional[Sidebar]) -> None:
        self._sidebar = value
        self._init_sidebar_refs()

    @property
    def inputFiles(self):
        if self._inputFiles is not None:
            return self._inputFiles
        return self._from_shell("inputFiles")

    @inputFiles.setter
    def inputFiles(self, value):
        self._inputFiles = value

    @property
    def outputFiles(self):
        if self._outputFiles is not None:
            return self._outputFiles
        return self._from_shell("outputFiles")

    @outputFiles.setter
    def outputFiles(self, value):
        self._outputFiles = value

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
    def pushButton_stackImages(self):
        if self._pushButton_stackImages is not None:
            return self._pushButton_stackImages
        return self._from_shell("pushButton_stackImages")

    @pushButton_stackImages.setter
    def pushButton_stackImages(self, value):
        self._pushButton_stackImages = value

    @property
    def pushButton_removeStreaks(self):
        if self._pushButton_removeStreaks is not None:
            return self._pushButton_removeStreaks
        return self._from_shell("pushButton_removeStreaks")

    @pushButton_removeStreaks.setter
    def pushButton_removeStreaks(self, value):
        self._pushButton_removeStreaks = value

    @property
    def pushButton_exportMasks(self):
        if self._pushButton_exportMasks is not None:
            return self._pushButton_exportMasks
        return self._from_shell("pushButton_exportMasks")

    @pushButton_exportMasks.setter
    def pushButton_exportMasks(self, value):
        self._pushButton_exportMasks = value

    @property
    def pushButton_exportTraining(self):
        if self._pushButton_exportTraining is not None:
            return self._pushButton_exportTraining
        return self._from_shell("pushButton_exportTraining")

    @pushButton_exportTraining.setter
    def pushButton_exportTraining(self, value):
        self._pushButton_exportTraining = value

    @property
    def checkBox_showDeletedMasks(self):
        if self._checkBox_showDeletedMasks is not None:
            return self._checkBox_showDeletedMasks
        return self._from_shell("checkBox_showDeletedMasks")

    @checkBox_showDeletedMasks.setter
    def checkBox_showDeletedMasks(self, value):
        self._checkBox_showDeletedMasks = value

    @property
    def pushButton_findBrightest(self):
        if self._pushButton_findBrightest is not None:
            return self._pushButton_findBrightest
        return self._from_shell("pushButton_findBrightest")

    @pushButton_findBrightest.setter
    def pushButton_findBrightest(self, value):
        self._pushButton_findBrightest = value

    @property
    def pushButton_fillGaps(self):
        if self._pushButton_fillGaps is not None:
            return self._pushButton_fillGaps
        return self._from_shell("pushButton_fillGaps")

    @pushButton_fillGaps.setter
    def pushButton_fillGaps(self, value):
        self._pushButton_fillGaps = value

    def build_sidebar(self, parent: QWidget) -> QWidget:
        if self._sidebar is not None and self._sidebar.parent() is parent:
            return self._sidebar

        if hasattr(parent, "count") and parent.count() > 0:
            existing = parent.widget(0)
            if isinstance(existing, Sidebar):
                self._sidebar = existing
                if hasattr(self._sidebar, "init_app"):
                    self._sidebar.init_app(self.app)
                self.sidebar_widget = self._sidebar
                self._init_sidebar_refs()
                return self._sidebar

        self._sidebar = Sidebar(parent, app=self.app)
        self.sidebar_widget = self._sidebar
        self._init_sidebar_refs()
        return self._sidebar

    def _init_sidebar_refs(self) -> None:
        sb = self.sidebar
        if sb is None:
            return
        self.inputFiles = sb.inputs
        self.outputFiles = sb.outputs
        self.pushButton_newProject = getattr(sb.ui, "newProject", None)
        self.pushButton_openProject = getattr(sb.ui, "openProject", None)
        self.pushButton_stackImages = sb.stack.ui.run
        self.pushButton_removeStreaks = sb.detect.ui.run
        self.pushButton_exportMasks = sb.tools.ui.masks
        self.pushButton_exportTraining = sb.review.ui.training
        self.checkBox_showDeletedMasks = sb.review.ui.showDeletedMasks
        self.pushButton_findBrightest = getattr(sb.review.ui, "findBrightest", None)
        self.pushButton_fillGaps = sb.fill.ui.run

    def bind(self) -> None:
        if self.sidebar is None:
            return
        self._init_sidebar_refs()
        signals = getSignals()

        if self.pushButton_newProject is not None and hasattr(self.shell, "doNewProject"):
            self.connect_signal(self.pushButton_newProject.clicked, self.shell.doNewProject)
        if self.pushButton_openProject is not None and hasattr(self.shell, "doOpenProject"):
            self.connect_signal(self.pushButton_openProject.clicked, self.shell.doOpenProject)

        self.connect_signal(self.inputFiles.addRequested, self.selectInputFiles)
        self.connect_signal(self.pushButton_stackImages.clicked, self.doStack)
        self.connect_signal(self.pushButton_removeStreaks.clicked, self.doDetectStreaks)
        self.connect_signal(self.pushButton_exportMasks.clicked, self.doExportMasks)
        self.connect_signal(self.pushButton_exportTraining.clicked, self.doExportTrainingStreaks)
        self.connect_signal(self.pushButton_fillGaps.clicked, self.doFillGaps)
        self.connect_signal(self.checkBox_showDeletedMasks.stateChanged, self.onShowDeletedMasksChanged)

        self.connect_signal(signals.drawInputFileList, self.slotRefreshInputs)
        self.connect_signal(signals.drawOutputFileList, self.slotRefreshOutputs)
        self.connect_signal(signals.fileMetadataChanged, self.slotFileIndicators)
        self.connect_signal(signals.refreshReadiness, self.slotRefreshReadiness)
        self.connect_signal(signals.findBrightestFrame, self.doFindBrightFrame)
        self.connect_signal(signals.sourceLookupReady, self.slotSourceLookupReady)

        for section in (self.inputFiles, self.outputFiles):
            self.connect_signal(section.showFile, self.showFile)
            self.connect_signal(section.removeFile, self.slotRemoveFile)
            self.connect_signal(section.excludeFile, self.slotExcludeFile)
            self.connect_signal(signals.focusFile, section.focus_file)

        self.connect_signal(self.inputFiles.sortRequested, self.slotSortInputFiles)
        self.connect_signal(self.inputFiles.model.summaryChanged, self.updateReadyStates)

        self.connect_signal(self.sidebar.review.ui.nextSource.clicked, self.nextSourceCandidate)
        self.connect_signal(self.sidebar.review.ui.backToStack.clicked, self.backToSourceStack)

        if self.pushButton_findBrightest is not None and hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.connect_signal(self.pushButton_findBrightest.toggled, self.shell.canvas_main.setFindBrightestMode)
            self.connect_signal(self.shell.canvas_main.findBrightestModeChanged, self.pushButton_findBrightest.setChecked)

    def teardown(self) -> None:
        self.clearSourceLookup()
        super().teardown()
        if self.sidebar is not None:
            self.sidebar.setParent(None)

    # -------------------------------------------------------------------------
    # File View & Selection
    # -------------------------------------------------------------------------

    @Slot()
    def updateReadyStates(self, _=None):
        if self.inputFiles is None or self.sidebar is None:
            return
        self.readyInputImages = bool(self.app.getInputFileList())
        self.readyStreaksRemoved = bool(self.inputFiles.model.mask_files)
        self.readyManualStreaksRemoved = bool(self.inputFiles.model.manual_files)

        self.pushButton_stackImages.setEnabled(self.readyInputImages)
        self.pushButton_removeStreaks.setEnabled(self.readyInputImages)
        self.pushButton_exportMasks.setEnabled(self.readyStreaksRemoved)
        self.pushButton_exportTraining.setEnabled(self.readyManualStreaksRemoved)
        self.sidebar.stack.set_has_masks(self.readyStreaksRemoved)
        self.sidebar.detectCard.setSubtitle(
            "Ready to detect streaks" if self.readyInputImages else "Add input files to begin"
        )
        self.sidebar.stackCard.setSubtitle(
            "Ready · detection is optional" if self.readyInputImages else "Add input files to begin"
        )
        self.updateFillEligibility()
        self.sidebar.update_operations_progress(self.app, getattr(self.shell, "currentFile", None))

    def updateFillEligibility(self):
        if self.sidebar is None or self.pushButton_fillGaps is None:
            return
        current = getattr(self.shell, "currentFile", None)
        eligible = isinstance(current, OutputFile) and current.operation == "Stacked"
        self.pushButton_fillGaps.setEnabled(eligible)
        bright_eligible = (
            isinstance(current, OutputFile) and current.operation in ("Stacked", "FillGaps")
        )
        if self.pushButton_findBrightest is not None:
            self.pushButton_findBrightest.setEnabled(bright_eligible)
            if not bright_eligible and self.pushButton_findBrightest.isChecked():
                self.pushButton_findBrightest.setChecked(False)
        self.sidebar.fillCard.setSubtitle("Ready to fill gaps" if eligible else "Select a stacked output image")
        self.sidebar.fill.ui.target.setText(
            current.basename if eligible else "Select a stacked output image to fill its gaps."
        )
        self.sidebar.update_operations_progress(self.app, current)

    @Slot(File)
    def showFile(self, file: Optional[File]):
        if self.shell is not None and hasattr(self.shell, "showFile"):
            self.shell.showFile(file)

    def resetProjectView(self):
        self.clearSourceLookup()
        self.showFile(None)
        if self.inputFiles is None:
            return
        self.inputFiles.set_files(self.app.getInputFileList())
        sortBy = getattr(getattr(self.app, "project", None), "sortBy", "date") or "date"
        sortOrder = getattr(getattr(self.app, "project", None), "sortOrder", "asc") or "asc"
        self.inputFiles.set_sort_state(sortBy, sortOrder)
        self.outputFiles.set_files(self.app.getOutputFileList())
        self.sidebar.reset_settings()
        self.updateReadyStates()
        files = self.app.getInputFileList() or self.app.getOutputFileList()
        if files:
            self.showFile(files[0])

    @Slot(File)
    def slotRefreshInputs(self, focus=None):
        if self.inputFiles is None:
            return
        self.inputFiles.set_files(self.app.getInputFileList())
        sortBy = getattr(getattr(self.app, "project", None), "sortBy", "date") or "date"
        sortOrder = getattr(getattr(self.app, "project", None), "sortOrder", "asc") or "asc"
        self.inputFiles.set_sort_state(sortBy, sortOrder)
        self.sidebar.refresh_inputs()
        self.updateReadyStates()
        if focus is not None:
            self.showFile(focus)

    @Slot(str, str)
    def slotSortInputFiles(self, sortBy: str, sortOrder: str):
        if hasattr(self.app, "sortInputFiles"):
            self.app.sortInputFiles(sortBy=sortBy, sortOrder=sortOrder)
        self.slotRefreshInputs(focus=getattr(self.shell, "currentFile", None))

    @Slot(File)
    def slotRefreshOutputs(self, focus=None):
        if self.outputFiles is not None:
            self.outputFiles.model.sync_files(self.app.getOutputFileList())
        if focus is not None:
            self.showFile(focus)

    @Slot(File)
    def slotFileIndicators(self, file):
        if self.inputFiles is not None:
            self.inputFiles.model.update_file(file)
        if self.outputFiles is not None:
            self.outputFiles.model.update_file(file)

    @Slot()
    def slotRefreshReadiness(self):
        if self.inputFiles is not None:
            self.inputFiles.model.refresh_annotations()

    def onShowDeletedMasksChanged(self, state):
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.showDeletedMasks = bool(state)
            self.shell.canvas_main.repaint()

    @Slot(File)
    def slotRemoveFile(self, file: File):
        was_current = file is getattr(self.shell, "currentFile", None)
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
        if section is not None:
            with QSignalBlocker(section.ui.files.selectionModel()):
                section.model.remove_file(file)
        if was_current:
            self.showFile(None)
        if self.sidebar is not None:
            self.sidebar.refresh_inputs()
        self.updateReadyStates()

    @Slot(File)
    def slotExcludeFile(self, file: InputFile):
        if file not in self.app.getInputFileList():
            return
        self.app.toggleExcludeFromStack(file)
        if self.inputFiles is not None:
            self.inputFiles.model.update_file(file)

    def selectInputFiles(self, *, clear=True):
        QApplication.processEvents()
        clear = clear and self.confirm_clear_files(len(self.app.getInputFileList()))

        fileNames, _ = QFileDialog.getOpenFileNames(filter="Image Files (*.jpg *.jpeg *.tif *.tiff)")
        if fileNames:
            self.app.addInputFiles(fileNames, clear=clear)
            if clear and isinstance(getattr(self.shell, "currentFile", None), InputFile):
                self.showFile(None)
            self.slotRefreshInputs()
            if self.inputFiles is not None:
                self.inputFiles.setExpanded(True)
            if getattr(self.shell, "currentFile", None) is None and self.app.getInputFileList():
                self.showFile(self.app.getInputFileList()[0])

        if self.pushButton_stackImages is not None:
            self.pushButton_stackImages.setEnabled(len(self.app.getInputFileList()) > 0)
        if self.pushButton_removeStreaks is not None:
            self.pushButton_removeStreaks.setEnabled(len(self.app.getInputFileList()) > 0)
        self.updateReadyStates()

    @Slot(File)
    def showFile(self, file: Optional[File]):
        session = self.sourceLookupSession
        if session and file not in [session["basis"], *session["result"].candidates]:
            self.clearSourceLookup()
        if hasattr(self.shell, "currentFile"):
            self.shell.currentFile = file
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            self.shell.canvas_main.setFile(file)
        if hasattr(self.shell, "label_imageName") and self.shell.label_imageName is not None:
            self.shell.label_imageName.setText(file.basename if file is not None else "")
        signals = getSignals()
        if hasattr(signals, "focusFile"):
            signals.focusFile.emit(file)
        self.updateFillEligibility()

    # -------------------------------------------------------------------------
    # Source Map & Lookup
    # -------------------------------------------------------------------------

    def doFindBrightFrame(self, file, x, y):
        if not isinstance(file, OutputFile) or file.operation not in ("Stacked", "FillGaps"):
            return
        canvas = self.shell.canvas_main
        view = (canvas.zoom_factor, canvas.posX, canvas.posY)

        def lookup():
            try:
                result = self.app.locateSources(x, y, file)
            except SourceMapError as error:
                result = SourceLookup(message=str(error))
            signals = getSignals()
            signals.sourceLookupReady.emit((file, result, view))

        self.shell.enqueue_task(
            "findBrightFrame", "Locate Source", 0, "Reading saved source map...", lookup
        )

    def clearSourceLookup(self):
        self.sourceLookupSession = None
        if self.sidebar is not None:
            self.sidebar.review.ui.nextSource.setEnabled(False)
            self.sidebar.review.ui.backToStack.setEnabled(False)
            self.sidebar.review.ui.sourceLookupStatus.clear()

    @Slot(object)
    def slotSourceLookupReady(self, packet):
        basis, result, view = packet
        if basis not in self.app.getOutputFileList() or getattr(self.shell, "currentFile", None) is not basis:
            return
        self.clearSourceLookup()
        if self.sidebar is not None:
            self.sidebar.reviewCard.setExpanded(True)
            if not result.candidates:
                self.sidebar.review.ui.sourceLookupStatus.setText(result.message)
                return
        self.sourceLookupSession = dict(basis=basis, result=result, view=view, index=0)
        self.showSourceCandidate()

    def showSourceCandidate(self):
        session = self.sourceLookupSession
        if session is None:
            return
        candidates = session["result"].candidates
        file = candidates[session["index"]]
        if file not in self.app.getInputFileList():
            self.clearSourceLookup()
            if self.sidebar is not None:
                self.sidebar.review.ui.sourceLookupStatus.setText("This source is no longer in the project.")
            return
        self.showFile(file)
        self.restoreSourceView(session["view"])
        if self.sidebar is not None:
            self.sidebar.review.ui.nextSource.setEnabled(len(candidates) > 1)
            self.sidebar.review.ui.backToStack.setEnabled(True)
            status = f"Candidate {session['index'] + 1} of {len(candidates)}: {file.basename}"
            if session["result"].message:
                status += "\n" + session["result"].message
            self.sidebar.review.ui.sourceLookupStatus.setText(status)

    def restoreSourceView(self, view):
        if hasattr(self.shell, "canvas_main") and self.shell.canvas_main is not None:
            canvas = self.shell.canvas_main
            canvas.zoom_factor, canvas.posX, canvas.posY = view
            canvas.repaint()

    def nextSourceCandidate(self):
        session = self.sourceLookupSession
        if session:
            session["index"] = (session["index"] + 1) % len(session["result"].candidates)
            self.showSourceCandidate()

    def backToSourceStack(self):
        session = self.sourceLookupSession
        if session:
            if session["basis"] not in self.app.getOutputFileList():
                self.clearSourceLookup()
                return
            self.showFile(session["basis"])
            self.restoreSourceView(session["view"])

    # -------------------------------------------------------------------------
    # Long-Running Workflow Task Triggers
    # -------------------------------------------------------------------------

    def doFillGaps(self):
        signals = getSignals()

        def f():
            current = getattr(self.shell, "currentFile", None)
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=1,
                desc="Filling Gaps:",
            )
            fileFillGaps = self.app.doFillGaps(current, progressUpdater.tick)
            try:
                signals.refreshReadiness.emit()
                signals.drawOutputFileList.emit(fileFillGaps)
            except RuntimeError:
                pass

        self.shell.enqueue_task("fillGaps", "Fill Gaps", 1, "Filling gaps...", f)

    def doStack(self, _=None):
        QApplication.processEvents()
        if self.sidebar is None:
            return
        settings = self.sidebar.stack.values()
        if settings is None:
            return
        streaksRemoved = settings.pop("streaksRemoved")
        files = self.app.getInputFileList()
        total = len(list(files))
        signals = getSignals()

        def f(fileList):
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=total,
                desc="Stacking:",
            )
            file = self.app.doStack(streaksRemoved, progressUpdater.tick, **settings)
            try:
                signals.drawOutputFileList.emit(file)
            except RuntimeError:
                pass

        self.shell.enqueue_task(
            "stack",
            "Stack Images",
            total,
            f"Processing frame 1 of {total}",
            partial(f, self.app.getInputFileList()),
        )

    def doExportTrainingStreaks(self):
        reply = QMessageBox.question(
            None,
            "Export training data",
            "This process will export manually labeled streaks, deleted streaks, and random negative examples as training data as 512x512px cropped training images and labels. You can share these samples with the project or use them to train your own models.\n\nContinue?",
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
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=total,
                desc="Exporting Training Labels:",
            )
            self.app.doExportTrainingStreaks(folderName, progressUpdater.tick)

        self.shell.enqueue_task(
            "exportTraining",
            "Export Training Data",
            total,
            f"Exporting sample 1 of {total}",
            partial(f, folderName),
        )

    def doDetectStreaks(self):
        if self.sidebar is None:
            return
        settings = self.sidebar.detect.values()
        if settings is None:
            return

        files = self.app.getInputFileList()
        total = len(list(files))
        signals = getSignals()

        def f(fileList):
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=total,
                desc="Removing Streaks:",
            )
            self.app.doDetectStreaks(progressUpdater.tick, **settings)
            try:
                signals.refreshReadiness.emit()
            except RuntimeError:
                pass

        self.shell.enqueue_task(
            "detectStreaks",
            "Detect Streaks",
            total,
            f"Processing frame 1 of {total}",
            partial(f, self.app.getInputFileList()),
        )

    def doExportMasks(self):
        folderName = QFileDialog.getExistingDirectory(caption="Choose folder to save mask files")
        if not folderName:
            return
        files = self.app.getInputFileList()
        total = len(list(files))

        def f(folderName):
            progressUpdater = ProgressBarUpdater(
                getattr(self.shell, "progressBar", None),
                getattr(self.shell, "label_progressBar", None),
                total=total,
                desc="Exporting Training Labels:",
            )
            self.app.doExportMaskedImages(folderName, progressUpdater.tick)

        self.shell.enqueue_task(
            "exportMasks",
            "Export Artifacts",
            total,
            f"Exporting mask 1 of {total}",
            partial(f, folderName),
        )
