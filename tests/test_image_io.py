"""Image formats, RGB order, precision, and owned normalization buffers."""

import errno
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from support import IsolatedTestCase
from startrails.lib.image_io import (
    imread,
    imwrite,
    normalize_image,
    quantize_image,
    validate_image_array,
)


class ImageIoTests(IsolatedTestCase):
    def test_locked_tiff_destination_uses_alternate_path(self):
        pixels = np.full((8, 11, 3), 32768, dtype=np.uint16)
        original_replace = Path.replace

        for name, allow_alternate_path in (("image", True), ("strict", False)):
            with self.subTest(allow_alternate_path=allow_alternate_path):
                destination = self.root / f"{name}.tif"
                destination.write_bytes(b"existing image")

                def replace_with_locked_destination(path, target, destination=destination):
                    if target == destination:
                        raise PermissionError(errno.EACCES, "File is locked", str(target))
                    return original_replace(path, target)

                with patch.object(Path, "replace", replace_with_locked_destination):
                    if allow_alternate_path:
                        saved = imwrite(destination, pixels)
                    else:
                        with self.assertRaises(PermissionError):
                            imwrite(destination, pixels, allow_alternate_path=False)

                self.assertEqual(destination.read_bytes(), b"existing image")
                if allow_alternate_path:
                    self.assertEqual(saved, self.root / "image_1.tif")
                    np.testing.assert_array_equal(imread(saved), pixels)
                else:
                    self.assertFalse((self.root / "strict_1.tif").exists())
                self.assertFalse(list(self.root.glob(".image-*")))

    def test_non_lock_write_error_does_not_use_alternate_path(self):
        destination = self.root / "image.tif"
        destination.write_bytes(b"existing image")
        pixels = np.zeros((8, 11), dtype=np.uint16)
        original_open = Path.open

        def open_with_full_disk(path, *args, **kwargs):
            if args == ("wb",):
                with original_open(path, "wb") as stream:
                    stream.write(b"partial image")
                raise OSError(errno.ENOSPC, "No space left", str(path))
            return original_open(path, *args, **kwargs)

        with patch.object(Path, "open", open_with_full_disk):
            with self.assertRaises(OSError) as error:
                imwrite(destination, pixels)

        self.assertEqual(error.exception.errno, errno.ENOSPC)
        self.assertFalse((self.root / "image_1.tif").exists())
        self.assertEqual(destination.read_bytes(), b"existing image")
        self.assertFalse(list(self.root.glob(".image-*")))

    def test_preview_keeps_complete_jpeg_during_next_write(self):
        destination = self.root / "preview.jpg"
        previous = np.zeros((32, 32, 3), dtype=np.uint8)
        updated = np.full_like(previous, 255)
        imwrite(destination, previous)
        original_open = Path.open
        previews = []

        @contextmanager
        def open_with_delayed_write(path, mode="r", *args, **kwargs):
            with original_open(path, mode, *args, **kwargs) as stream:
                if mode != "wb":
                    yield stream
                    return

                def write(data):
                    midpoint = len(data) // 2
                    stream.write(data[:midpoint])
                    stream.flush()
                    previews.append(imread(destination))
                    stream.write(data[midpoint:])
                    return len(data)

                yield SimpleNamespace(write=write)

        with patch.object(Path, "open", open_with_delayed_write):
            saved = imwrite(destination, updated)

        self.assertEqual(saved, destination)
        self.assertEqual(len(previews), 1)
        np.testing.assert_array_equal(previews[0], previous)
        np.testing.assert_array_equal(imread(destination), updated)
        self.assertFalse(list(self.root.glob(".image-*")))

    def test_roundtrip_encodes_requested_format_and_preserves_rgb(self):
        pixels = np.empty((8, 11, 3), dtype=np.float32)
        pixels[:] = [0.137, 0.419, 0.823]
        for suffix, format_name, tolerance in (
            (".tif", "TIFF", 0.5 / 65535),
            (".png", "PNG", 0.5 / 255),
            (".jpg", "JPEG", 3 / 255),
            (".jpeg", "JPEG", 3 / 255),
        ):
            with self.subTest(suffix=suffix):
                path = imwrite(self.root / ("image" + suffix), pixels, convertBGR=True, optimize=suffix == ".jpeg")
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

    def test_quantize_image(self):
        float_img = np.array([[[0.0, 0.5, 1.0]]], dtype=np.float32)

        q8 = quantize_image(float_img, bit_depth=8)
        self.assertEqual(q8.dtype, np.uint8)
        self.assertEqual(q8[0, 0, 0], 0)
        self.assertEqual(q8[0, 0, 1], 128)
        self.assertEqual(q8[0, 0, 2], 255)

        q16 = quantize_image(float_img, bit_depth=16)
        self.assertEqual(q16.dtype, np.uint16)
        self.assertEqual(q16[0, 0, 0], 0)
        self.assertEqual(q16[0, 0, 1], 32768)
        self.assertEqual(q16[0, 0, 2], 65535)

        with self.assertRaises(ValueError):
            quantize_image(float_img, bit_depth=32)

    def test_validate_image_array(self):
        valid = np.zeros((16, 16, 3), dtype=np.float32)
        validate_image_array(valid, expected_channels=3, normalized=True)

        with self.assertRaises(TypeError):
            validate_image_array([0, 1, 2])  # type: ignore

        with self.assertRaises(ValueError):
            validate_image_array(np.zeros((16, 16, 3), dtype=np.uint8), normalized=True)

        nan_img = valid.copy()
        nan_img[0, 0, 0] = np.nan
        with self.assertRaises(ValueError):
            validate_image_array(nan_img)

        out_of_bounds = valid.copy()
        out_of_bounds[0, 0, 0] = 1.2
        with self.assertRaises(ValueError):
            validate_image_array(out_of_bounds, normalized=True)

        with self.assertRaises(ValueError):
            validate_image_array(valid, expected_channels=4)

    def test_imwrite_with_explicit_bit_depth(self):
        pixels = np.array([[[0.0, 0.5, 1.0]]], dtype=np.float32)

        # 8-bit TIFF export preserves 8-bit depth without promotion to 16-bit
        path_8 = imwrite(self.root / "image_8bit.tif", pixels, bit_depth=8)
        decoded_8 = imread(path_8)
        self.assertEqual(decoded_8.dtype, np.uint8)

        # 16-bit TIFF export preserves 16-bit depth
        path_16 = imwrite(self.root / "image_16bit.tif", pixels, bit_depth=16)
        decoded_16 = imread(path_16)
        self.assertEqual(decoded_16.dtype, np.uint16)

        # 16-bit PNG output ignores the JPEG-only optimize hint while preserving depth and RGB order
        color_pixels = np.array([[[0.25, 0.5, 0.75]]], dtype=np.float32)
        path_16_png = imwrite(self.root / "image_16bit.png", color_pixels, convertBGR=True, bit_depth=16, optimize=True)
        decoded_16_png = imread(path_16_png, to_rgb=True)
        self.assertEqual(decoded_16_png.dtype, np.uint16)
        np.testing.assert_array_equal(decoded_16_png, np.array([[[16384, 32768, 49151]]], dtype=np.uint16))

    def test_explicit_depth_rejects_incompatible_codec_or_integer_samples(self):
        pixels = np.full((8, 8, 3), 0.25, dtype=np.float32)
        destination = self.root / "image.jpg"
        destination.write_bytes(b"previous image")
        with self.assertRaisesRegex(ValueError, "16-bit"):
            imwrite(destination, pixels, bit_depth=16)
        self.assertEqual(destination.read_bytes(), b"previous image")
        with self.assertRaisesRegex(ValueError, "dtype"):
            imwrite(self.root / "depth.tif", np.zeros((2, 2, 3), dtype=np.uint16), bit_depth=8)
        with self.assertRaisesRegex(ValueError, "legacy"):
            imwrite(self.root / "depth.tif", pixels, bit_depth=8, tiff_uint8_as_uint16=True)
