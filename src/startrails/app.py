from __future__ import annotations
import logging
import os
from typing import Any, Dict, List, Optional
import jsonpickle

# Use deferred loading for torch and modules that use torch to reduce startup latency.
from deferred_import import deferred_import
torch = deferred_import("torch")
dsm = deferred_import("startrails.op.detectStreaks")
fgm = deferred_import("startrails.op.fillGaps")

from startrails.lib.file import InputFile, OutputFile
from startrails.lib.util import Observable
from startrails.lib.project import Project
from startrails.lib.project_denoise import DenoiseProject
from startrails.lib.gpu import GPUInfo
from startrails.workflow.base import Workflow
from startrails.workflow.startrails import StarTrailsWorkflow
from startrails.workflow.denoise import DenoiseWorkflow

logger = logging.getLogger(__name__)


class App:
    stateFile = "app.json"

    def __init__(self):
        try:
            torch.cuda.init()
        except Exception:
            pass
        self.activeOperation: Optional[Observable] = None
        self.gpuInfo = GPUInfo()
        self._workflow: Optional[Workflow] = None

        self.loadAppState()

        # Ensure default denoise project exists on disk
        DenoiseProject.ensure_default_project("projects/default.proj_denoise")

        self.loadProject(self.state.get("projectFile", "projects/default.project.json"))
        self.loadAppState()

    @property
    def workflow(self) -> Workflow:
        wf = getattr(self, "_workflow", None)
        if wf is None:
            proj = getattr(self, "project", None)
            wf = self._create_workflow(proj)
            self._workflow = wf
        return wf

    @workflow.setter
    def workflow(self, wf: Workflow) -> None:
        self._workflow = wf

    def _create_workflow(self, project: Any) -> Workflow:
        if isinstance(project, DenoiseProject):
            return DenoiseWorkflow(self)
        return StarTrailsWorkflow(self)

    # -------------------------------------------------------------------------
    # Delegated StarTrails Workflow methods (backward compatibility)
    # -------------------------------------------------------------------------

    def getInputFileList(self) -> List[InputFile]:
        return getattr(self.workflow, "getInputFileList", lambda: [])()

    def clearInputFileList(self) -> None:
        if hasattr(self.workflow, "clearInputFileList"):
            self.workflow.clearInputFileList()

    def appendInputFile(self, basename: str, path: str) -> InputFile:
        return self.workflow.appendInputFile(basename, path)

    def addInputFiles(self, paths: List[str], clear: bool = False) -> None:
        self.workflow.addInputFiles(paths, clear=clear)

    def sortInputFiles(self, sortBy: Optional[str] = None, sortOrder: Optional[str] = None) -> None:
        if hasattr(self, "workflow") and self.workflow is not None:
            self.workflow.sortInputFiles(sortBy=sortBy, sortOrder=sortOrder)
            return

        # Fallback for standalone/mock callers like FakeApp in unittests
        project = getattr(self, "project", None)
        if project is None:
            return
        if sortBy is not None:
            project.sortBy = sortBy
        if sortOrder is not None:
            project.sortOrder = sortOrder

        sort_by = getattr(project, "sortBy", "date") or "date"
        sort_order = getattr(project, "sortOrder", "asc") or "asc"
        reverse = (sort_order.lower() == "desc")

        if sort_by in ("name", "filename"):
            project.rawInputFiles.sort(
                key=lambda file: (file.basename.lower() if file.basename else "", file.get_mtime()),
                reverse=reverse,
            )
        else:
            project.rawInputFiles.sort(
                key=lambda file: (file.get_mtime(), file.basename.lower() if file.basename else ""),
                reverse=reverse,
            )
        if hasattr(self, "saveProject"):
            self.saveProject()

    def removeInputFile(self, file: InputFile) -> None:
        self.workflow.removeInputFile(file)

    def toggleExcludeFromStack(self, file: InputFile) -> None:
        self.workflow.toggleExcludeFromStack(file)

    def getOutputFileList(self) -> List[OutputFile]:
        return getattr(self.workflow, "getOutputFileList", lambda: [])()

    def clearOutputFileList(self) -> None:
        if hasattr(self.workflow, "clearOutputFileList"):
            self.workflow.clearOutputFileList()

    def appendOutputFile(self, basename, path, operation, fadeGradient=None) -> OutputFile:
        return self.workflow.appendOutputFile(basename, path, operation, fadeGradient=fadeGradient)

    def removeOutputFile(self, file: OutputFile) -> None:
        self.workflow.removeOutputFile(file)

    def doStack(self, *args, **kwargs):
        return self.workflow.doStack(*args, **kwargs)

    def doDetectStreaks(self, *args, **kwargs):
        return self.workflow.doDetectStreaks(*args, **kwargs)

    def doFindBrightFrame(self, *args, **kwargs):
        return self.workflow.doFindBrightFrame(*args, **kwargs)

    def locateSources(self, *args, **kwargs):
        return self.workflow.locateSources(*args, **kwargs)

    def doExportTrainingStreaks(self, *args, **kwargs):
        return self.workflow.doExportTrainingStreaks(*args, **kwargs)

    def doExportMaskedImages(self, *args, **kwargs):
        return self.workflow.doExportMaskedImages(*args, **kwargs)

    def doFillGaps(self, *args, **kwargs):
        return self.workflow.doFillGaps(*args, **kwargs)

    def stackSuggestBatchSize(self, file: InputFile, useGPU=True):
        return self.workflow.stackSuggestBatchSize(file, useGPU=useGPU)

    # -------------------------------------------------------------------------
    # Core Application State & Project Management
    # -------------------------------------------------------------------------

    def doInterruptOperation(self):
        if self.activeOperation:
            self.activeOperation.requestInterrupt()

    def loadAppState(self):
        try:
            with open(self.stateFile, "r") as f:
                self.state = jsonpickle.decode(f.read())
        except Exception as e:
            logger.debug(f"Could not load stateFile {self.stateFile}: {e}")
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
        except Exception as e:
            logger.debug(f"Failed to load project {projectFile}: {e}")
            if projectFile.endswith(".proj_denoise"):
                self.project = DenoiseProject(projectFile=projectFile)
            else:
                self.project = Project(projectFile=projectFile)
            self.saveProject()

        self.workflow = self._create_workflow(self.project)

        if isinstance(self.project, Project):
            if not getattr(self.project, "sortBy", None):
                self.project.sortBy = "date"
            if not getattr(self.project, "sortOrder", None):
                self.project.sortOrder = "asc"
            if any(getattr(f, "timestamp", 0) == 0 for f in self.project.rawInputFiles):
                self.sortInputFiles()

        self.state["projectFile"] = self.project.projectFile
        self.saveAppState()

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
        if fileName.endswith(".proj_denoise"):
            self.project = DenoiseProject(projectFile=fileName)
        else:
            self.project = Project(projectFile=fileName)
        self.workflow = self._create_workflow(self.project)
        self.saveProject()
