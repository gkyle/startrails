
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
from PIL import Image
import numpy as np
from shapely import Point, Polygon

from startrails.lib.util import Observable
from startrails.lib.file import InputFile


class FindBrightFrame(Observable):

    # enumerate files, finding the file containing the brightest pixel at the given coordinates
    def findBrightFrame(self, srcFiles: List[InputFile], x, y, fadeGradient) -> str:
        def process_file(file: InputFile, idx: int) -> Tuple[str, float]:
            # exclude masked areas
            for mask in file.streaksMasks + file.streaksManualMasks:
                if len(mask) > 2:
                    polygon = Polygon(mask.tolist())
                    if polygon.contains(Point(x, y)):
                        return file, 0

            # scale image for faster processing
            img = Image.open(file.path)
            ws = img.width // r
            hs = img.height // r
            img.draft('BGR', (ws, hs))

            p = img.getpixel((x // r, y // r))
            mean = np.mean(np.array(p))

            # approximate impact of fadeGradient
            if not fadeGradient is None and fadeGradient[idx] != 1:
                mean = mean * fadeGradient[idx]

            return file, mean

        brightest = None
        brightestValue = 0
        self.startJob(len(srcFiles))
        r = 4

        with ThreadPoolExecutor() as executor:
            futures = {executor.submit(process_file, file, idx): file for idx, file in enumerate(srcFiles)}
            for future in as_completed(futures):
                file, mean = future.result()
                if mean > brightestValue:
                    brightest = file
                    brightestValue = mean
                self.updateJob(1, None)
                if self.shouldInterrupt():
                    return None
        return brightest
