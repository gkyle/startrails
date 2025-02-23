import time
from typing import List, Any, Dict
import jsonpickle
import os

import torch
import GPUtil

from startrails.ui.file import InputFile, OutputFile
from startrails.op.detectStreaks import DetectStreaks
from startrails.op.fillGaps import FillGaps
from startrails.op.exportMaskedImages import ExportMaskedImages
from startrails.op.exportStreaksTraining import ExportStreaksDetectTraining
from startrails.op.findBrightFrame import FindBrightFrame
from startrails.op.stackImages import StackImages
from startrails.ui.project import Project


class App:
    stateFile = "app.json"

    def __init__(self):
        torch.cuda.init()
        self.loadAppState()
        self.loadProject(self.state["projectFile"])
        self.loadAppState()

    def getInputFileList(self) -> List[InputFile]:
        return self.project.rawInputFiles

    def clearInputFileList(self) -> None:
        self.project.rawInputFiles = []
        self.saveProject()

    def appendInputFile(self, basename: str, path: str) -> InputFile:
        file = InputFile(basename, path)
        self.project.rawInputFiles.append(file)
        self.saveProject()
        return file

    def removeInputFile(self, file: InputFile) -> None:
        self.project.rawInputFiles.remove(file)
        self.saveProject()

    def toggleExcludeFromStack(self, file: InputFile) -> None:
        file.excludeFromStack = not file.excludeFromStack
        self.saveProject()

    def getOutputFileList(self) -> List[OutputFile]:
        return self.project.outputFiles

    def clearOutputFileList(self) -> None:
        self.project.outputFiles = []
        self.saveProject()

    def appendOutputFile(self, basename, path, operation):
        file = OutputFile(basename, path, operation)
        self.project.outputFiles.append(file)
        self.saveProject()
        return file

    def removeOutputFile(self, file: OutputFile) -> None:
        self.project.outputFiles.remove(file)
        self.saveProject()

    def doStack(self, satellitesRemoved, progressBar, fade=False, fadeAmount=(0.0, 0.0), batchSize=None, useGPU=True):
        stackImages = StackImages(useGPU)
        filteredInputFiles = list(filter(lambda file: not file.excludeFromStack, self.project.rawInputFiles))
        paths = [file.path for file in filteredInputFiles]
        outDir = self.project.projectFile.replace(".json", "")
        filename = StackImages.suggestOutFileName(self.getInputFileList()[0], outDir)
        os.makedirs(outDir, exist_ok=True)

        fadeGradient = None
        if fade:
            fadeGradient = StackImages.makeFadeGradient(len(filteredInputFiles), fadeAmount)
        basename = os.path.basename(filename)
        file = self.appendOutputFile(basename, filename, "Stacked")
        stackImages.addObserver(progressBar)
        stackImages.stack(filteredInputFiles, file, satellitesRemoved, fade,
                          fadeGradient=fadeGradient, batchSize=batchSize)
        stackImages.removeObserver(progressBar)
        return file

    def doDetectStreaks(self, progressBar):
        detectStreaks = DetectStreaks()
        detectStreaks.addObserver(progressBar)
        detectStreaks.detectStreaks(self.getInputFileList())
        detectStreaks.removeObserver(progressBar)

    def doFindBrightFrame(self, x, y, progressBar):
        filteredInputFiles = list(filter(lambda file: not file.excludeFromStack, self.project.rawInputFiles))
        findBrightFrame = FindBrightFrame()
        findBrightFrame.addObserver(progressBar)
        file = findBrightFrame.findBrightFrame(filteredInputFiles, x, y)
        findBrightFrame.removeObserver(progressBar)
        return file

    def doExportTrainingStreaks(self, outDir: str, progressBar):
        exportStreaksTraining = ExportStreaksDetectTraining()
        exportStreaksTraining.addObserver(progressBar)
        exportStreaksTraining.cropAndLabelFiles(self.getInputFileList(), outDir)
        exportStreaksTraining.removeObserver(progressBar)

    def doExportMaskedImages(self, outDir: str, progressBar):
        exportMaskedImages = ExportMaskedImages()
        exportMaskedImages.addObserver(progressBar)
        exportMaskedImages.exportMaskedImages(self.getInputFileList(), outDir)
        exportMaskedImages.removeObserver(progressBar)

    def doFillGaps(self, file: OutputFile, progressBar):
        fillGaps = FillGaps()
        fillGaps.addObserver(progressBar)
        filenameFillGaps = file.path.replace("stacked-", "fillgaps-")
        fileNameFillGapsMask = file.path.replace("stacked-", "fillgaps_mask-")
        fileFillGapsMask = self.appendOutputFile(
            os.path.basename(fileNameFillGapsMask), fileNameFillGapsMask, "FillGapsMask")
        fileFillGaps = self.appendOutputFile(
            os.path.basename(filenameFillGaps), filenameFillGaps, "FillGaps")
        fillGaps.fillGaps(file, fileFillGaps, fileFillGapsMask)
        fillGaps.removeObserver(progressBar)
        return fileFillGaps

    def getGPUStats(self):
        if torch.cuda.is_available():
            gpu = GPUtil.getGPUs()
            return int(to_GB(gpu[0].memoryFree)), int(to_GB(gpu[0].memoryTotal))
        return None

    def loadAppState(self):
        try:
            with open(self.stateFile, "r") as f:
                self.state = jsonpickle.decode(f.read())
        except Exception as e:
            print(e)
            self.state = {
                "projectFile": "default_project.json",
            }

    def saveAppState(self):
        with open(self.stateFile, "w+") as f:
            f.write(jsonpickle.encode(self.state, indent=4))

    def loadProject(self, projectFile: str) -> None:
        try:
            with open(projectFile, "r") as f:
                self.project = jsonpickle.decode(f.read(), on_missing="error")
            self.state["projectFile"] = self.project.projectFile
            self.saveAppState()
        except Exception as e:
            print(e)
            self.project = Project()
            self.saveProject()

    def saveProject(self):
        with open(self.project.projectFile, "w+") as f:
            f.write(jsonpickle.encode(self.project, indent=4))
        self.state["projectFile"] = self.project.projectFile
        self.saveAppState()

    def getWindowSettings(self) -> Dict[str, Any]:
        if "window" not in self.state:
            self.state["window"] = {}
        return self.state["window"]

    def updateWindowSettings(self, window: Dict[str, Any]):
        self.state["window"] = window
        self.saveProject()

    def newProject(self, fileName: str):
        self.project = Project(projectFile=fileName)
        self.saveProject()

    def stackSuggestBatchSize(self, file: InputFile, useGPU=True):
        return StackImages.suggestBatchSize(file.path, useGPU=useGPU)


def to_GB(bytes):
    return bytes / (1024)
