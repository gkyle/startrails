"""Operation for exporting downscaled 8-bit sky training images and masks."""

from __future__ import annotations
from pathlib import Path
from typing import Optional, Tuple, Union
import cv2
import numpy as np

from startrails.lib.image_io import imread
from startrails.lib.util import Observable


class ExportSkyTraining(Observable):
    """Downscales reference image and sky mask by half into 8-bit training assets."""

    def export(
        self,
        image_path: Union[str, Path],
        mask: Union[np.ndarray, str, Path],
        out_dir: Union[str, Path],
    ) -> Tuple[Path, Path]:
        """Export downscaled 8-bit image.jpg and mask.png into out_dir.

        Args:
            image_path: Path to reference image file.
            mask: 2D numpy array (float32 [0.0, 1.0] or uint8) or path to mask file.
            out_dir: Target directory.

        Returns:
            Tuple of (image_file_path, mask_file_path).
        """
        self.startJob(2)
        out_path = Path(out_dir).resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        img_file = Path(image_path).resolve()
        if not img_file.exists():
            raise FileNotFoundError(f"Reference image not found: {img_file}")

        img = imread(img_file, to_rgb=False, as_float=False)

        # 1. Convert depth to 8-bit uint8
        if img.dtype == np.uint16:
            img_u8 = np.round(img.astype(np.float32) / 257.0).astype(np.uint8)
        elif img.dtype in (np.float32, np.float64):
            img_u8 = np.clip(img * 255.0, 0, 255).astype(np.uint8)
        else:
            img_u8 = img.astype(np.uint8)

        # 2. Standardize channels to 3-channel BGR for JPEG export
        if img_u8.ndim == 3 and img_u8.shape[2] == 4:
            img_u8 = cv2.cvtColor(img_u8, cv2.COLOR_BGRA2BGR)
        elif img_u8.ndim == 2:
            img_u8 = cv2.cvtColor(img_u8, cv2.COLOR_GRAY2BGR)

        h, w = img_u8.shape[:2]
        target_w = max(1, w // 2)
        target_h = max(1, h // 2)

        # 3. Downscale image by half with INTER_AREA
        small_img = cv2.resize(img_u8, (target_w, target_h), interpolation=cv2.INTER_AREA)
        image_out = out_path / "image.jpg"
        cv2.imwrite(str(image_out), small_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
        self.updateJob(1, {"desc": "Exported training image"})

        if self.shouldInterrupt():
            return image_out, out_path / "mask.png"

        # 4. Prepare mask
        if isinstance(mask, (str, Path)):
            from startrails.lib.denoise.mask import MaskHandler
            mask_arr = MaskHandler.load_mask(mask)
        else:
            mask_arr = mask

        if mask_arr.dtype != np.uint8:
            mask_u8 = (mask_arr > 0.5).astype(np.uint8) * 255
        else:
            if mask_arr.max() <= 1 and mask_arr.max() > 0:
                mask_u8 = mask_arr * 255
            else:
                mask_u8 = (mask_arr >= 128).astype(np.uint8) * 255

        if mask_u8.shape[:2] != (h, w):
            mask_u8 = cv2.resize(mask_u8, (w, h), interpolation=cv2.INTER_NEAREST)

        # 5. Downscale mask by half with INTER_NEAREST
        small_mask = cv2.resize(mask_u8, (target_w, target_h), interpolation=cv2.INTER_NEAREST)
        mask_out = out_path / "mask.png"
        cv2.imwrite(str(mask_out), small_mask)
        self.updateJob(1, {"desc": "Exported training mask"})

        return image_out, mask_out
