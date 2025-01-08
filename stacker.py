import argparse
import glob
import shutil
import torch
from tqdm.auto import tqdm
import cv2
import numpy as np
import os
from datetime import datetime
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from sahi.utils.ultralytics import download_yolo11n_model

STACK_BATCH_SIZE = 1
EXTENSIONS = [".jpg", ".tif", ".jpeg", ".tiff"]
SAHI_CONFIDENCE_THRESHOLD = 0.3
SAHI_SLICE_SIZE = 512
SAHI_OVERLAP = 0.2
PREPROCESS_DIR = ".preprocess"

YOLO11N_MODEL_PATH = "../models/yolo11n.pt"
STREAKS_MODEL_PATH = "./models/streaks.pt"

class Stacker:
    darkFrameFiles = []
    darkFrame = None
    srcFiles = []

    # Detect streaks using YOLO+SAHI with fine-tuned model and generate blackout images.
    def blackoutStreaks(self):
        if not os.path.exists(YOLO11N_MODEL_PATH):
            download_yolo11n_model(YOLO11N_MODEL_PATH)

        detection_model = AutoDetectionModel.from_pretrained(
            model_type='yolo11',
            model_path=STREAKS_MODEL_PATH,
            confidence_threshold=SAHI_CONFIDENCE_THRESHOLD,
            device='cuda:0' if torch.cuda.is_available() else 'cpu')

        shutil.rmtree(PREPROCESS_DIR, ignore_errors=True)
        os.makedirs(PREPROCESS_DIR, exist_ok=True)

        for _, frame in tqdm(enumerate(self.srcFiles), total=len(self.srcFiles)):
            result = get_sliced_prediction(
                frame,
                detection_model,
                slice_height = SAHI_SLICE_SIZE,
                slice_width = SAHI_SLICE_SIZE,
                overlap_height_ratio = SAHI_OVERLAP,
                overlap_width_ratio = SAHI_OVERLAP,
                verbose=False
            )
            
            # draw blackout rectangles
            img = cv2.imread(frame)
            if len(result.object_prediction_list) > 0:
                for prediction in result.object_prediction_list:
                    bbox = prediction.bbox.get_shifted_box().to_xyxy()
                    img = cv2.rectangle(img, (int(bbox[0]), int(bbox[1])), (int(bbox[2]), int(bbox[3])), (0,0,0), -1)

            cv2.imwrite("{}/{}".format(PREPROCESS_DIR, os.path.basename(frame)), img)


    # Create a single dark frame image from 1 or more dark frame images by stacking light pixels
    def createDarkFrame(self):
        if len(self.darkFrameFiles) == 0:
            return
        
        ## ensure dark frame images and input iumages have same shape
        shape = np.shape(cv2.imread(self.darkFrameFiles[0]))
        darkFrames = []
        for file in self.darkFrameFiles:
            frame = cv2.imread(file)
            if shape != np.shape(frame):
                raise SystemExit("Dark frame shapes do not match: {} vs {}".format(str(shape), str(np.shape(frame))))
            darkFrames.append(frame)
            
        refImage = cv2.imread(self.srcFiles[0])
        if shape != np.shape(refImage):
            raise SystemExit("Dark frame shape does not match input files: {} vs {}".format(str(shape), str(np.shape(refImage))))

        imageStack = np.stack(darkFrames, axis=0)
        self.darkFrame = np.max(imageStack, axis=0)


    def subtractDarkFrame(self, image):
        return cv2.subtract(image, self.darkFrame)


    # Stack images, preserving lightest pixels
    def stack(self, files, outfile):
        images = []
        for idx, frame in tqdm(enumerate(files), total=len(files)):
            img = cv2.imread(frame)
            if not self.darkFrame is None:
                img = self.subtractDarkFrame(img)
            images.append(img)
            if idx % STACK_BATCH_SIZE == 0:
                imageStack = np.stack(images, axis=0)
                imageMax = np.max(imageStack, axis=0)
                cv2.imwrite(outfile, imageMax)
                images = [imageMax]

        imageStack = np.stack(images, axis=0)
        imageMax = np.max(imageStack, axis=0)
        cv2.imwrite(outfile, imageMax)


    def _getFileList(self, path):
        if path is None:
            return []
        if os.path.isdir(path):
            return sum([glob.glob(path + "/*" + ext) for ext in EXTENSIONS], [])
        return glob.glob(path)


    def _getStackedOutputFileName(self, outfile, options=""):
        if not outfile is None:
            return outfile
        if len(self.srcFiles) > 0:
            fileName = os.path.basename(self.srcFiles[0])
            baseName, extension = os.path.splitext(fileName)
        else:
            baseName, extension = ["", ".jpg"]
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
        return "./stacked-{}{}-{}{}".format(baseName, options, ts, extension)


    def run(self):
        parser = argparse.ArgumentParser(
                    prog='stacker',
                    description='Stack night sky images into star trails',
                    epilog='...')

        parser.add_argument('path', type=str, help='path / expression for input images')
        parser.add_argument('--outfile',  nargs="?", help='(Optional) Path to stacked output file.')
        parser.add_argument('--darkFrames',  nargs="?", help='(Optional) Path to a dark frame images.')
        parser.add_argument('--removeStreaks', default=False, action=argparse.BooleanOptionalAction, help='(Optional) Remove staellite streaks from frames.')
        args = parser.parse_args()

        self.srcFiles = self._getFileList(args.path)
        print("Found {} files matching {}".format(len(self.srcFiles), args.path))

        print("Options:")
        print("- [{}] Subtract dark frames".format("YES" if not args.darkFrames is None else "NO "))
        print("- [{}] Detect and remove streaks".format("YES" if args.removeStreaks else "NO "))

        # --darkFrames:
        self.darkFrameFiles = self._getFileList(args.darkFrames)
        if len(self.darkFrameFiles) > 0:
            self.createDarkFrame()
    
        # --removeStreaks
        if args.removeStreaks:
            print("Detecting streaks and writing blackout images to {}".format(PREPROCESS_DIR))
            self.blackoutStreaks()

        # stack
        optionsToOutputFile = ""
        if not args.darkFrames is None:
            optionsToOutputFile = optionsToOutputFile + "-DF"
        if args.removeStreaks:
            optionsToOutputFile = optionsToOutputFile + "-RS"

        stackedFileName = self._getStackedOutputFileName(args.outfile, optionsToOutputFile)
        print("Stacking images to {}".format(stackedFileName))
        if args.removeStreaks:
            self.stack(self._getFileList(PREPROCESS_DIR), stackedFileName)
        else:
            self.stack(self.srcFiles, stackedFileName)


def main():
    stacker = Stacker()
    stacker.run()

if __name__ == "__main__":
    main()