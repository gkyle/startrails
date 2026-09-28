from datetime import datetime
from copy import copy
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
import cv2
import psutil
import numpy
try:
    import cupy
except:
    pass

from startrails.lib.util import applyMask, Observable
from startrails.lib.file import InputFile, OutputFile
from startrails.lib.source_map import save_source_map, snapshot_sources, source_dtype
from startrails.lib.gpu import GPUInfo


USE_GPU_IF_AVAILABLE = True
MAX_BATCH_SIZE = 16


class StackImages(Observable):
    defaultBatchSize = 4

    def __init__(self, useGPU=True):
        super().__init__()
        self.useGPU = False

        # Use cupy instead of numpy if CUDA is available.
        try:
            if USE_GPU_IF_AVAILABLE and useGPU and cupy.is_available():
                self.useGPU = True
        except:
            pass

    def processBatch(self, inputImages, outImage, outfile, writeToFile=True):
        """Reduce (stable source ID, preprocessed image) pairs and their owners."""
        np = cupy if self.useGPU else numpy
        if outImage is not None:
            # Previous batch previews may still be queued on the GUI thread.
            outImage = np.array(outImage, copy=True)
        for source_id, image in inputImages:
            image = np.asarray(image)
            if outImage is None:
                outImage = np.zeros_like(image)
                self.sourceOwners = np.full(image.shape, numpy.iinfo(self.ownerDtype).max,
                                            dtype=self.ownerDtype)
            if image.shape != outImage.shape or image.dtype != outImage.dtype:
                raise ValueError("All input images must have the same dimensions and bit depth.")
            wins = (image > outImage) | ((image == outImage) & (image > 0)
                                        & (source_id < self.sourceOwners))
            self.sourceOwners[wins] = source_id
            np.maximum(outImage, image, out=outImage)
        if self.useGPU:
            outImage = cupy.asnumpy(outImage)
        if writeToFile:
            if not cv2.imwrite(outfile, outImage, [cv2.IMWRITE_JPEG_QUALITY, 100]):
                raise OSError(f"Could not write stacked image: {outfile}")
        return outImage

    def stack(self, srcFiles: List[InputFile], outfile: OutputFile, applyMasks=False, fade=False, fadeGradient=None, batchSize=None):
        if not srcFiles:
            raise ValueError("Include at least one input image in the stack.")
        batchSize = self.defaultBatchSize if batchSize is None else max(1, int(batchSize))
        self.batch = []
        self.sourceOwners = None
        self.ownerDtype = source_dtype(len(srcFiles))
        outfile.sourceMap = None
        sources = snapshot_sources(srcFiles, outfile)
        # Freeze preprocessing inputs before workers start. Later edits belong to
        # the next stack, not the output whose provenance is being recorded.
        inputs = []
        for file in srcFiles:
            snapshot = copy(file)
            snapshot.streaksMasks = [numpy.array(mask, copy=True) for mask in file.streaksMasks]
            snapshot.streaksManualMasks = [numpy.array(mask, copy=True) for mask in file.streaksManualMasks]
            inputs.append(snapshot)
        fadeGradient = list(fadeGradient) if fadeGradient is not None else None

        def processFile(file, idx):
            return self.preprocessImage(file, applyMasks, fade, fadeGradient, idx)

        max_workers = min(32, (os.cpu_count() or 1) + 4)
        completedCount = 0
        targetCount = len(inputs)
        outImg = None
        self.startJob(targetCount)
        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []
                next_index = 0
                while completedCount < targetCount and not self.shouldInterrupt():
                    while len(futures) < batchSize * 2 and next_index < targetCount:
                        futures.append(executor.submit(processFile, inputs[next_index], next_index))
                        next_index += 1
                    for future in as_completed(futures):
                        if self.shouldInterrupt():
                            break
                        source_id, result = future.result()
                        futures.remove(future)
                        self.batch.append((source_id, result))
                        completedCount += 1
                        if len(self.batch) == batchSize:
                            shouldWrite = completedCount % (batchSize * 8) == 0 or completedCount == targetCount
                            outImg = self.processBatch(self.batch, outImg, outfile.path, shouldWrite)
                            self.updateJob(len(self.batch), outfile if shouldWrite else outImg)
                            self.batch.clear()
                    if self.shouldInterrupt():
                        for future in futures:
                            future.cancel()
                        break
            if self.batch:
                outImg = self.processBatch(self.batch, outImg, outfile.path)
                self.updateJob(len(self.batch), outfile)
                self.batch.clear()
            elif outImg is not None and self.shouldInterrupt():
                # A cancelled stack may still be previewed, but has no complete map.
                if not cv2.imwrite(outfile.path, outImg, [cv2.IMWRITE_JPEG_QUALITY, 100]):
                    raise OSError(f"Could not write stacked image: {outfile.path}")
            if completedCount == targetCount and not self.shouldInterrupt():
                owners = cupy.asnumpy(self.sourceOwners) if self.useGPU else self.sourceOwners
                save_source_map(outfile, owners, sources, {
                    "apply_masks": bool(applyMasks), "fade": bool(fade),
                    "fade_gradient": fadeGradient, "tie_break": "first_source_in_stack_order",
                })
        finally:
            self.batch.clear()
            self.sourceOwners = None
            if self.useGPU:
                cupy.get_default_memory_pool().free_all_blocks()

    def preprocessImage(self, file: InputFile, applyMasks, fade, fadeGradient, idx):
        img = cv2.imread(file.path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Failed to load image: {file.path}")
        
        masks = None
        if applyMasks:
            masks = file.streaksMasks + file.streaksManualMasks

        # optionally apply masks
        if not masks is None:
            img = applyMask(img, masks)

        # optionally adjust exposure for fade
        if fade and fadeGradient[idx] != 1:
            img = cv2.addWeighted(img, fadeGradient[idx], img, 0, 0.0)

        return idx, img

    def makeFadeGradient(frameCount, fadeAmount=(0.0, 0.0)):
        fadeFrameStartCount = int(fadeAmount[0]*frameCount)
        fadeFrameEndCount = int(fadeAmount[1]*frameCount)

        fadeGradient = [1] * frameCount
        for i in range(0, fadeFrameStartCount):
            brightnessStart = (i+1)/fadeFrameStartCount
            fadeGradient[i] = brightnessStart

        for i in range(0, fadeFrameEndCount):
            brightnessEnd = (i+1)/fadeFrameEndCount
            fadeGradient[len(fadeGradient)-i-1] = brightnessEnd

        return fadeGradient

    def suggestOutFileName(file: InputFile, outDir: str):
        fileName = os.path.basename(file.path)
        baseName, extension = os.path.splitext(fileName)
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M-%S-%f")
        return "{}/stacked-{}-{}{}".format(outDir, baseName, ts, extension)

    def suggestBatchSize(path: str, gpuInfo: GPUInfo, useGPU=True, sourceCount=0):
        img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
        if img is None:
            raise ValueError(f"Failed to load image: {path}")
        bPerImage = img.nbytes
        provenanceBytes = img.size * numpy.dtype(source_dtype(sourceCount)).itemsize
        # Owner array plus comparison masks and a host copy for GPU publication.
        provenanceWorkingBytes = provenanceBytes * 2 + img.size * 3

        availableBytes = 0
        if useGPU:
            try:
                if cupy.cuda.is_available():
                    targetUtilization = 0.6
                    mempool = cupy.get_default_memory_pool()
                    mempool.free_all_blocks()

                    gpuMemoryAvailable = gpuInfo.getGpuMemoryAvailable()
                    if gpuMemoryAvailable is None:
                        availableBytes = 0
                    else:
                        availableBytes = gpuMemoryAvailable * 1024 * 1024 * 1024
            except Exception as e:
                pass

        # Fall back to RAM if GPU unavailable
        if availableBytes == 0:
            useGPU = False
            targetUtilization = 0.4
            memory = psutil.virtual_memory()
            availableBytes = memory.available

        availableImages = max(0, availableBytes * targetUtilization - provenanceWorkingBytes) // bPerImage

        # Number of images in memory = 4 * batchSize + 2.
        suggestedBatchSize = int((availableImages - 2) // 4)
        suggestedBatchSize = min(MAX_BATCH_SIZE, suggestedBatchSize)
        if suggestedBatchSize < 1:
            suggestedBatchSize = 1

        expectedMemoryUsed = int(((suggestedBatchSize*4+2) * bPerImage) + provenanceWorkingBytes)
        return suggestedBatchSize, expectedMemoryUsed, useGPU
