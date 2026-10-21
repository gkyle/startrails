"""Canvas channel order, mask editing, and preview overlay behavior."""

import numpy as np
from PySide6.QtCore import QPointF

from support import QtTestCase, qt_app
from startrails.ui.canvasLabel import CanvasLabel

QT_APP = qt_app()


class CanvasTests(QtTestCase):
    def setUp(self):
        super().setUp()
        self.canvas = CanvasLabel()
        self.canvas.resize(400, 400)

    def test_float32_rgb_display_conversion(self):
        """Verify float32 RGB data in [0.0, 1.0] does not reverse channels or quantize input array."""
        h, w = 40, 40
        img = np.zeros((h, w, 3), dtype=np.float32)
        # Set top-left pixel to bright Red (R=1.0, G=0.0, B=0.0)
        img[0, 0] = [1.0, 0.0, 0.0]
        # Set bottom-right pixel to bright Blue (R=0.0, G=0.0, B=1.0)
        img[-1, -1] = [0.0, 0.0, 1.0]

        # Float32 defaults to is_bgr=False
        self.canvas.setFromNumpyArray(img, resetZoomAndPosition=True)

        self.assertIsNotNone(self.canvas.pixmap)
        qimg = self.canvas.pixmap.toImage()
        c_top_left = qimg.pixelColor(0, 0)
        c_bottom_right = qimg.pixelColor(w - 1, h - 1)

        # Red channel must be high and Blue channel zero for Red pixel
        self.assertGreater(c_top_left.red(), 240)
        self.assertEqual(c_top_left.blue(), 0)

        # Blue channel must be high and Red channel zero for Blue pixel
        self.assertGreater(c_bottom_right.blue(), 240)
        self.assertEqual(c_bottom_right.red(), 0)

        # Original array must be unchanged (full float32 precision preserved)
        self.assertEqual(img[0, 0, 0], 1.0)
        self.assertEqual(img.dtype, np.float32)

    def test_bgr_uint8_display_conversion(self):
        """Verify integer BGR data (OpenCV) correctly swaps channels for display."""
        h, w = 20, 20
        img = np.zeros((h, w, 3), dtype=np.uint8)
        # BGR blue: channel 0 is blue, channel 2 is red
        img[0, 0] = [255, 0, 0]

        self.canvas.setFromNumpyArray(img, resetZoomAndPosition=True, is_bgr=True)
        qimg = self.canvas.pixmap.toImage()
        c = qimg.pixelColor(0, 0)
        self.assertEqual(c.blue(), 255)
        self.assertEqual(c.red(), 0)

    def test_2d_mask_array_display(self):
        """Verify 2D grayscale/mask numpy arrays display without crashing."""
        mask = np.zeros((30, 30), dtype=np.float32)
        mask[:15, :] = 1.0
        self.canvas.setFromNumpyArray(mask, resetZoomAndPosition=True)
        self.assertIsNotNone(self.canvas.pixmap)
        self.assertEqual(self.canvas.pixmap.width(), 30)
        self.assertEqual(self.canvas.pixmap.height(), 30)

    def test_mask_brush_painting_and_erasing(self):
        """Verify continuous mask brush painting and erasing with screen-to-image mapping."""
        h, w = 100, 100
        base_img = np.zeros((h, w, 3), dtype=np.float32)
        self.canvas.setFromNumpyArray(base_img, resetZoomAndPosition=True)
        self.canvas.updatePixMapDimensions()

        # Enable mask editing
        self.canvas.set_mask_edit_mode(True)
        self.assertTrue(self.canvas.is_mask_edit_mode())
        self.canvas.set_brush_radius(10)

        # Paint stroke from image coordinates (20, 20) to (80, 80)
        scale = self.canvas.scale
        pos_x = self.canvas.posX
        pos_y = self.canvas.posY

        p1 = QPointF(pos_x + 20 * scale, pos_y + 20 * scale)
        p2 = QPointF(pos_x + 80 * scale, pos_y + 80 * scale)

        self.canvas.brushMode = "paint"
        self.canvas._paint_mask_stroke(p1, p2)

        mask = self.canvas.get_denoise_mask()
        self.assertIsNotNone(mask)
        # Midpoint (50, 50) and endpoints must be covered
        self.assertEqual(mask[20, 20], 1.0)
        self.assertEqual(mask[50, 50], 1.0)
        self.assertEqual(mask[80, 80], 1.0)
        # Unpainted area must be 0
        self.assertEqual(mask[5, 5], 0.0)

        # Erase midpoint (45, 45) to (55, 55)
        p_e1 = QPointF(pos_x + 45 * scale, pos_y + 45 * scale)
        p_e2 = QPointF(pos_x + 55 * scale, pos_y + 55 * scale)
        self.canvas.brushMode = "erase"
        self.canvas._paint_mask_stroke(p_e1, p_e2)

        mask_after = self.canvas.get_denoise_mask()
        self.assertEqual(mask_after[50, 50], 0.0)
        # Earlier points should still be intact
        self.assertEqual(mask_after[20, 20], 1.0)

    def test_clear_and_fill_mask(self):
        """Verify clear_denoise_mask and fill_denoise_mask emit mask_changed and set array values."""
        self.canvas.setFromNumpyArray(np.zeros((50, 50, 3), dtype=np.float32), resetZoomAndPosition=True)
        signals_fired = []
        self.canvas.mask_changed.connect(lambda: signals_fired.append(True))

        self.canvas.fill_denoise_mask()
        mask = self.canvas.get_denoise_mask()
        self.assertTrue(np.all(mask == 1.0))
        self.assertEqual(len(signals_fired), 1)

        self.canvas.clear_denoise_mask()
        mask_cleared = self.canvas.get_denoise_mask()
        self.assertTrue(np.all(mask_cleared == 0.0))
        self.assertEqual(len(signals_fired), 2)

    def test_multiple_horizon_patches_render_and_clear_together(self):
        base = np.zeros((400, 400, 3), dtype=np.float32)
        self.canvas.setFromNumpyArray(base, is_bgr=False)
        red = np.full((20, 20, 3), (1, 0, 0), dtype=np.float32)
        green = np.full((20, 20, 3), (0, 1, 0), dtype=np.float32)
        self.canvas.set_horizon_patches([(red, (30, 40, 20, 20)), (green, (200, 250, 20, 20))])
        rendered = self.canvas.grab().toImage()
        self.assertEqual(rendered.pixelColor(40, 50).red(), 255)
        self.assertEqual(rendered.pixelColor(210, 260).green(), 255)
        self.canvas.clear_horizon_overlay()
        rendered = self.canvas.grab().toImage()
        self.assertEqual(rendered.pixelColor(40, 50).red(), 0)
        self.assertEqual(rendered.pixelColor(210, 260).green(), 0)
