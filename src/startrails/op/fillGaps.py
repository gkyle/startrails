from datetime import datetime
import os
import torch
import numpy as np
from torchvision.transforms import ToTensor
import cv2

from startrails.lib.util import imwrite, Observable
from startrails.models.fillGaps.model import UNet
from startrails.lib.file import OutputFile, InputFile

ROI_SIZE = 128
MODEL_PATH = "models/fillGaps/gapfill.pt"


class FillGaps(Observable):
    def __init__(self):
        super().__init__()

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = UNet(in_channels=3, out_channels=4).to(self.device)
        self.model.load_state_dict(torch.load(MODEL_PATH,
                                   map_location=self.device, weights_only=True))
        self.model.eval()

        self.patch_size = (ROI_SIZE, ROI_SIZE)
        self.stride = int(ROI_SIZE*0.75)

    def fillGaps(self, file: OutputFile, fileFillGaps: OutputFile, fileFillGapsMask: OutputFile):
        input_full_image = cv2.imread(file.path)

        # Get dimensions of the large image
        height, width, _ = input_full_image.shape

        # Prepare an empty array for the full image
        full_image = np.zeros_like(input_full_image)
        full_mask = np.zeros_like(input_full_image)  # np.zeros((height, width))

        self.startJob((height // self.stride) * (width // self.stride))

        # Patch-wise inference
        for y in range(0, height, self.stride):
            for x in range(0, width, self.stride):

                # Extract the patch from the large image
                patch = input_full_image[y:y + self.patch_size[0], x:x + self.patch_size[1]]
                patch_tensor = transform(patch).unsqueeze(0).to(self.device)

                # Run inference on the patch
                with torch.no_grad():
                    output, output_mask = self.model(patch_tensor)

                # Convert output to numpy array and back to the original shape
                output = untransform(output[0])

                # Convert mask
                threshold_value = 64
                mask = np.where((output_mask[0].cpu().numpy() * 255).astype(np.uint8)
                                > threshold_value, 255, 0).astype(np.uint8)

                # Apply mask
                merged = output.copy()
                merged[mask == 0] = patch[mask == 0]
                merged[mask == 255] = output[mask == 255]
                fmask = np.stack((mask,) * 3, axis=-1)

                full_image[y:y + self.patch_size[0], x:x + self.patch_size[1]] = merged
                full_mask[y:y + self.patch_size[0], x:x + self.patch_size[1]] = fmask

            imwrite(fileFillGaps.path, full_image)
            imwrite(fileFillGapsMask.path, full_mask)
            self.updateJob((width // self.stride), fileFillGaps)

            if self.shouldInterrupt():
                break

        return full_image, full_mask

    def suggestOutFileName(file: InputFile, outDir: str):
        fileName = os.path.basename(file.path)
        baseName, extension = os.path.splitext(fileName)
        ts = datetime.now().strftime("%Y-%m-%d-%H-%M")
        return [
            "{}/fillgaps-{}-{}{}".format(outDir, baseName, ts, extension),
            "{}/fillgaps_mask-{}-{}{}".format(outDir, baseName, ts, extension),
        ]


# Convert 8bit image to tensor (C, H, W) [-1,1]
def transform(img):
    imgTensor = ToTensor()(img)
    imgTensor = (imgTensor * 2) - 1
    return imgTensor


# Convert image tensor to 8bit image (H, W, C) [0,255]
def untransform(imgTensor):
    img = np.transpose(imgTensor.cpu().numpy(), (1, 2, 0))
    img = ((img + 1) * 127.5).astype(np.uint8)
    return img
