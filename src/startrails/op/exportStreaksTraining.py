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
from startrails.op.detectStreaks import ROI_SIZE

MAX_STREAKLESS_ATTEMPTS = 20
DEBUG = False


class ExportStreaksDetectTraining(Observable):

    def cropAndLabelFiles(self, srcFiles: List[InputFile], outputDir: str):
        def process_file(file: InputFile) -> None:
            # identify human-detected streaks and export crops
            count = self.exportCroppedAndLabeledStreaks(file, outputDir)
            # export deleted masks as negative examples
            deletedCount = self.exportDeletedMasksAsNegative(file, outputDir)
            # get additional random negative examples
            exportRandomStreaklessCrops(file, outputDir, count - deletedCount)

        with ThreadPoolExecutor() as executor:
            self.startJob(len(srcFiles))
            futures = {executor.submit(process_file, file): file for file in srcFiles}
            for future in as_completed(futures):
                future.result()
                self.updateJob(1)

    def _processMaskCrops(self, file: InputFile, outputDir: str, masks, prefix: str, 
                          exportAsNegative: bool = False, addBorder: bool = False) -> int:
        """Process a list of masks and export crops."""
        if len(masks) == 0:
            return 0

        img = cv2.imread(file.path)
        
        # Add border if requested (for deleted masks at edges)
        if addBorder:
            BORDER = ROI_SIZE // 4
            img = cv2.copyMakeBorder(img, BORDER, BORDER, BORDER, BORDER, 
                                    cv2.BORDER_CONSTANT, value=[0, 0, 0])
        
        h, w, _ = np.shape(img)
        count = 0
        basename = os.path.basename(file.path)
        name, ext = os.path.splitext(basename)

        for idx, mask in enumerate(masks):
            bbox = getBoundingBox(mask)
            bbox_width = bbox[2] - bbox[0]
            bbox_height = bbox[3] - bbox[1]

            for idx_h in range(0, math.ceil(bbox_height/ROI_SIZE)):
                for idx_w in range(0, math.ceil(bbox_width/ROI_SIZE)):

                    centerPoint = getCenter(mask)
                    if bbox_width > ROI_SIZE:
                        centerPoint[0] = bbox[0] + ROI_SIZE/2 + idx_w*ROI_SIZE
                    if bbox_height > ROI_SIZE:
                        centerPoint[1] = bbox[1] + ROI_SIZE/2 + idx_h*ROI_SIZE
                    centerPoint = recenter(centerPoint, ROI_SIZE, h, w)

                    shapes, manualShapeCount = getLabelsInROI(file, centerPoint)

                    # Skip if no manual shapes and we're not exporting as negative
                    if not exportAsNegative and manualShapeCount == 0:
                        continue

                    roi = img.copy()[
                        int(centerPoint[1]-ROI_SIZE/2):int(centerPoint[1]+ROI_SIZE/2),
                        int(centerPoint[0]-ROI_SIZE/2):int(centerPoint[0]+ROI_SIZE/2)
                    ]

                    # Determine if this should be a positive (with labels) or negative example
                    hasActiveShapes = len(shapes) > 0
                    
                    if hasActiveShapes:
                        # Export as positive example with labels
                        self._exportPositiveExample(roi, shapes, outputDir, name, ext, 
                                                   prefix, idx, idx_w, idx_h)
                    elif exportAsNegative:
                        # Export as negative example
                        self._exportNegativeExample(roi, mask, centerPoint, outputDir, 
                                                   name, ext, prefix, idx, idx_w, idx_h)
                    
                    count += 1

        return count

    def _exportPositiveExample(self, roi, shapes, outputDir, name, ext, 
                              prefix, idx, idx_w, idx_h):
        """Export a crop with active masks as a positive training example."""
        crop_image_filename = "{}/{}-{}-{}-{}-{}{}".format(
            outputDir, prefix, name, idx, idx_w, idx_h, ext)
        imwrite(crop_image_filename, roi)

        if DEBUG:
            # Save annotated version
            roi_copy = roi.copy()
            for shape in shapes:
                try:
                    points_int = [np.array(shape).astype(np.int64)]
                    cv2.polylines(roi_copy, points_int, isClosed=True, 
                                color=(0, 255, 0), thickness=2)
                except Exception as e:
                    print(traceback.format_exc())
            crop_image_filename = "{}/{}-{}-{}-{}-{}-annotate{}".format(
                outputDir, prefix, name, idx, idx_w, idx_h, ext)
            imwrite(crop_image_filename, roi_copy)

        # Export labels
        lines = []
        for _, label in enumerate(shapes):
            line = ['0']
            for point in label:
                line.append(point[0]/ROI_SIZE)
                line.append(point[1]/ROI_SIZE)
            lines.append(" ".join(str(num) for num in line))

        if len(lines) > 0:
            label_filename = "{}/{}-{}-{}-{}-{}.txt".format(
                outputDir, prefix, name, idx, idx_w, idx_h)
            with open(label_filename, "w") as f_out:
                for line in lines:
                    f_out.write(line + "\n")

    def _exportNegativeExample(self, roi, mask, centerPoint, outputDir, 
                              name, ext, prefix, idx, idx_w, idx_h):
        """Export a crop without active masks as a negative training example."""
        crop_image_filename = "{}/{}-{}-{}-{}-{}{}".format(
            outputDir, prefix, name, idx, idx_w, idx_h, ext)
        imwrite(crop_image_filename, roi)

        if DEBUG:
            # Save annotated version showing the deleted mask
            roi_copy = roi.copy()
            try:
                shifted_points = []
                for point in mask:
                    shifted_points.append([
                        int(point[0] - centerPoint[0]+ROI_SIZE/2),
                        int(point[1] - centerPoint[1]+ROI_SIZE/2)
                    ])
                cv2.polylines(roi_copy, [np.array(shifted_points)], 
                            isClosed=True, color=(255, 0, 0), thickness=2)
            except Exception as e:
                print(traceback.format_exc())
            crop_image_filename = "{}/{}-{}-{}-{}-{}-annotate{}".format(
                outputDir, prefix, name, idx, idx_w, idx_h, ext)
            imwrite(crop_image_filename, roi_copy)

    def exportCroppedAndLabeledStreaks(self, file: InputFile, outputDir: str) -> int:
        return self._processMaskCrops(file, outputDir, file.streaksManualMasks, 
                                     "streaks", exportAsNegative=False)

    def exportDeletedMasksAsNegative(self, file: InputFile, outputDir: str) -> int:
        """Export crops of manually deleted masks as negative training examples."""
        return self._processMaskCrops(file, outputDir, file.streaksManualDeletedMasks, 
                                     "deleted", exportAsNegative=True, addBorder=True)


def exportRandomStreaklessCrops(file: InputFile, outputDir: str, count: int):
    if count == 0:
        return

    img = cv2.imread(file.path)
    h, w, _ = np.shape(img)
    c = 0
    while c < count and c < MAX_STREAKLESS_ATTEMPTS:
        centerPoint = [np.random.randint(0, w), np.random.randint(0, h)]
        centerPoint = recenter(centerPoint, ROI_SIZE, h, w)

        shapes, _ = getLabelsInROI(file, centerPoint)

        if len(shapes) == 0:
            roi = img[
                int(centerPoint[1]-ROI_SIZE/2):int(centerPoint[1]+ROI_SIZE/2),
                int(centerPoint[0]-ROI_SIZE/2):int(centerPoint[0]+ROI_SIZE/2)
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
    roi_box = box(0, 0, ROI_SIZE, ROI_SIZE)
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
                    point[0] - centerPoint[0]+ROI_SIZE/2,
                    point[1] - centerPoint[1]+ROI_SIZE/2
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
