"""Owned row transfers and cleanup of temporary frame storage."""

import numpy as np

from support import IsolatedTestCase
from startrails.lib.denoise.stacking.disk_buffer import DiskFrameBuffer, read_frame_chunk


class DiskBufferTests(IsolatedTestCase):
    def test_windowed_conversion_and_reads_do_not_alias_input_or_storage(self):
        source = np.arange(2 * 7 * 10, dtype=np.uint16).reshape(2, 7, 10)[..., ::2]
        self.assertFalse(source.flags.c_contiguous)
        # A window smaller than two rows forces repeated bounded transfers.
        with DiskFrameBuffer(source.shape, np.float32, scratch_dir=self.root, window_bytes=21) as buffer:
            for index, frame in enumerate(source):
                buffer.write_frame(index, frame)
            np.testing.assert_array_equal(buffer.read_rows(2, 7), source[:, 2:7])
            owned = buffer.read_frame(0)
            owned[:] = -1
            np.testing.assert_array_equal(buffer.read_frame(0), source[0])
            np.testing.assert_array_equal(buffer.read_rows(0, 1, dtype=np.float64), source[:, :1])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_integer_normalization_matches_list_and_disk_paths(self):
        pixels = np.array([[[0, 255]], [[255, 0]]], dtype=np.uint8)
        with DiskFrameBuffer(pixels.shape, pixels.dtype, scratch_dir=self.root) as buffer:
            for i, frame in enumerate(pixels):
                buffer.write_frame(i, frame)
            expected = np.array([[[0, 1]], [[1, 0]]], dtype=np.float32)
            np.testing.assert_array_equal(read_frame_chunk(buffer, 0, 1, normalize=True), expected)
            np.testing.assert_array_equal(read_frame_chunk(list(pixels), 0, 1, normalize=True), expected)
        floating = [np.array([[-0.1, 1.1]], dtype=np.float32)]
        np.testing.assert_array_equal(read_frame_chunk(floating, 0, 1, normalize=True)[0], floating[0])

    def test_invalid_ranges_truncated_reads_and_exception_cleanup(self):
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with DiskFrameBuffer((2, 3, 4), np.uint16, scratch_dir=self.root) as buffer:
                path = buffer.filepath
                with self.assertRaises(IndexError):
                    buffer.read_frame(2)
                with self.assertRaises(ValueError):
                    buffer.read_rows(0, 4)
                with self.assertRaises(ValueError):
                    buffer.write_frame(0, np.zeros((2, 4)))
                path.write_bytes(b"truncated")
                with self.assertRaisesRegex(OSError, "end of frame"):
                    buffer.read_frame(1)
                raise RuntimeError("abort")
        self.assertFalse(path.exists())
        buffer.close()
        with self.assertRaises(ValueError):
            buffer.read_frame(0)
