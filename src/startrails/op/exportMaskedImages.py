from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from typing import List
import cv2

from startrails.lib.util import applyMask, imwrite, Observable
from startrails.lib.file import InputFile


class ExportMaskedImages(Observable):

    def exportMaskedImages(self, srcFiles: List[InputFile], outputDir):
        def process_file(file: InputFile) -> None:
            self.exportMaskedImage(file, outputDir)

        with ThreadPoolExecutor() as executor:
            jobLabel = "exportMaskedImages"
            self.startJob(jobLabel, len(srcFiles))
            futures = {executor.submit(process_file, file): file for file in srcFiles}
            for future in as_completed(futures):
                future.result()
                self.updateJob(jobLabel, 1)

    def exportMaskedImage(self, file: InputFile, outputDir):
        masks = file.streaksMasks + file.streaksManualMasks
        img = applyMask(cv2.imread(file.path), masks)
        basename = os.path.basename(file.path)
        outFileName = "{}/masked_{}".format(outputDir, basename)
        imwrite(outFileName, img)
