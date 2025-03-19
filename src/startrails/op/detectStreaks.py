from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from typing import List
import cv2
from skimage.draw import polygon
import numpy as np

from ultralytics import YOLO
from ultralytics.utils import ThreadingLocked
from sahi.utils.torch import is_torch_cuda_available
from sahi.postprocess.combine import NMSPostprocess, NMMPostprocess, GreedyNMMPostprocess
from sahi.prediction import ObjectPrediction
from sahi.annotation import Mask
from sahi.slicing import slice_image
from typing import List

from startrails.lib.util import Observable
from startrails.lib.file import InputFile

USE_GPU_IF_AVAILABLE = True

PATCH_OVERLAP = 0.2
STREAKS_MODEL_PATH = "models/detectStreaks/streaks.pt"
STREAKS_MODEL_OPENVINO_PATH = "models/detectStreaks/streaks_openvino_model/"
DETECT_BATCH_SIZE = 2
ROI_SIZE = 512


class DetectStreaks(Observable):
    def __init__(self, useGPU=True):
        super().__init__()
        self.device = 'cuda:0' if USE_GPU_IF_AVAILABLE and useGPU and is_torch_cuda_available() else 'cpu'

        # Prefer openvino/fp16 model variant if device is cpu
        if self.device == 'cpu':
            self.model = YOLO(STREAKS_MODEL_OPENVINO_PATH, task="obb")
        else:
            self.model = YOLO(STREAKS_MODEL_PATH, task="obb")

    def detectStreaks(self, srcFiles: List[InputFile], confThreshold, mergeMethod, mergeThreshold):

        def processFile(file: InputFile):
            return self.detectStreaksInImage(file, confThreshold, mergeMethod, mergeThreshold)

        completed = 0
        showIncrement = 20
        self.startJob(len(srcFiles))
        with ThreadPoolExecutor(max_workers=DETECT_BATCH_SIZE) as executor:
            futures = {executor.submit(processFile, file): file for file in srcFiles}
            for future in as_completed(futures):
                result = future.result()
                if completed % showIncrement == 0:
                    self.updateJob(1, result)
                else:
                    self.updateJob(1, None)
                completed += 1
                if self.shouldInterrupt():
                    for future in futures:
                        future.cancel()
                    executor.shutdown()
                    break

    @ThreadingLocked()
    def predict(self, images, conf, batchSize, imgsz):
        return self.model(images, conf=conf, batch=batchSize,
                          imgsz=imgsz, device=self.device, half=True, verbose=False)

    # Sliced predictions are good at identifying small objects. Standard prediction is good at
    # fully identifying objects that span multiple slices. So we do both and combine.
    # This is faster than SAHI get_sliced_prediction because:
    # - Uses YOLO model batched processing
    # - Does not build / use expensive masks when not needed

    def detectStreaksInImage(self, file: InputFile, confThreshold: float, postProcessMethod: str, mergeThreshold: float) -> InputFile:
        try:
            img = cv2.imread(file.path)
            # make a larger canvas to improve detection at edges
            BORDER = ROI_SIZE // 4
            h, w, _ = np.shape(img)
            canvas = np.zeros((h + BORDER*2, w + BORDER*2, 3), dtype=np.uint8)
            canvas[BORDER:h + BORDER, BORDER:w + BORDER] = img
            img = canvas

            # sliced predictions
            sliceImageResult = getSlices(img, ROI_SIZE, ROI_SIZE, PATCH_OVERLAP, PATCH_OVERLAP)
            images = []
            for image in sliceImageResult.sliced_image_list:
                images.append(image.image)

            yoloBatchResults = self.predict(images, conf=confThreshold, batchSize=16, imgsz=ROI_SIZE)
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

            # standard prediction, downscaled
            imgsz = ROI_SIZE * 4
            yoloStdResult = self.predict([img], conf=confThreshold, batchSize=1, imgsz=imgsz)
            sahiStdResult = yolo2sahi(yoloStdResult[0], np.shape(img), [0, 0], postProcessMethod)
            if len(sahiStdResult) > 0:
                shiftedStdResult = sahiStdResult[0].get_shifted_object_prediction()
                shiftedStdResult.obb = sahiStdResult[0].obb
                objectPredictions.append(shiftedStdResult)

            if postProcessMethod == "GREEDYNMM":
                postprocess = GreedyNMMPostprocess(mergeThreshold, "IOS", True)
            elif postProcessMethod == "NMS":
                postprocess = NMSPostprocess(mergeThreshold, "IOU", True)
            elif postProcessMethod == "NMM":
                postprocess = NMMPostprocess(mergeThreshold, "IOS", True)

            # combine
            processedObjectPredictions = postprocess(objectPredictions)
            file.streaksMasks = processResults(processedObjectPredictions, BORDER)

        except Exception as e:
            traceback.print_exc()

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


def processResults(results: List[ObjectPrediction], border=0):
    masks = []
    if len(results) > 0:
        for prediction in results:
            if hasattr(prediction, 'obb'):
                box = np.array(prediction.obb).astype(int)
                box -= border
                masks.append(box)
            elif hasattr(prediction, 'mask') and prediction.mask is not None:
                imask = prediction.mask.bool_mask.astype(dtype=np.uint8)[:, :, np.newaxis]
                contours, _ = cv2.findContours(imask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for contour in contours:
                    rect = cv2.minAreaRect(contour)
                    box = cv2.boxPoints(rect).astype(int)
                    box -= border
                    masks.append(box)
            else:
                print("can't process prediction")

    return masks
