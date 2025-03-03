from datetime import datetime
import os
import time
import GPUtil
from threading import Semaphore
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
import cv2
import psutil
import numpy
try:
    import cupy
except:
    pass

from startrails.lib.util import applyMask, imwrite, Observable
from startrails.lib.file import InputFile, OutputFile


USE_GPU_IF_AVAILABLE = True


class StackImages(Observable):
    defaultBatchSize = 4  # Uses 1.4GB VRAM, but cupy may allocate more memory to the pool.

    def __init__(self, useGPU=True):
        super().__init__()
        self.useGPU = False

        # Use cupy instead of numpy if CUDA is available.
        try:
            if USE_GPU_IF_AVAILABLE and useGPU and cupy.is_available():
                self.useGPU = True
        except:
            pass

    def processBatch(self, inputImages: List[numpy.ndarray], outImage: numpy.ndarray, outfile: str) -> numpy.ndarray:
        if self.useGPU:
            np = cupy
        else:
            np = numpy

        if outImage is None:
            outImage = np.zeros(np.shape(inputImages[0]), dtype=np.uint8)

        images = outImage.reshape((1, ) + outImage.shape)
        for img in inputImages:
            images = np.append(images, img.reshape((1, ) + img.shape), axis=0)

        imageStack = np.stack(np.array(images), axis=0)
        imageMax = np.max(imageStack, axis=0)

        imwrite(outfile, imageMax)
        return imageMax

    def stack(self, srcFiles: List[InputFile], outfile: OutputFile, applyMasks=False, fade=False, fadeGradient=None, batchSize=None):
        self.batch = []
        if batchSize is None:
            batchSize = self.defaultBatchSize

        def processFile(file: InputFile, idx: int):
            return self.preprocessImage(file, applyMasks, fade, fadeGradient, idx)

        # limit number of concurrent / results-waiting tasks so we don't blow up memory
        semaphore = Semaphore(batchSize*2)

        with ThreadPoolExecutor() as executor:
            self.startJob(len(srcFiles))
            futures = []
            completedCount = 0
            targetCount = len(srcFiles)
            outImg = None
            i = 0

            while completedCount < targetCount:
                while semaphore._value > 0 and i < targetCount:
                    semaphore.acquire()
                    future = executor.submit(processFile, srcFiles[i], i)
                    futures.append(future)
                    i += 1

                # Process completed futures
                for future in as_completed(futures):
                    _, result = future.result()
                    futures.remove(future)
                    self.batch.append(result)
                    completedCount += 1
                    semaphore.release()

                    if completedCount % batchSize == 0:
                        outImg = self.processBatch(self.batch, outImg, outfile.path)
                        self.updateJob(len(self.batch), outfile)
                        self.batch.clear()

                if self.shouldInterrupt():
                    for future in futures:
                        future.cancel()
                    executor.shutdown()
                    break

                time.sleep(0.01)

            if self.batch:
                outImg = self.processBatch(self.batch, outImg, outfile.path)
                self.updateJob(len(self.batch), outfile)

            if self.useGPU:
                cupy.get_default_memory_pool().free_all_blocks()

    def preprocessImage(self, file: InputFile, applyMasks, fade, fadeGradient, idx):
        if self.useGPU:
            np = cupy
        else:
            np = numpy

        img = cv2.imread(file.path)
        masks = None
        if applyMasks:
            masks = file.streaksMasks + file.streaksManualMasks

        # optionally apply masks
        if not masks is None:
            img = applyMask(img, masks)

        # optionally adjust exposure for fade
        if fade and fadeGradient[idx] != 1:
            img = cv2.addWeighted(img, fadeGradient[idx], img, 0, 0.0)

        return idx, np.array(img)

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
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
        return "{}/stacked-{}-{}{}".format(outDir, baseName, ts, extension)

    def suggestBatchSize(path: str, useGPU=True):
        img = cv2.imread(path)
        h, w, c = numpy.shape(img)
        bPerImage = h*w*c

        availableBytes = 0
        if useGPU:
            try:
                if cupy.cuda.is_available():
                    TARGET_UTILIZATION = 0.6
                    mempool = cupy.get_default_memory_pool()
                    mempool.free_all_blocks()

                    gpu = GPUtil.getGPUs()
                    availableBytes = gpu[0].memoryFree * 1024 * 1024  # MB -> Bytes
            except Exception as e:
                pass

        # Fall back to RAM if GPU unavailable
        if availableBytes == 0:
            useGPU = False
            TARGET_UTILIZATION = 0.2
            memory = psutil.virtual_memory()
            availableBytes = memory.available

        availableImages = availableBytes * TARGET_UTILIZATION // bPerImage

        # Number of images in memory = 4 * batchSize + 2. (This calculation is accurate for GPU. We use additional RAM in both cases)
        suggestedBatchSize = int((availableImages - 2) // 4)
        expectedMemoryUsed = int(((suggestedBatchSize*4+2) * bPerImage))
        return suggestedBatchSize, expectedMemoryUsed, useGPU
