import os
from typing import List, Optional, Tuple
import cv2
import numpy as np
from PySide6.QtCore import (Qt, QPointF, QTimer, Signal, QRect)
from PySide6.QtGui import (QPainter, QPaintEvent, QWheelEvent, QMouseEvent,
                           QPixmap, QColor, QPen, QPainterPath, QFont, QImage,
                           QImageReader, QCursor, qRgba)
from PySide6.QtWidgets import QLabel, QWidget

from startrails.lib.file import File, InputFile, OutputFile
from startrails.ui.signals import Signals, getSignals
from startrails.ui.theme import themed_color

# Disable Qt's default 256MB QImageIOHandler allocation limit so large camera/denoise TIFFs load properly
QImageReader.setAllocationLimit(0)


class CanvasLabel(QLabel):
    NUB_SIZE = 10
    NUB_SIZE_TOLERANT = 15
    findBrightestModeChanged = Signal(bool)
    mask_changed = Signal()
    brush_radius_changed = Signal(int)

    def __init__(self, text: Optional[str] = None, pixmap: Optional[QPixmap] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.zoom_factor: float = 1.0
        self.posX: int = 0
        self.posY: int = 0
        self.dragX: int = 0
        self.dragY: int = 0
        self.mouseX: int = 0
        self.mouseY: int = 0
        self.pixmap: Optional[QPixmap] = None
        self.signals: Signals = getSignals()
        self.setMouseTracking(True)
        self.file: Optional[File] = None
        self.selectedMask: Optional[Tuple[List[List[float]], List[List[float]]]] = None  # (mask, original points)
        self.draggingMask: bool = False
        self.selectedNub: Optional[Tuple[List[List[float]], int, List[float]]] = None  # (mask, idx, original point)
        self.draggingNub: bool = False

        self.renderWidth: Optional[int] = None
        self.renderHeight: Optional[int] = None
        self.scale: Optional[float] = None
        self.ratio: Optional[float] = None
        self.showDeletedMasks: bool = False
        self.findBrightestMode: bool = False

        # Denoise mask brush editing state
        self.maskEditMode: bool = False
        self.brushRadius: int = 25
        self.brushMode: str = "paint"
        self._mask_array: Optional[np.ndarray] = None  # uint8 (H, W) in [0, 255]
        self._mask_qimage: Optional[QImage] = None
        self._is_brush_painting: bool = False
        self._last_brush_pos: Optional[QPointF] = None

        # Gradient mask overlay state
        self._gradient_mask_array: Optional[np.ndarray] = None
        self._gradient_mask_qimage: Optional[QImage] = None
        self.gradientMaskVisible: bool = False

        # Live horizon preview overlay state
        self._horizon_overlay_pixmap: Optional[QPixmap] = None
        self._horizon_overlay_rect: Optional[Tuple[int, int, int, int]] = None
        self._horizon_overlay_arr: Optional[np.ndarray] = None
        self._horizon_overlay_patches = []

        # Debounce timers for high-frequency events
        self.wheelDebounceTimer = QTimer()
        self.wheelDebounceTimer.setSingleShot(True)
        self.wheelDebounceTimer.timeout.connect(self._debouncedWheelAction)
        self.pendingWheelDelta = 0

        self.mouseMoveDebounceTimer = QTimer()
        self.mouseMoveDebounceTimer.setSingleShot(True)
        self.mouseMoveDebounceTimer.timeout.connect(self._debouncedMouseMoveAction)

        self.setAlignment(Qt.AlignCenter)
        font = self.font()
        font.setPointSize(20)
        font.setWeight(QFont.Bold)
        self.setFont(font)
        self.setPixmap(pixmap)

    def setFindBrightestMode(self, active: bool) -> None:
        active = bool(active)
        if self.findBrightestMode != active:
            self.findBrightestMode = active
            if active:
                self.setCursor(Qt.CrossCursor)
            else:
                self.unsetCursor()
            self.findBrightestModeChanged.emit(active)

    def keyPressEvent(self, ev) -> None:
        if ev.key() == Qt.Key_Escape and self.findBrightestMode:
            self.setFindBrightestMode(False)
            ev.accept()
            return
        if self.maskEditMode:
            if ev.key() == Qt.Key_BracketLeft:
                self.set_brush_radius(self.brushRadius - 5)
                ev.accept()
                return
            elif ev.key() == Qt.Key_BracketRight:
                self.set_brush_radius(self.brushRadius + 5)
                ev.accept()
                return
        super().keyPressEvent(ev)

    def setFile(self, file: File, reload: bool = False) -> None:
        if (
            not reload
            and file is not None
            and self.file is not None
            and getattr(file, "path", None) == getattr(self.file, "path", None)
            and self.pixmap is not None
            and not self.pixmap.isNull()
        ):
            return

        if self.findBrightestMode:
            self.setFindBrightestMode(False)
        if self.maskEditMode:
            self.set_mask_edit_mode(False)
        self.clear_horizon_overlay()
        self.set_gradient_mask_visible(False)
        # clear previous active mask points
        if isinstance(self.file, InputFile):
            self.file.activeMaskPoints = []

        if file is not None and getattr(file, "path", None):
            self.file = file
            QImageReader.setAllocationLimit(0)
            newPixmap = QPixmap(file.path)
            # Sometimes we're writing over a file at the same moment we try to replace the pixmap. Try to not replace useful pixels with nil.
            if newPixmap.width() > 0 and newPixmap.height() > 0:
                self.setPixmap(newPixmap, True)
            elif os.path.exists(file.path):
                # Robust fallback for large, 16-bit, float, or formats that Qt QPixmap couldn't load directly
                try:
                    with open(file.path, "rb") as f:
                        buf = np.frombuffer(f.read(), dtype=np.uint8)
                    arr = cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
                    if arr is not None and arr.size > 0:
                        self.setFromNumpyArray(arr, resetZoomAndPosition=True)
                except Exception as err:
                    print(f"Error loading image fallback for {file.path}: {err}")
        else:
            self.file = None
            self.selectedMask = None
            self.selectedNub = None
            self.draggingMask = False
            self.draggingNub = False
            self.setPixmap(QPixmap(), True)

    def setFromNumpyArray(
        self,
        inputImage: np.ndarray,
        resetZoomAndPosition: bool = False,
        is_bgr: Optional[bool] = None,
    ) -> None:
        if inputImage is None:
            self.setPixmap(QPixmap(), True)
            return

        img = inputImage
        if is_bgr is None:
            # Floating-point data from denoise operations is RGB in [0.0, 1.0]
            # Integer data from OpenCV / StarTrails operations is BGR
            is_bgr = (img.dtype not in (np.float32, np.float64))

        # Convert to 8-bit for QPixmap display without quantizing input image in memory
        if img.dtype in (np.float32, np.float64):
            img_disp = (np.clip(img, 0.0, 1.0) * 255.0).astype(np.uint8)
        elif img.dtype == np.uint16:
            img_disp = (img / 256).astype(np.uint8)
        elif img.dtype == np.bool_:
            img_disp = (img.astype(np.uint8) * 255)
        else:
            img_disp = img.astype(np.uint8, copy=False)

        if img_disp.ndim == 2:
            img_disp = np.stack([img_disp] * 3, axis=-1)
        elif img_disp.ndim == 3 and img_disp.shape[2] == 1:
            img_disp = np.repeat(img_disp, 3, axis=2)
        elif img_disp.ndim == 3 and img_disp.shape[2] == 3 and is_bgr:
            img_disp = img_disp[:, :, ::-1]
        elif img_disp.ndim == 3 and img_disp.shape[2] == 4 and is_bgr:
            img_disp = img_disp[:, :, [2, 1, 0, 3]]

        height, width, channels = img_disp.shape
        img_disp = np.ascontiguousarray(img_disp)
        bytesPerLine = channels * width
        fmt = QImage.Format_RGBA8888 if channels == 4 else QImage.Format_RGB888
        qimage = QImage(img_disp.data, width, height, bytesPerLine, fmt)
        pixmap = QPixmap.fromImage(qimage.copy())
        self.setPixmap(pixmap, doResetZoomAndPosition=resetZoomAndPosition)

    # -------------------------------------------------------------------------
    # Denoise Mask Brush & Overlay Methods
    # -------------------------------------------------------------------------

    def _init_mask_qimage(self) -> None:
        if self._mask_array is None:
            self._mask_qimage = None
            return
        h, w = self._mask_array.shape[:2]
        if not self._mask_array.flags["C_CONTIGUOUS"]:
            self._mask_array = np.ascontiguousarray(self._mask_array)
        self._mask_qimage = QImage(
            self._mask_array.data,
            w,
            h,
            self._mask_array.strides[0],
            QImage.Format_Indexed8,
        )
        color_table = [
            qRgba(0, 255, 0, int(i * 0.45)) if i > 5 else qRgba(0, 0, 0, 0)
            for i in range(256)
        ]
        self._mask_qimage.setColorTable(color_table)

    def set_denoise_mask(self, mask: Optional[np.ndarray]) -> None:
        if mask is None:
            self._mask_array = None
            self._mask_qimage = None
            self.update()
            return

        if mask.ndim == 3:
            mask = mask[..., 0]

        if self.pixmap is not None and self.pixmap.width() > 0 and self.pixmap.height() > 0:
            pw, ph = self.pixmap.width(), self.pixmap.height()
            if mask.shape[:2] != (ph, pw):
                mask = cv2.resize(mask.astype(np.float32), (pw, ph), interpolation=cv2.INTER_NEAREST)

        if mask.dtype != np.uint8:
            self._mask_array = (np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8)
        else:
            self._mask_array = mask.copy()

        if not self._mask_array.flags["C_CONTIGUOUS"]:
            self._mask_array = np.ascontiguousarray(self._mask_array)
        self._init_mask_qimage()
        self.update()

    def get_denoise_mask(self) -> Optional[np.ndarray]:
        if self._mask_array is None:
            return None
        return (self._mask_array.astype(np.float32) / 255.0).clip(0.0, 1.0)

    def clear_denoise_mask(self) -> None:
        if self._mask_array is not None:
            self._mask_array.fill(0)
            self.update()
            self.mask_changed.emit()

    def fill_denoise_mask(self) -> None:
        if self._mask_array is None and self.pixmap is not None and self.pixmap.width() > 0:
            self._mask_array = np.full((self.pixmap.height(), self.pixmap.width()), 255, dtype=np.uint8)
            self._init_mask_qimage()
        if self._mask_array is not None:
            self._mask_array.fill(255)
            self.update()
            self.mask_changed.emit()

    def set_mask_edit_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self.maskEditMode != enabled:
            self.maskEditMode = enabled
            if enabled:
                if self._mask_array is None and self.pixmap is not None and self.pixmap.width() > 0:
                    self._mask_array = np.zeros((self.pixmap.height(), self.pixmap.width()), dtype=np.uint8)
                    self._init_mask_qimage()
                self._update_brush_cursor()
            else:
                self.unsetCursor()
            self.update()

    def is_mask_edit_mode(self) -> bool:
        return self.maskEditMode

    def set_brush_radius(self, r: int) -> None:
        new_r = max(2, min(500, int(r)))
        if self.brushRadius != new_r:
            self.brushRadius = new_r
            if self.maskEditMode:
                self._update_brush_cursor()
            self.brush_radius_changed.emit(self.brushRadius)

    def _update_brush_cursor(self) -> None:
        if not self.maskEditMode:
            self.unsetCursor()
            return

        size = int(self.brushRadius * 2)
        if size < 6:
            size = 6
        if size > 128:
            self.setCursor(Qt.CrossCursor)
            return

        pixmap = QPixmap(size + 4, size + 4)
        pixmap.fill(Qt.transparent)
        p = QPainter(pixmap)
        p.setRenderHint(QPainter.Antialiasing)
        outline = themed_color("#0f172a", self.palette())
        outline.setAlpha(180)
        p.setPen(QPen(outline, 2))
        p.drawEllipse(2, 2, size, size)
        highlight = themed_color("#ffffff", self.palette(), "background")
        highlight.setAlpha(240)
        p.setPen(QPen(highlight, 1))
        p.drawEllipse(2, 2, size, size)
        center = size // 2 + 2
        p.drawPoint(center, center)
        p.end()

        cursor = QCursor(pixmap, center, center)
        self.setCursor(cursor)

    def _paint_mask_stroke(self, p1: QPointF, p2: QPointF) -> None:
        if self._mask_array is None or self.scale is None or self.scale <= 0:
            return

        x1 = int(round((p1.x() - self.posX) / self.scale))
        y1 = int(round((p1.y() - self.posY) / self.scale))
        x2 = int(round((p2.x() - self.posX) / self.scale))
        y2 = int(round((p2.y() - self.posY) / self.scale))

        r = max(1, int(round(self.brushRadius / self.scale)))
        val = 255 if self.brushMode == "paint" else 0
        thickness = max(1, 2 * r)

        if x1 == x2 and y1 == y2:
            cv2.circle(self._mask_array, (x2, y2), r, int(val), -1)
        else:
            cv2.circle(self._mask_array, (x1, y1), r, int(val), -1)
            cv2.line(self._mask_array, (x1, y1), (x2, y2), int(val), thickness)
            cv2.circle(self._mask_array, (x2, y2), r, int(val), -1)

        self.update()

    # -------------------------------------------------------------------------
    # Gradient Mask Overlay Methods
    # -------------------------------------------------------------------------

    def _init_gradient_mask_qimage(self) -> None:
        if self._gradient_mask_array is None:
            self._gradient_mask_qimage = None
            return
        h, w = self._gradient_mask_array.shape[:2]
        if not self._gradient_mask_array.flags["C_CONTIGUOUS"]:
            self._gradient_mask_array = np.ascontiguousarray(self._gradient_mask_array)
        self._gradient_mask_qimage = QImage(
            self._gradient_mask_array.data,
            w,
            h,
            self._gradient_mask_array.strides[0],
            QImage.Format_Indexed8,
        )
        color_table = [
            qRgba(255, 30, 30, int(i * 0.65)) if i > 2 else qRgba(0, 0, 0, 0)
            for i in range(256)
        ]
        self._gradient_mask_qimage.setColorTable(color_table)

    def set_gradient_mask(self, mask: Optional[np.ndarray]) -> None:
        if mask is None:
            self._gradient_mask_array = None
            self._gradient_mask_qimage = None
            self.update()
            return

        if self.pixmap is not None and self.pixmap.width() > 0 and self.pixmap.height() > 0:
            pw, ph = self.pixmap.width(), self.pixmap.height()
            if mask.shape[:2] != (ph, pw):
                mask = cv2.resize(mask.astype(np.float32), (pw, ph), interpolation=cv2.INTER_LINEAR)

        if mask.dtype != np.uint8:
            self._gradient_mask_array = (np.clip(mask, 0.0, 1.0) * 255.0).astype(np.uint8)
        else:
            self._gradient_mask_array = mask.copy()

        if not self._gradient_mask_array.flags["C_CONTIGUOUS"]:
            self._gradient_mask_array = np.ascontiguousarray(self._gradient_mask_array)
        self._init_gradient_mask_qimage()
        self.update()

    def get_gradient_mask(self) -> Optional[np.ndarray]:
        if self._gradient_mask_array is None:
            return None
        return (self._gradient_mask_array.astype(np.float32) / 255.0).clip(0.0, 1.0)

    def set_gradient_mask_visible(self, visible: bool) -> None:
        self.gradientMaskVisible = bool(visible)
        self.update()

    def is_gradient_mask_visible(self) -> bool:
        return self.gradientMaskVisible

    # -------------------------------------------------------------------------
    # Live Horizon Tuning Overlay Methods
    # -------------------------------------------------------------------------

    def set_horizon_overlay(self, arr: np.ndarray, rect: Tuple[int, int, int, int]) -> None:
        self.set_horizon_patches([(arr, rect)])

    def set_horizon_patches(self, patches) -> None:
        """Replace a preview atomically without creating a full-image overlay."""
        prepared = []
        for arr, rect in patches:
            h, w = arr.shape[:2]
            u8 = np.ascontiguousarray((np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8))
            if u8.ndim == 3:
                qimg = QImage(u8.data, w, h, u8.strides[0], QImage.Format_RGB888)
            else:
                qimg = QImage(u8.data, w, h, u8.strides[0], QImage.Format_Grayscale8)
            prepared.append((QPixmap.fromImage(qimg.copy()), rect))
        self._horizon_overlay_patches = prepared
        # Retain the single-patch inspection API without assembling the tiles.
        self._horizon_overlay_arr = patches[0][0] if patches else None
        self._horizon_overlay_rect = patches[0][1] if patches else None
        self._horizon_overlay_pixmap = prepared[0][0] if prepared else None
        self.update()

    def clear_horizon_overlay(self) -> None:
        self.set_horizon_patches([])

    def setPixmap(self, pixmap: QPixmap, doResetZoomAndPosition: bool = True) -> None:
        self.pixmap = pixmap
        if pixmap is None or pixmap.width() == 0 or pixmap.height() == 0:
            self.setText("To get started, choose Add Files in the sidebar.")
        else:
            self.setText("")

        if doResetZoomAndPosition:
            self.renderWidth = None
            self.renderHeight = None
            self.scale = None
            self.ratio = None
            self.updatePixMapDimensions()

            # Presevering zoom / position after user actions, but need to perform at initial load
            if self.zoom_factor == 1:
                self.resetZoomAndPosition()

        self.update()

    def resetZoomAndPosition(self) -> None:
        self.zoom_factor = 1
        # Center the pixmap within the QLabel
        if self.pixmap is not None:
            labelWidth: int = self.width()
            labelHeight: int = self.height()
            imageWidth: int = self.pixmap.width()
            imageHeight: int = self.pixmap.height()
            labelWidth: int = self.width()
            labelHeight: int = self.height()

            if imageWidth == 0 or imageHeight == 0:
                return

            ratio: float = min(labelWidth / imageWidth, labelHeight / imageHeight)
            self.renderWidth: int = int(imageWidth * ratio * self.zoom_factor)
            self.renderHeight: int = int(imageHeight * ratio * self.zoom_factor)

            self.posX = (labelWidth - self.renderWidth) // 2
            self.posY = (labelHeight - self.renderHeight) // 2

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self.maskEditMode and (event.modifiers() & Qt.ControlModifier):
            delta = event.angleDelta().y()
            step = 5 if delta > 0 else -5
            self.set_brush_radius(self.brushRadius + step)
            event.accept()
            return

        # Note: This is an unusual kind of event that contains a relative delta. We're storing the value for the most recent event, but might need to aggregate.
        self.pendingWheelDelta = event.angleDelta().y()
        # Only trigger zoom/repaint after wheel events have settled for 5ms
        self.wheelDebounceTimer.start(5)

    def _debouncedWheelAction(self) -> None:
        old_zoom_factor = self.zoom_factor
        if self.pendingWheelDelta < 0:
            self.zoom_factor /= 1.1
        if self.pendingWheelDelta > 0:
            self.zoom_factor *= 1.1

        # Calculate the new position to keep the mouse position at the same place
        self.posX = self.mouseX - (self.mouseX - self.posX) * (self.zoom_factor / old_zoom_factor)
        self.posY = self.mouseY - (self.mouseY - self.posY) * (self.zoom_factor / old_zoom_factor)
        self.repaint()

    @staticmethod
    def moveMaskFromAutoToManual(mask, auto_masks_list, manual_masks_list):
        for i, m in enumerate(auto_masks_list):
            if np.array_equal(mask, m):
                auto_masks_list.pop(i)
                manual_masks_list.append(mask)
                return True
        return False

    def checkMaskContains(self, masks, x, y):
        if self.scale is None:
            return

        match = None
        for idx, mask in enumerate(masks):
            polygon = self.translateAndScalePoints(mask, self.scale)
            path = QPainterPath()
            path.addPolygon(polygon)
            if path.contains(QPointF(x, y)):
                match = idx
                break
        return match

    def mousePressEvent(self, ev: QMouseEvent) -> None:
        super().mousePressEvent(ev)
        pos = ev.position()
        self.mouseX = pos.x()
        self.mouseY = pos.y()

        # Denoise mask brush painting
        if self.maskEditMode and self._mask_array is not None:
            if ev.button() == Qt.LeftButton:
                self._is_brush_painting = True
                self.brushMode = "paint"
                self._last_brush_pos = pos
                self._paint_mask_stroke(pos, pos)
                return
            elif ev.button() == Qt.RightButton:
                self._is_brush_painting = True
                self.brushMode = "erase"
                self._last_brush_pos = pos
                self._paint_mask_stroke(pos, pos)
                return
            elif ev.button() == Qt.MiddleButton:
                self.dragX = pos.x() - self.posX
                self.dragY = pos.y() - self.posY
                return

        if ev.button() == Qt.LeftButton:
            self.dragX = pos.x() - self.posX
            self.dragY = pos.y() - self.posY

            if isinstance(self.file, InputFile):
                if len(self.file.activeMaskPoints) > 0:
                    self.file.streaksManualMasks.append(np.array(self.file.activeMaskPoints).astype(np.int64))
                    self.file.activeMaskPoints = []
                    self.repaint()
                    self.signals.updateFile.emit(self.file)

        if self.findBrightestMode and isinstance(self.file, OutputFile):
            if ev.button() == Qt.LeftButton:
                ratio = self.ratio if self.ratio else 1.0
                zoom = self.zoom_factor if self.zoom_factor else 1.0
                self.signals.findBrightestFrame.emit(self.file,
                                                     int((pos.x() - self.posX) / zoom / ratio),
                                                     int((pos.y() - self.posY) / zoom / ratio))
                self.setFindBrightestMode(False)
                return

        if isinstance(self.file, OutputFile):
            if ev.modifiers() == Qt.ShiftModifier:
                self.signals.findBrightestFrame.emit(self.file,
                                                     int((pos.x() - self.posX) / self.zoom_factor / self.ratio),
                                                     int((pos.y() - self.posY) / self.zoom_factor / self.ratio))

        # Check if the mouse is over any mask
        if isinstance(self.file, InputFile):
            if self.scale is None:
                return

            # Delete mask
            if ev.modifiers() == Qt.ShiftModifier:
                idx = self.checkMaskContains(self.file.streaksMasks, pos.x(), pos.y())
                if idx is not None:
                    deletedMask = self.file.streaksMasks.pop(idx)
                    self.file.streaksManualDeletedMasks.append(deletedMask)
                    self.repaint()
                    self.signals.updateFile.emit(self.file)
                else:
                    idx = self.checkMaskContains(self.file.streaksManualMasks, pos.x(), pos.y())
                    if idx is not None:
                        self.file.streaksManualMasks.pop(idx)
                        self.repaint()
                        self.signals.updateFile.emit(self.file)

            # Edit mask
            else:
                for mask in self.file.streaksMasks + self.file.streaksManualMasks:
                    polygon = self.translateAndScalePoints(mask, self.scale)
                    # nub
                    for idx, point in enumerate(mask):
                        path = QPainterPath()
                        path.addEllipse(polygon[idx], self.NUB_SIZE_TOLERANT, self.NUB_SIZE_TOLERANT)
                        if path.contains(QPointF(pos.x(), pos.y())):
                            self.selectedNub = (mask, idx, (point[0], point[1]))
                            self.draggingNub = True
                            # If this was an auto-generated mask, switch it to manual
                            self.moveMaskFromAutoToManual(
                                mask,
                                self.file.streaksMasks,
                                self.file.streaksManualMasks,
                            )
                            break

                    # mask
                    path = QPainterPath()
                    path.addPolygon(polygon)
                    if not self.draggingNub and path.contains(QPointF(pos.x(), pos.y())):
                        self.selectedMask = (mask, [point.copy() for point in mask])
                        self.draggingMask = True
                        # If this was an auto-generated mask, switch it to manual
                        self.moveMaskFromAutoToManual(
                            mask, self.file.streaksMasks, self.file.streaksManualMasks
                        )
                        break

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        super().mouseMoveEvent(ev)
        pos = ev.position()
        self.mouseX = pos.x()
        self.mouseY = pos.y()

        if self._is_brush_painting and self._mask_array is not None:
            curr_pos = pos
            prev_pos = self._last_brush_pos if self._last_brush_pos is not None else curr_pos
            self._paint_mask_stroke(prev_pos, curr_pos)
            self._last_brush_pos = curr_pos
            return

        if ev.buttons() == Qt.LeftButton:
            if self.draggingNub and self.selectedNub:
                if self.renderWidth is None:
                    return

                mask, idx, point = self.selectedNub
                dx = ((self.mouseX-self.posX)/self.scale - self.dragX/self.scale)
                dy = ((self.mouseY-self.posY)/self.scale - self.dragY/self.scale)
                mask[idx][0] = point[0] + dx
                mask[idx][1] = point[1] + dy

            elif self.draggingMask and self.selectedMask:
                dx = ((self.mouseX-self.posX)/self.scale - self.dragX/self.scale)
                dy = ((self.mouseY-self.posY)/self.scale - self.dragY/self.scale)
                for i, point in enumerate(self.selectedMask[1]):
                    self.selectedMask[0][i][0] = point[0] + dx
                    self.selectedMask[0][i][1] = point[1] + dy
            else:
                self.posX = pos.x() - self.dragX
                self.posY = pos.y() - self.dragY

        self.mouseMoveDebounceTimer.start(5)

    def _debouncedMouseMoveAction(self) -> None:
        self.repaint()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        super().mouseReleaseEvent(ev)
        if self._is_brush_painting:
            self._is_brush_painting = False
            self._last_brush_pos = None
            self.mask_changed.emit()
            return

        if ev.button() == Qt.LeftButton:
            if self.draggingMask or self.draggingNub:
                self.signals.updateFile.emit(self.file)
            self.draggingMask = False
            self.selectedMask = None
            self.draggingNub = False
            self.selectedNub = None

        if ev.button() == Qt.RightButton:
            if isinstance(self.file, InputFile):
                self.file.activeMaskPoints.append([(ev.position().x() - self.posX) / self.zoom_factor / self.ratio,
                                                   (ev.position().y() - self.posY) / self.zoom_factor / self.ratio])
                self.repaint()

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.resetZoomAndPosition()
        self.repaint()

    def updatePixMapDimensions(self):
        if self.pixmap is not None and self.pixmap.width() > 0 and self.pixmap.height() > 0:
            imageWidth: int = self.pixmap.width()
            imageHeight: int = self.pixmap.height()
            labelWidth: int = self.width()
            labelHeight: int = self.height()
            ratio: float = min(labelWidth / imageWidth, labelHeight / imageHeight)
            renderWidth: int = int(imageWidth * ratio * self.zoom_factor)
            renderHeight: int = int(imageHeight * ratio * self.zoom_factor)

            if renderWidth is None:
                return

            if renderWidth < labelWidth and renderHeight < labelHeight:
                self.resetZoomAndPosition()
                renderWidth = int(imageWidth * ratio * self.zoom_factor)
                renderHeight = int(imageHeight * ratio * self.zoom_factor)

            scale = renderWidth / imageWidth
            self.renderWidth = renderWidth
            self.renderHeight = renderHeight
            self.scale = scale
            self.ratio = ratio

            return renderWidth, renderHeight, ratio

        return None, None, None

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self.pixmap is not None and self.pixmap.width() > 0 and self.pixmap.height() > 0:

            self.updatePixMapDimensions()

            newPixmap = self.pixmap.scaled(self.renderWidth, self.renderHeight,
                                           Qt.KeepAspectRatio, Qt.SmoothTransformation)

            x: int = self.posX
            y: int = self.posY
            painter = QPainter(self)
            painter.setRenderHint(QPainter.SmoothPixmapTransform, True) # Note: Needed for antialising on Windows
            painter.drawPixmap(x, y, newPixmap)

            # Use one image-coordinate transform for all patches to avoid rounded tile gaps.
            if self._horizon_overlay_patches and self.scale is not None:
                painter.save()
                painter.translate(self.posX, self.posY)
                painter.scale(self.scale, self.scale)
                for patch, (ox, oy, ow, oh) in self._horizon_overlay_patches:
                    painter.drawPixmap(QPointF(ox, oy), patch)
                painter.restore()

            # Draw gradient mask overlay (translucent red) if active
            if self.gradientMaskVisible and self._gradient_mask_qimage is not None:
                img_rect = QRect(self.posX, self.posY, self.renderWidth, self.renderHeight)
                painter.drawImage(img_rect, self._gradient_mask_qimage)

            # Draw denoise sky mask overlay (translucent green) if active
            if self.maskEditMode and self._mask_qimage is not None:
                img_rect = QRect(self.posX, self.posY, self.renderWidth, self.renderHeight)
                painter.drawImage(img_rect, self._mask_qimage)

            imgMousePos = self.translateAndScaleMousePoint(self.mouseX, self.mouseY, self.ratio)

            if isinstance(self.file, InputFile):
                if self.file.streaksMasks is not None:
                    for mask in self.file.streaksMasks:
                        self.drawMask(mask, QColor(0, 255, 0, 255), self.scale, painter)

                if self.file.streaksManualMasks is not None:
                    for mask in self.file.streaksManualMasks:
                        self.drawMask(mask, QColor(0, 255, 255, 255), self.scale, painter)

                if self.showDeletedMasks and self.file.streaksManualDeletedMasks is not None:
                    for mask in self.file.streaksManualDeletedMasks:
                        self.drawMask(mask, QColor(255, 0, 0, 255), self.scale, painter)

                if len(self.file.activeMaskPoints) > 0:
                    pen = QPen()
                    pen.setWidth(1)
                    pen.setColor(QColor("#FFFF00"))
                    painter.setPen(pen)
                    pts = self.file.activeMaskPoints.copy()
                    # current mouse position
                    pts.append(imgMousePos)
                    painter.drawPolyline(self.translateAndScalePoints(pts, self.scale))

    def drawMask(self, mask: List[List[float]], color: QColor, scale: float, painter: QPainter) -> None:
        # Translucent color
        colorT = QColor(color)
        colorT.setAlpha(64)

        pen = QPen()
        pen.setWidth(1)
        pen.setColor(color)
        polygon = self.translateAndScalePoints(mask, scale)
        path = QPainterPath()
        path.addPolygon(polygon)
        for point in polygon:
            path.addEllipse(point, self.NUB_SIZE_TOLERANT, self.NUB_SIZE_TOLERANT)
        if path.contains(QPointF(self.mouseX, self.mouseY)):
            pen2 = QPen()
            pen2.setWidth(1)
            pen2.setColor(QColor("#FFFFFF"))
            painter.setPen(pen2)
            for point in polygon:
                painter.drawEllipse(point, self.NUB_SIZE, self.NUB_SIZE)
            painter.setBrush(colorT)
        painter.setPen(pen)
        painter.drawPolygon(polygon)
        painter.setBrush(Qt.NoBrush)

    def translateAndScalePoints(self, points: List[List[float]], scale: float) -> List[QPointF]:
        return [QPointF(point[0] * scale + self.posX, point[1] * scale + self.posY) for point in points]

    def translateAndScaleMousePoint(self, x: int, y: int, scale: float) -> List[float]:
        return [(x - self.posX) / self.zoom_factor / scale, (y - self.posY) / self.zoom_factor / scale]
