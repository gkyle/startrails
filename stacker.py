import argparse
import cv2
from datetime import datetime
import glob
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from sahi.utils.ultralytics import download_yolo11n_model
from sahi.utils.torch import is_torch_cuda_available
import shutil
import time
from tqdm.auto import tqdm
import os

from taskqueue import Task, TaskQueue
from util import imwrite

# Use cupy wrapper around numpy if CUDA is available
USE_GPU_IF_AVAILABLE = True
try:
    import cupy as np
    if not USE_GPU_IF_AVAILABLE or not np.is_available():
        import numpy as np
except ModuleNotFoundError:
    import numpy as np

STACK_BATCH_SIZE = 4
DETECT_BATCH_SIZE = 2
# If using GPU and cupy, set more aggressive defaults.
if USE_GPU_IF_AVAILABLE and hasattr(np, 'asnumpy') and is_torch_cuda_available():
    STACK_BATCH_SIZE = 16 # Can go to 64 or higher, but requires a lot of VRAM.
    DETECT_BATCH_SIZE = 8

EXTENSIONS = [".jpg", ".tif", ".jpeg", ".tiff"]
SAHI_CONFIDENCE_THRESHOLD = 0.3
SAHI_SLICE_SIZE = 512
SAHI_OVERLAP = 0.2
PREPROCESS_DIR = ".preprocess"

YOLO11N_MODEL_PATH = "./models/yolo11n-obb.pt"
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
            device='cuda:0' if USE_GPU_IF_AVAILABLE and is_torch_cuda_available() else 'cpu')

        shutil.rmtree(PREPROCESS_DIR, ignore_errors=True)
        os.makedirs(PREPROCESS_DIR, exist_ok=True)

        with tqdm(range(0, len(self.srcFiles))) as progressBar:
            self.queue = TaskQueue(progressBar, DETECT_BATCH_SIZE)
            for _, frame in enumerate(self.srcFiles):
                self.queue.append(BlackoutTask(detection_model, frame))

            self.queue.start()
            while not self.queue.done:
                time.sleep(0.1)

            self.queue.join()


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
        images = None
        for idx, frame in tqdm(enumerate(files), total=len(files)):
            img = cv2.imread(frame)
            if not self.darkFrame is None:
                img = self.subtractDarkFrame(img)
            if images is None:
                images = img.reshape((1, ) + img.shape)
            else:
                images = np.append(images, img.reshape((1, ) + img.shape), axis=0)
    
            if idx % STACK_BATCH_SIZE == 0:
                imageStack = np.stack(np.array(images), axis=0)
                imageMax = np.max(imageStack, axis=0)
                imwrite(outfile, imageMax)
                images = imageMax.reshape((1, ) + imageMax.shape)

        imageStack = np.stack(np.array(images), axis=0)
        imageMax = np.max(imageStack, axis=0)
        imwrite(outfile, imageMax)


    def _getFileList(self, path):
        if path is None:
            return []
        if os.path.isdir(path):
            return sorted(sum([glob.glob(path + "/*" + ext) for ext in EXTENSIONS], []))
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


class BlackoutTask(Task):
    def __init__(self, detection_model, fileName):
        Task.__init__(self)
        self.detection_model = detection_model
        self.fileName = fileName

    def run(self):
        try:
            result = get_sliced_prediction(
                self.fileName,
                self.detection_model,
                slice_height = SAHI_SLICE_SIZE,
                slice_width = SAHI_SLICE_SIZE,
                overlap_height_ratio = SAHI_OVERLAP,
                overlap_width_ratio = SAHI_OVERLAP,
                verbose=False
            )
            
            img = np.array(result.image)
            h,w,_ = np.shape(img)
            if len(result.object_prediction_list) > 0:
                mask = np.zeros((h,w), bool)
                for prediction in result.object_prediction_list:
                    mask = mask + np.array(prediction.mask.bool_mask).astype(dtype=bool)

                mask = mask == 0 # invert
                mask = np.repeat(mask[:, :, np.newaxis], 3, axis=2)
                img = img * mask

            imwrite("{}/{}".format(PREPROCESS_DIR, os.path.basename(self.fileName)), img, convertBGR=True)
            self.callback(self)
        except Exception as e:
            print(e)


def main():
    stacker = Stacker()
    stacker.run()

if __name__ == "__main__":
    main()