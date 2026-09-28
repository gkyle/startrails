from typing import List, Any, Dict
import jsonpickle
import os

# Use deferred loading for torch and modules that use torch to reduce startup latency.
from deferred_import import deferred_import
torch = deferred_import('torch')
dsm = deferred_import('startrails.op.detectStreaks')
fgm = deferred_import('startrails.op.fillGaps')

try:
    import cupy
except:
    pass
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.util import Observable
from startrails.op.exportMaskedImages import ExportMaskedImages
from startrails.op.exportStreaksTraining import ExportStreaksDetectTraining
from startrails.lib.source_map import locate_sources, output_sidecar, relative_path
from startrails.op.stackImages import StackImages
from startrails.ui.project import Project
from startrails.lib.gpu import GPUInfo


class App:
    stateFile = "app.json"

    def __init__(self):
        try:
            torch.cuda.init()
        except Exception as e:
            pass
        self.loadAppState()
        self.loadProject(self.state["projectFile"])
        self.loadAppState()
        self.activeOperation: Observable = None
        self.gpuInfo = GPUInfo()

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

    def addInputFiles(self, paths: List[str], clear: bool = False) -> None:
        """Import one selection and persist once, keeping existing file objects."""
        added = [InputFile(os.path.basename(path), path) for path in sorted(paths)]
        if clear:
            self.project.rawInputFiles = []
        self.project.rawInputFiles.extend(added)
        self.sortInputFiles()

    def sortInputFiles(self) -> None:
        self.project.rawInputFiles.sort(key=lambda file: file.basename)
        self.saveProject()

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

    def appendOutputFile(self, basename, path, operation, fadeGradient=None) -> OutputFile:
        file = OutputFile(basename, path, operation, fadeGradient=fadeGradient)
        self.project.outputFiles.append(file)
        self.saveProject()
        return file

    def removeOutputFile(self, file: OutputFile) -> None:
        self.project.outputFiles.remove(file)
        self.saveProject()

    def doStack(self, satellitesRemoved, progressBar, fade=False, fadeAmount=(0.0, 0.0), batchSize=None, useGPU=True):
        stackImages = StackImages(useGPU)
        filteredInputFiles = list(filter(lambda file: not file.excludeFromStack, self.project.rawInputFiles))
        if not filteredInputFiles:
            raise ValueError("Include at least one input image in the stack.")
        outDir = self.project.projectFile.replace(".json", "")
        filename = StackImages.suggestOutFileName(filteredInputFiles[0], outDir)
        os.makedirs(outDir, exist_ok=True)

        fadeGradient = None
        if fade:
            fadeGradient = StackImages.makeFadeGradient(len(filteredInputFiles), fadeAmount)
        basename = os.path.basename(filename)
        file = self.appendOutputFile(basename, filename, "Stacked", fadeGradient=fadeGradient)
        stackImages.addObserver(progressBar)
        self.activeOperation = stackImages
        try:
            stackImages.stack(filteredInputFiles, file, satellitesRemoved, fade,
                              fadeGradient=fadeGradient, batchSize=batchSize)
        finally:
            self.activeOperation = None
            stackImages.removeObserver(progressBar)
        self.saveProject()
        return file

    def doDetectStreaks(self, progressBar, useGPU, confThreshold, mergeMethod, mergeThreshold):
        detectStreaks = dsm.DetectStreaks(useGPU)
        detectStreaks.addObserver(progressBar)
        self.activeOperation = detectStreaks
        try:
            detectStreaks.detectStreaks(self.getInputFileList(), confThreshold, mergeMethod, mergeThreshold)
        finally:
            self.activeOperation = None
            detectStreaks.removeObserver(progressBar)
        self.saveProject()

    def doFindBrightFrame(self, x, y, basisFile: OutputFile, progressBar):
        """Compatibility entry point for callers requesting just the best source."""
        result = self.locateSources(x, y, basisFile)
        return result.candidates[0] if result.candidates else None

    def locateSources(self, x, y, basisFile: OutputFile):
        # Consult the saved stack, including sources now excluded from future stacks.
        return locate_sources(basisFile, list(self.project.rawInputFiles), x, y)

    def doExportTrainingStreaks(self, outDir: str, progressBar):
        exportStreaksTraining = ExportStreaksDetectTraining()
        exportStreaksTraining.addObserver(progressBar)
        self.activeOperation = exportStreaksTraining
        try:
            exportStreaksTraining.cropAndLabelFiles(self.getInputFileList(), outDir)
        finally:
            self.activeOperation = None
            exportStreaksTraining.removeObserver(progressBar)

    def doExportMaskedImages(self, outDir: str, progressBar):
        exportMaskedImages = ExportMaskedImages()
        exportMaskedImages.addObserver(progressBar)
        self.activeOperation = exportMaskedImages
        try:
            exportMaskedImages.exportMaskedImages(self.getInputFileList(), outDir)
        finally:
            self.activeOperation = None
            exportMaskedImages.removeObserver(progressBar)

    def doFillGaps(self, file: OutputFile, progressBar):
        fillGaps = fgm.FillGaps()
        fillGaps.addObserver(progressBar)
        outDir = self.project.projectFile.replace(".json", "")
        filenameFillGaps, fileNameFillGapsMask = fgm.FillGaps.suggestOutFileName(file, outDir)
        fileFillGaps = self.appendOutputFile(
            os.path.basename(filenameFillGaps), filenameFillGaps, "FillGaps")
        fileFillGapsMask = self.appendOutputFile(
            os.path.basename(fileNameFillGapsMask), fileNameFillGapsMask, "FillGapsMask")
        self.activeOperation = fillGaps
        try:
            fillGaps.fillGaps(file, fileFillGaps, fileFillGapsMask)
        finally:
            self.activeOperation = None
            fillGaps.removeObserver(progressBar)
        fileFillGaps.fadeGradient = file.fadeGradient
        fileFillGapsMask.fadeGradient = file.fadeGradient
        if file.sourceMap and not fillGaps.shouldInterrupt():
            directory = os.path.dirname(os.path.abspath(fileFillGaps.path))
            fileFillGaps.sourceMap = relative_path(output_sidecar(file, "sourceMap"), directory)
            fileFillGaps.sourceStack = relative_path(file.path, directory)
            fileFillGaps.gapMask = relative_path(fileFillGapsMask.path, directory)
        self.saveProject()
        return fileFillGaps

    def doInterruptOperation(self):
        if self.activeOperation:
            self.activeOperation.requestInterrupt()

    def loadAppState(self):
        try:
            with open(self.stateFile, "r") as f:
                self.state = jsonpickle.decode(f.read())
        except Exception as e:
            print(e)
            self.state = {
                "projectFile": "projects/default.project.json",
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
        return StackImages.suggestBatchSize(file.path, gpuInfo=self.gpuInfo, useGPU=useGPU,
                                           sourceCount=len(self.getInputFileList()))
