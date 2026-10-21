"""Image formats, RGB order, precision, and owned normalization buffers."""

import numpy as np
from PIL import Image

from support import IsolatedTestCase
from startrails.lib.image_io import imread, imwrite, normalize_image


class ImageIoTests(IsolatedTestCase):
    def test_roundtrip_encodes_requested_format_and_preserves_rgb(self):
        pixels = np.empty((8, 11, 3), dtype=np.float32)
        pixels[:] = [0.137, 0.419, 0.823]
        for suffix, format_name, tolerance in (
            (".tif", "TIFF", 0.5 / 65535),
            (".png", "PNG", 0.5 / 255),
            (".jpg", "JPEG", 3 / 255),
        ):
            with self.subTest(suffix=suffix):
                path = imwrite(self.root / ("image" + suffix), pixels, convertBGR=True)
                with Image.open(path) as image:
                    self.assertEqual(image.format, format_name)
                result = imread(path, to_rgb=True, as_float=True)
                self.assertEqual(result.dtype, np.float32)
                # Lossless formats round to their integer step; JPEG also alters chroma.
                np.testing.assert_allclose(result, pixels, atol=tolerance + 1e-7, rtol=0)

    def test_normalization_owns_its_buffer_and_preserves_input(self):
        for pixels in (np.array([[0, 32768, 65535]], np.uint16), np.array([[-0.2, 0.5, 1.2]], np.float32)):
            before = pixels.copy()
            result = normalize_image(pixels)
            self.assertEqual(result.dtype, np.float32)
            self.assertFalse(np.shares_memory(result, pixels))
            np.testing.assert_array_equal(pixels, before)
            np.testing.assert_allclose(result, [[0, 0.5, 1]], atol=1 / 65535, rtol=0)

    def test_missing_and_undecodable_images_report_errors(self):
        with self.assertRaises(FileNotFoundError):
            imread(self.root / "missing.png")
        corrupt = self.root / "corrupt.png"
        corrupt.write_bytes(b"not an image")
        with self.assertRaisesRegex(ValueError, "decode"):
            imread(corrupt)
