from concurrent.futures import ThreadPoolExecutor, as_completed
import math
import os
import traceback
from typing import List
import cv2
import numpy as np
from shapely.geometry import Polygon, box

from startrails.lib.util import imwrite, Observable
from startrails.lib.file import InputFile

SIZE = 512  # Generated images will be 512x512
MAX_STREAKLESS_ATTEMPTS = 20
DEBUG = False


class ExportStreaksDetectTraining(Observable):

    def cropAndLabelFiles(self, srcFiles: List[InputFile], outputDir: str):
        def process_file(file: InputFile) -> None:
            # identify human-detected streaks and export crops
            count = self.exportCroppedAndLabeledStreaks(file, outputDir)
            # get an equal number of negative examples
            exportRandomStreaklessCrops(file, outputDir, count)

        with ThreadPoolExecutor() as executor:
            self.startJob(len(srcFiles))
            futures = {executor.submit(process_file, file): file for file in srcFiles}
            for future in as_completed(futures):
                future.result()
                self.updateJob(1)

    def exportCroppedAndLabeledStreaks(self, file: InputFile, outputDir: str) -> int:
        if len(file.streaksManualMasks) == 0:
            return 0

        img = cv2.imread(file.path)
        h, w, _ = np.shape(img)
        count = 0

        masks = file.streaksManualMasks
        for idx, mask in enumerate(masks):

            bbox = getBoundingBox(mask)
            bbox_width = bbox[2] - bbox[0]
            bbox_height = bbox[3] - bbox[1]

            for idx_h in range(0, math.ceil(bbox_height/SIZE)):
                for idx_w in range(0, math.ceil(bbox_width/SIZE)):

                    centerPoint = getCenter(mask)
                    if bbox_width > SIZE:
                        centerPoint[0] = bbox[0] + SIZE/2 + idx_w*SIZE
                    if bbox_height > SIZE:
                        centerPoint[1] = bbox[1] + SIZE/2 + idx_h*SIZE
                    centerPoint = recenter(centerPoint, SIZE, h, w)

                    shapes, manualShapeCount = getLabelsInROI(file, centerPoint)

                    if manualShapeCount > 0:
                        roi = img.copy()[
                            int(centerPoint[1]-SIZE/2):int(centerPoint[1]+SIZE/2),
                            int(centerPoint[0]-SIZE/2):int(centerPoint[0]+SIZE/2)
                        ]

                        # Save the cropped image
                        basename = os.path.basename(file.path)
                        name, ext = os.path.splitext(basename)
                        crop_image_filename = "{}/streaks-{}-{}-{}-{}{}".format(outputDir, name, idx, idx_w, idx_h, ext)
                        imwrite(crop_image_filename, roi)
                        count = count + 1

                        if DEBUG:
                            # Save annotated version
                            for shape in shapes:
                                try:
                                    points_int = [np.array(shape).astype(np.int64)]
                                    cv2.polylines(roi, points_int, isClosed=True, color=(0, 255, 0), thickness=2)
                                except Exception as e:
                                    print(traceback.format_exc())
                            crop_image_filename = "{}/streaks-{}-{}-{}-{}-annotate{}".format(
                                outputDir, name, idx, idx_w, idx_h, ext)
                            imwrite(crop_image_filename, roi)

                        # Format is "class x1 y1 x2 y2 x3 y3 x4 y4"... where class is 0 for "streak"
                        # Each line in the text file represents one object with its class label, followed by the polygon coordinates.
                        # Each polygon point is normalized x and y coordinates (between 0 and 1) relative to the image dimensions.
                        lines = []
                        for _, label in enumerate(shapes):
                            line = ['0']
                            for point in label:
                                line.append(point[0]/SIZE)
                                line.append(point[1]/SIZE)
                            lines.append(" ".join(str(num) for num in line))

                        if len(lines) > 0:
                            label_filename = "{}/streaks-{}-{}-{}-{}.txt".format(outputDir, name, idx, idx_w, idx_h)
                            f_out = open(label_filename, "w")
                            for line in lines:
                                f_out.write(line + "\n")
                            f_out.close()

        return count


def exportRandomStreaklessCrops(file: InputFile, outputDir: str, count: int):
    if count == 0:
        return

    img = cv2.imread(file.path)
    h, w, _ = np.shape(img)
    c = 0
    while c < count and c < MAX_STREAKLESS_ATTEMPTS:
        centerPoint = [np.random.randint(0, w), np.random.randint(0, h)]
        centerPoint = recenter(centerPoint, SIZE, h, w)

        shapes, _ = getLabelsInROI(file, centerPoint)

        if len(shapes) == 0:
            roi = img[
                int(centerPoint[1]-SIZE/2):int(centerPoint[1]+SIZE/2),
                int(centerPoint[0]-SIZE/2):int(centerPoint[0]+SIZE/2)
            ]

            c = c + 1
            basename = os.path.basename(file.path)
            name, ext = os.path.splitext(basename)
            crop_image_filename = "{}/nostreaks-{}-{}{}".format(
                outputDir, name, c, ext)
            imwrite(crop_image_filename, roi)


# Intersect labels with crop
def getLabelsInROI(file: InputFile, centerPoint):
    shapes = []
    roi_box = box(0, 0, SIZE, SIZE)
    manualShapeCount = 0

    # include all masks present in this crop
    for masks in [file.streaksManualMasks, file.streaksMasks]:
        for imask in masks:
            if len(imask) < 3:
                continue
            points = imask
            shifted_points = []
            for point in points:
                shifted_points.append([
                    point[0] - centerPoint[0]+SIZE/2,
                    point[1] - centerPoint[1]+SIZE/2
                ])

            try:
                uncropped_polygon = Polygon(shifted_points)
                # Fix case where polygon segments cross by redrawing polygon around exterior coords.
                uncropped_polygon = Polygon(uncropped_polygon.exterior.coords)
                clipped_polygon = uncropped_polygon.intersection(roi_box)
                if not clipped_polygon.is_empty:
                    if clipped_polygon.area > 250:
                        clipped_points = list(clipped_polygon.exterior.coords)
                        shapes.append(clipped_points)
                        if np.array_equal(masks, file.streaksManualMasks):
                            manualShapeCount = manualShapeCount + 1
            except Exception as e:
                print(traceback.format_exc())

    return shapes, manualShapeCount


def getBoundingBox(points):
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]

    x_min = min(x_coords)
    x_max = max(x_coords)
    y_min = min(y_coords)
    y_max = max(y_coords)

    return (x_min, y_min, x_max, y_max)


# Get polygon center
def getCenter(points):
    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]

    x_center = sum(x_coords) / len(points)
    y_center = sum(y_coords) / len(points)

    return [x_center, y_center]


# Adjust center point if ROI goes out of bounds.
def recenter(centerPoint, size, h, w):
    bbox_y1 = (centerPoint[1]-size/2)
    bbox_y2 = (centerPoint[1]+size/2)
    bbox_x1 = (centerPoint[0]-size/2)
    bbox_x2 = (centerPoint[0]+size/2)

    cpx = centerPoint[0]
    cpy = centerPoint[1]

    if bbox_y1 < 0:
        cpy = cpy - bbox_y1
    if bbox_x1 < 0:
        cpx = cpx - bbox_x1
    if bbox_y2 > h:
        cpy = cpy - (bbox_y2 - h)
    if bbox_x2 > w:
        cpx = cpx - (bbox_x2 - w)

    return ([cpx, cpy])
