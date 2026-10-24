"""Image formats, RGB order, precision, and owned normalization buffers."""

import errno
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
from PIL import Image

from support import IsolatedTestCase
from startrails.lib.image_io import imread, imwrite, normalize_image


class ImageIoTests(IsolatedTestCase):
    def test_locked_tiff_destination_uses_alternate_path(self):
        destination = self.root / "image.tif"
        destination.write_bytes(b"existing image")
        pixels = np.full((8, 11, 3), 32768, dtype=np.uint16)
        original_replace = Path.replace

        def replace_with_locked_destination(path, target):
            if target == destination:
                raise PermissionError(errno.EACCES, "File is locked", str(target))
            return original_replace(path, target)

        with patch.object(Path, "replace", replace_with_locked_destination):
            saved = imwrite(destination, pixels)

        self.assertEqual(saved, self.root / "image_1.tif")
        self.assertEqual(destination.read_bytes(), b"existing image")
        np.testing.assert_array_equal(imread(saved), pixels)
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
