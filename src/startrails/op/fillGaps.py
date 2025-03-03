import torch
import numpy as np
from torchvision.transforms import ToTensor
import cv2

from startrails.lib.util import imwrite, Observable
from startrails.models.fillGaps.model import UNet
from startrails.lib.file import OutputFile

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
                patch_tensor = ToTensor()(patch)
                patch_tensor = patch_tensor.unsqueeze(0).to(self.device)

                # Run inference on the patch
                with torch.no_grad():
                    output, output_mask = self.model(patch_tensor)

                # Convert output to numpy array and back to the original shape
                output = output[0].cpu().numpy()  # Remove batch dim and convert to NumPy
                output = np.transpose(output, (1, 2, 0))  # Change shape from (C, H, W) to (H, W, C)
                output = np.clip(output, 0, 1)  # Ensure pixel values are within [0, 1]
                output = (output * 255).astype(np.uint8)  # Convert to 8-bit RGB format

                # Convert mask
                threshold_value = 32
                mask = np.where((output_mask[0].cpu().numpy() * 255).astype(np.uint8)
                                > threshold_value, 255, 0).astype(np.uint8)

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
