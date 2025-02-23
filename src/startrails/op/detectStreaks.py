from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
import cv2
from skimage.draw import polygon
import numpy as np

from ultralytics import YOLO
from sahi.utils.torch import is_torch_cuda_available
from sahi.postprocess.combine import NMSPostprocess, NMMPostprocess, GreedyNMMPostprocess
from sahi.prediction import ObjectPrediction
from sahi.annotation import Mask
from sahi.slicing import slice_image
from typing import List

from startrails.lib.util import Observable
from startrails.ui.file import InputFile

USE_GPU_IF_AVAILABLE = True

SAHI_CONFIDENCE_THRESHOLD = 0.3
SAHI_OVERLAP = 0.2

STREAKS_MODEL_PATH = "../models/detectStreaks/streaks.pt"
DETECT_BATCH_SIZE = 2
ROI_SIZE = 512


class DetectStreaks(Observable):
    def __init__(self):
        super().__init__()
        pass

    def detectStreaks(self, srcFiles: List[InputFile]):
        model = YOLO(STREAKS_MODEL_PATH, verbose=False)

        def processFile(file: InputFile):
            return self.detectStreaksInImage(model, file)

        total = len(srcFiles)
        completed = 0
        showIncrement = total // 20
        jobLabel = "removeStreaks"
        self.startJob(jobLabel, len(srcFiles))
        with ThreadPoolExecutor(max_workers=DETECT_BATCH_SIZE) as executor:
            futures = {executor.submit(processFile, file): file for file in srcFiles}
            for future in as_completed(futures):
                try:
                    result = future.result()
                    if completed % showIncrement == 0:
                        self.updateJob(jobLabel, 1, result)
                    else:
                        self.updateJob(jobLabel, 1, None)
                    completed += 1

                except Exception as e:
                    print(f"Error retrieving result: {e}")

    # This is faster than SAHI get_sliced_prediction because:
    # - Uses YOLO model batched processing
    # - Does not build / use expensive masks when not needed
    def detectStreaksInImage(self, model, file: InputFile, postProcessMethod="NMS", postProcessMetric="IOU") -> InputFile:
        img = cv2.imread(file.path)

        # sliced predictions
        sliceImageResult = getSlices(img, ROI_SIZE, ROI_SIZE, SAHI_OVERLAP, SAHI_OVERLAP)
        images = []
        for image in sliceImageResult.sliced_image_list:
            images.append(image.image)

        yoloBatchResults = model(images, conf=SAHI_CONFIDENCE_THRESHOLD,
                                 device='cuda:0' if USE_GPU_IF_AVAILABLE and is_torch_cuda_available() else 'cpu',
                                 verbose=False)
        sahiPredictions = []
        objectPredictions = []
        for i in range(len(sliceImageResult.sliced_image_list)):
            sahiPrediction = yolo2sahi(yoloBatchResults[i], np.shape(
                img), sliceImageResult.starting_pixels[i], postProcessMethod)
            if not sahiPrediction is None and len(sahiPrediction) > 0:
                sahiPredictions += sahiPrediction

        for sahiPrediction in sahiPredictions:
            shiftedPrediction = sahiPrediction.get_shifted_object_prediction()
            shiftedPrediction.obb = sahiPrediction.obb
            objectPredictions.append(shiftedPrediction)

        # standard prediction
        yoloStdResult = model([img], verbose=False)
        sahiStdResult = yolo2sahi(yoloStdResult[0], np.shape(img), [0, 0], postProcessMethod)
        objectPredictions += sahiStdResult

        if postProcessMethod == "GREEDYNMM":
            postprocess = GreedyNMMPostprocess(0.5, postProcessMetric, True)
        elif postProcessMethod == "NMS":
            postprocess = NMSPostprocess(0.5, postProcessMetric, True)
        elif postProcessMethod == "NMM":
            postprocess = NMMPostprocess(0.5, postProcessMetric, True)

        # combine
        processedObjectPredictions = postprocess(objectPredictions)
        file.streaksMasks = processResults(processedObjectPredictions)

        return file


def bbox(points):
    minX = float('inf')
    minY = float('inf')
    maxX = float('-inf')
    maxY = float('-inf')

    for x, y in points:
        minX = int(min(minX, x))
        minY = int(min(minY, y))
        maxX = int(max(maxX, x))
        maxY = int(max(maxY, y))

    return [minX, minY, maxX, maxY]


def shiftPoints(points, shiftXY):
    return [[x + shiftXY[0], y + shiftXY[1]] for x, y in points]


def polygonToMask(polygonCoords, imageShape):
    cols, rows = polygonCoords[:, 0], polygonCoords[:, 1]
    mask = np.zeros(imageShape, dtype=bool)
    rr, cc = polygon(rows, cols, imageShape)
    mask[rr, cc] = True
    return mask.astype(np.uint8)


def getSlices(image, sliceHeight, sliceWidth, overlapHeightRatio, overlapWidthRatio):
    return slice_image(
        image=image,
        output_file_name=None,
        output_dir=None,
        slice_height=sliceHeight,
        slice_width=sliceWidth,
        overlap_height_ratio=overlapHeightRatio,
        overlap_width_ratio=overlapWidthRatio,
    )


# convert yolo prediction to sahi prediction fmt
def yolo2sahi(result, shape, shift, postProcessMethod):
    results = []
    h, w, _ = shape

    for i in range(len(result.obb)):
        obb = result.obb.xyxyxyxy.cpu().numpy()[i]
        shape = obb.astype(int).tolist()
        shape = shiftPoints(shape, [shift[0], shift[1]])

        prediction = ObjectPrediction(
            category_id=0,
            category_name="streak",
            bbox=bbox(obb),
            score=result.obb.conf.cpu().numpy()[i],
            shift_amount=shift,
            full_shape=[h, w],
        )
        prediction.obb = shape
        # Only need mask for nmm and greedy_nmm
        if postProcessMethod == "GREEDYNMM" or postProcessMethod == "NMM":
            bmask = polygonToMask(np.array(shape), (h, w))
            prediction.mask = Mask.from_bool_mask(bmask, [h, w])

        results.append(prediction)

    return results


def processResults(results: List[ObjectPrediction]):
    masks = []
    if len(results) > 0:
        for prediction in results:
            if prediction.score.is_greater_than_threshold(SAHI_CONFIDENCE_THRESHOLD):
                if hasattr(prediction, 'obb'):
                    masks.append(np.array(prediction.obb).astype(int))
                elif hasattr(prediction, 'mask') and prediction.mask is not None:
                    imask = prediction.mask.bool_mask.astype(dtype=np.uint8)[:, :, np.newaxis]
                    contours, _ = cv2.findContours(imask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    for contour in contours:
                        rect = cv2.minAreaRect(contour)
                        box = cv2.boxPoints(rect).astype(int)
                        masks.append(box)
                else:
                    print("can't process prediction")

    return masks
