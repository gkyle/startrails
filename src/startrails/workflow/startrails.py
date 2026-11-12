"""StarTrails workflow implementation containing star trail stacking and streak detection."""

from __future__ import annotations
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional
from concurrent.futures import CancelledError, ThreadPoolExecutor

from deferred_import import deferred_import
dsm = deferred_import("startrails.op.detectStreaks")
fgm = deferred_import("startrails.op.fillGaps")

from startrails.lib.file import (
    OP_FILL_GAPS,
    OP_FILL_GAPS_MASK,
    OP_STACKED_KEEP,
    OP_STACKED_REMOVE,
    InputFile,
    OutputFile,
    canonical_output,
)
from startrails.lib.source_map import locate_sources, output_sidecar, relative_path, signature
from startrails.op.exportMaskedImages import ExportMaskedImages
from startrails.op.exportStreaksTraining import ExportStreaksDetectTraining
from startrails.op.stackImages import StackImages
from startrails.workflow.base import Workflow

if TYPE_CHECKING:
    from startrails.app import App
    from startrails.lib.project import Project


class StarTrailsWorkflow(Workflow):
    """Workflow controller for the classic StarTrails stacking pipeline."""

    @property
    def mode_name(self) -> str:
        return "startrails"

    @property
    def project(self) -> Project:
        return self.app.project

    # -------------------------------------------------------------------------
    # Input file operations
    # -------------------------------------------------------------------------

    def getInputFileList(self) -> List[InputFile]:
        if not hasattr(self.project, "rawInputFiles"):
            return []
        return self.project.rawInputFiles

    get_input_file_list = getInputFileList

    def clearInputFileList(self) -> None:
        self.project.rawInputFiles = []
        self.save_project()

    clear_input_file_list = clearInputFileList

    def appendInputFile(self, basename: str, path: str) -> InputFile:
        file = InputFile(basename, path)
        self.project.rawInputFiles.append(file)
        self.sortInputFiles()
        return file

    append_input_file = appendInputFile

    def addInputFiles(self, paths: List[str], clear: bool = False) -> None:
        """Import one selection and persist once, keeping existing file objects."""
        def make_input(p):
            return InputFile(os.path.basename(p), p)

        if len(paths) > 16:
            with ThreadPoolExecutor(max_workers=16) as pool:
                added = list(pool.map(make_input, paths))
        else:
            added = [make_input(p) for p in paths]

        if clear:
            self.project.rawInputFiles = []
        self.project.rawInputFiles.extend(added)
        self.sortInputFiles()

    add_input_files = addInputFiles

    def sortInputFiles(self, sortBy: Optional[str] = None, sortOrder: Optional[str] = None) -> None:
        if sortBy is not None:
            self.project.sortBy = sortBy
        if sortOrder is not None:
            self.project.sortOrder = sortOrder

        sort_by = getattr(self.project, "sortBy", "date") or "date"
        sort_order = getattr(self.project, "sortOrder", "asc") or "asc"
        reverse = (sort_order.lower() == "desc")

        if sort_by in ("name", "filename"):
            self.project.rawInputFiles.sort(
                key=lambda file: (file.basename.lower() if file.basename else "", file.get_mtime()),
                reverse=reverse,
            )
        else:  # "date" default
            self.project.rawInputFiles.sort(
                key=lambda file: (file.get_mtime(), file.basename.lower() if file.basename else ""),
                reverse=reverse,
            )
        self.save_project()

    sort_input_files = sortInputFiles

    def removeInputFile(self, file: InputFile) -> None:
        self.project.rawInputFiles.remove(file)
        self.save_project()

    remove_input_file = removeInputFile

    def toggleExcludeFromStack(self, file: InputFile) -> None:
        file.excludeFromStack = not file.excludeFromStack
        self.save_project()

    toggle_exclude_from_stack = toggleExcludeFromStack

    # -------------------------------------------------------------------------
    # Output file operations
    # -------------------------------------------------------------------------

    def getOutputFileList(self) -> List[OutputFile]:
        if not hasattr(self.project, "outputFiles"):
            return []
        return self.project.outputFiles

    get_output_file_list = getOutputFileList

    def clearOutputFileList(self) -> None:
        self.project.outputFiles = []
        self.save_project()

    clear_output_file_list = clearOutputFileList

    def appendOutputFile(self, basename, path, operation, fadeGradient=None) -> OutputFile:
        file = OutputFile(basename, path, operation, fadeGradient=fadeGradient)
        self.project.outputFiles.append(file)
        self.save_project()
        return file

    append_output_file = appendOutputFile

    def removeOutputFile(self, file: OutputFile) -> None:
        self.project.outputFiles.remove(file)
        self.save_project()

    remove_output_file = removeOutputFile

    def _upsert_output_file(self, basename, path, operation, fadeGradient=None) -> OutputFile:
        """Return the record for a completed artifact without touching older results first."""
        target_path = os.path.abspath(path)
        existing = next(
            (
                f
                for f in self.project.outputFiles
                if isinstance(f, OutputFile) and os.path.abspath(f.path) == target_path
            ),
            None,
        )
        if existing is None:
            existing = canonical_output(self.project.outputFiles, operation)
        if existing is not None:
            existing.basename = basename
            existing.path = path
            existing.operation = operation
            existing.fadeGradient = fadeGradient
            existing.sourceMap = None
            existing.sourceStack = None
            existing.gapMask = None
            existing.source_stack_signature = None
            return existing
        file = OutputFile(basename, path, operation, fadeGradient=fadeGradient)
        self.project.outputFiles.append(file)
        return file

    def _output_extension(self, operation, fallback_path):
        existing = canonical_output(self.project.outputFiles, operation)
        path = existing.path if existing is not None else fallback_path
        return os.path.splitext(os.path.basename(path))[1]

    def _invalidate_fill_dependents(self, basis_path):
        """Drop fill records produced from a replaced stack while keeping their files."""
        basis = os.path.normcase(os.path.abspath(basis_path))
        retained = []
        for output in self.project.outputFiles:
            if not isinstance(output, OutputFile) or output.operation not in (OP_FILL_GAPS, OP_FILL_GAPS_MASK):
                retained.append(output)
                continue
            source = output_sidecar(output, "sourceStack")
            if source is None or os.path.normcase(os.path.abspath(source)) == basis:
                continue
            retained.append(output)
        self.project.outputFiles = retained

    # -------------------------------------------------------------------------
    # Stacking and Processing Operations
    # -------------------------------------------------------------------------

    def doStack(
        self,
        satellitesRemoved,
        progressBar,
        fade=False,
        fadeAmount=(0.0, 0.0),
        batchSize=None,
        useGPU=True,
    ) -> OutputFile:
        stackImages = StackImages(useGPU)
        filteredInputFiles = list(filter(lambda file: not file.excludeFromStack, self.project.rawInputFiles))
        if not filteredInputFiles:
            raise ValueError("Include at least one input image in the stack.")
        outDir = str(self.project.get_output_dir())
        operation = OP_STACKED_REMOVE if satellitesRemoved else OP_STACKED_KEEP
        extension = self._output_extension(operation, filteredInputFiles[0].path)
        filename = StackImages.suggestOutFileName(outDir, operation, extension)
        os.makedirs(outDir, exist_ok=True)

        fadeGradient = None
        if fade:
            fadeGradient = StackImages.makeFadeGradient(len(filteredInputFiles), fadeAmount)
        basename = os.path.basename(filename)
        file = OutputFile(basename, filename, operation, fadeGradient=fadeGradient)
        stackImages.addObserver(progressBar)
        self.app.activeOperation = stackImages
        try:
            stackImages.stack(
                filteredInputFiles,
                file,
                satellitesRemoved,
                fade,
                fadeGradient=fadeGradient,
                batchSize=batchSize,
            )
        finally:
            self.app.activeOperation = None
            stackImages.removeObserver(progressBar)
        self._invalidate_fill_dependents(filename)
        total_corrections = sum(
            len(getattr(f, "streaksManualMasks", [])) + len(getattr(f, "streaksManualDeletedMasks", []))
            for f in self.project.rawInputFiles
        )
        self.project.applied_corrections = total_corrections
        record = self._upsert_output_file(basename, filename, operation, fadeGradient=fadeGradient)
        record.sourceMap = file.sourceMap
        record.sourceStack = file.sourceStack
        record.gapMask = file.gapMask
        record.source_stack_signature = file.source_stack_signature
        self.save_project()
        return record

    do_stack = doStack

    def doDetectStreaks(self, progressBar, useGPU, confThreshold, mergeMethod, mergeThreshold) -> None:
        import startrails.app as app_module
        dsm_module = getattr(app_module, "dsm", getattr(self.app, "dsm", dsm))
        detectStreaks = dsm_module.DetectStreaks(useGPU)
        detectStreaks.addObserver(progressBar)
        self.app.activeOperation = detectStreaks
        try:
            detectStreaks.detectStreaks(self.getInputFileList(), confThreshold, mergeMethod, mergeThreshold)
        finally:
            self.app.activeOperation = None
            detectStreaks.removeObserver(progressBar)
        self.save_project()

    do_detect_streaks = doDetectStreaks

    def doFindBrightFrame(self, x, y, basisFile: OutputFile, progressBar) -> Optional[InputFile]:
        """Compatibility entry point for callers requesting just the best source."""
        result = self.locateSources(x, y, basisFile)
        return result.candidates[0] if result.candidates else None

    do_find_bright_frame = doFindBrightFrame

    def locateSources(self, x, y, basisFile: OutputFile) -> Any:
        return locate_sources(basisFile, list(self.project.rawInputFiles), x, y)

    locate_sources = locateSources

    def doExportTrainingStreaks(self, outDir: str, progressBar) -> None:
        exportStreaksTraining = ExportStreaksDetectTraining()
        exportStreaksTraining.addObserver(progressBar)
        self.app.activeOperation = exportStreaksTraining
        try:
            exportStreaksTraining.cropAndLabelFiles(self.getInputFileList(), outDir)
        finally:
            self.app.activeOperation = None
            exportStreaksTraining.removeObserver(progressBar)

    do_export_training_streaks = doExportTrainingStreaks

    def doContributeTrainingStreaks(
        self,
        progressBar,
        user_email: str | None = None,
        user_comments: str | None = None,
        client=None,
    ) -> dict:
        import tempfile
        from startrails.lib.contrib import ContributionClient, package_training_directory

        if client is None:
            client = ContributionClient()

        with tempfile.TemporaryDirectory() as temp_dir:
            exportStreaksTraining = ExportStreaksDetectTraining()
            exportStreaksTraining.addObserver(progressBar)
            self.app.activeOperation = exportStreaksTraining
            try:
                exportStreaksTraining.cropAndLabelFiles(self.getInputFileList(), temp_dir)
                if exportStreaksTraining.shouldInterrupt():
                    raise CancelledError("Streak training export cancelled")
                zip_bytes, _ = package_training_directory(temp_dir)
                return client.submit_bundle(
                    zip_bytes=zip_bytes,
                    user_email=user_email,
                    user_comments=user_comments,
                    app_version=getattr(self.app, "__version__", "0.1.1"),
                    is_cancelled=exportStreaksTraining.shouldInterrupt,
                )
            finally:
                self.app.activeOperation = None
                exportStreaksTraining.removeObserver(progressBar)

    do_contribute_training_streaks = doContributeTrainingStreaks

    def doExportMaskedImages(self, outDir: str, progressBar) -> None:
        exportMaskedImages = ExportMaskedImages()
        exportMaskedImages.addObserver(progressBar)
        self.app.activeOperation = exportMaskedImages
        try:
            exportMaskedImages.exportMaskedImages(self.getInputFileList(), outDir)
        finally:
            self.app.activeOperation = None
            exportMaskedImages.removeObserver(progressBar)

    do_export_masked_images = doExportMaskedImages

    def doFillGaps(self, file: OutputFile, progressBar) -> OutputFile:
        import startrails.app as app_module
        fgm_module = getattr(app_module, "fgm", getattr(self.app, "fgm", fgm))
        basis_signature = signature(file.path)
        fillGaps = fgm_module.FillGaps()
        fillGaps.addObserver(progressBar)
        outDir = str(self.project.get_output_dir())
        os.makedirs(outDir, exist_ok=True)
        fill_extension = self._output_extension(OP_FILL_GAPS, file.path)
        mask_extension = self._output_extension(OP_FILL_GAPS_MASK, file.path)
        filenameFillGaps, fileNameFillGapsMask = fgm_module.FillGaps.suggestOutFileName(
            outDir, fill_extension, mask_extension
        )
        fileFillGaps = OutputFile(os.path.basename(filenameFillGaps), filenameFillGaps, OP_FILL_GAPS)
        fileFillGapsMask = OutputFile(
            os.path.basename(fileNameFillGapsMask), fileNameFillGapsMask, OP_FILL_GAPS_MASK
        )
        self.app.activeOperation = fillGaps
        try:
            fillGaps.fillGaps(file, fileFillGaps, fileFillGapsMask)
        finally:
            self.app.activeOperation = None
            fillGaps.removeObserver(progressBar)
        directory = os.path.dirname(os.path.abspath(fileFillGaps.path))
        source_stack = relative_path(file.path, directory)
        fileFillGaps.fadeGradient = file.fadeGradient
        fileFillGapsMask.fadeGradient = file.fadeGradient
        fileFillGaps.sourceStack = source_stack
        fileFillGapsMask.sourceStack = source_stack
        fileFillGaps.source_stack_signature = basis_signature
        fileFillGapsMask.source_stack_signature = basis_signature
        if file.sourceMap:
            fileFillGaps.sourceMap = relative_path(output_sidecar(file, "sourceMap"), directory)
            fileFillGaps.gapMask = relative_path(fileFillGapsMask.path, directory)
        record = self._upsert_output_file(
            fileFillGaps.basename, fileFillGaps.path, fileFillGaps.operation,
            fadeGradient=fileFillGaps.fadeGradient,
        )
        record.sourceMap = fileFillGaps.sourceMap
        record.sourceStack = fileFillGaps.sourceStack
        record.gapMask = fileFillGaps.gapMask
        record.source_stack_signature = fileFillGaps.source_stack_signature
        mask_record = self._upsert_output_file(
            fileFillGapsMask.basename, fileFillGapsMask.path, fileFillGapsMask.operation,
            fadeGradient=fileFillGapsMask.fadeGradient,
        )
        mask_record.sourceMap = fileFillGapsMask.sourceMap
        mask_record.sourceStack = fileFillGapsMask.sourceStack
        mask_record.gapMask = fileFillGapsMask.gapMask
        mask_record.source_stack_signature = fileFillGapsMask.source_stack_signature
        self.save_project()
        return record

    do_fill_gaps = doFillGaps

    def stackSuggestBatchSize(self, file: InputFile, useGPU=True) -> int:
        return StackImages.suggestBatchSize(
            file.path,
            gpuInfo=self.app.gpuInfo,
            useGPU=useGPU,
            sourceCount=len(self.getInputFileList()),
        )

    stack_suggest_batch_size = stackSuggestBatchSize
