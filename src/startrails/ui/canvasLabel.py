from typing import List, Optional, Tuple
import numpy as np
from PySide6.QtCore import (Qt, QPointF)
from PySide6.QtGui import (QPainter, QPaintEvent, QWheelEvent, QMouseEvent,
                           QPixmap, QColor, QPen, QPainterPath, QFont)
from PySide6.QtWidgets import QLabel, QWidget

from startrails.lib.file import File, InputFile, OutputFile
from startrails.ui.signals import Signals, getSignals


class CanvasLabel(QLabel):
    NUB_SIZE = 10
    NUB_SIZE_TOLERANT = 15

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

        self.setAlignment(Qt.AlignCenter)
        self.setFont(QFont("Arial", 20, QFont.Bold))
        self.setPixmap(pixmap)

    def setFile(self, file: File) -> None:
        # clear previous active mask points
        if isinstance(self.file, InputFile):
            self.file.activeMaskPoints = []

        if file is not None:
            self.file = file
            newPixmap = QPixmap(file.path)
            # Sometimes we're writing over a file at the same moment we try to replace the pixmap. Try to not replace useful pixels with nil.
            if newPixmap.width() > 0 and newPixmap.height() > 0:
                self.setPixmap(newPixmap, True)
        else:
            self.setPixmap(QPixmap(), True)

    def setPixmap(self, pixmap: QPixmap, doResetZoomAndPosition: bool = True) -> None:
        self.pixmap = pixmap
        if pixmap is None or pixmap.width() == 0 or pixmap.height() == 0:
            self.setText("To get started, click \"Add Star Images\" on the panel to the right")
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

        self.repaint()

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

    def setZoom(self, dir: int, mouseX: int, mouseY: int) -> None:
        old_zoom_factor = self.zoom_factor
        if dir < 0:
            self.zoom_factor /= 1.1
        if dir > 0:
            self.zoom_factor *= 1.1

        # Calculate the new position to keep the mouse position at the same place
        self.posX = mouseX - (mouseX - self.posX) * (self.zoom_factor / old_zoom_factor)
        self.posY = mouseY - (mouseY - self.posY) * (self.zoom_factor / old_zoom_factor)
        self.repaint()

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta: int = event.angleDelta().y()
        self.setZoom(delta, self.mouseX, self.mouseY)

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
        if ev.button() == Qt.LeftButton:
            self.dragX = ev.position().x() - self.posX
            self.dragY = ev.position().y() - self.posY

            # TODO: Is this a reasonable way to end a polygon? Dblclick instead?
            if isinstance(self.file, InputFile):
                if len(self.file.activeMaskPoints) > 0:
                    self.file.streaksManualMasks.append(np.array(self.file.activeMaskPoints).astype(np.int64))
                    self.file.activeMaskPoints = []
                    self.repaint()
                    if len(self.file.streaksManualMasks) == 1:
                        self.signals.updateFile.emit(self.file)

        if isinstance(self.file, OutputFile):
            if ev.modifiers() == Qt.ShiftModifier:
                self.signals.findBrightestFrame.emit(self.file,
                                                     int((ev.position().x() - self.posX) / self.zoom_factor / self.ratio),
                                                     int((ev.position().y() - self.posY) / self.zoom_factor / self.ratio))

        # Check if the mouse is over any mask
        if isinstance(self.file, InputFile):
            if self.scale is None:
                return

            if ev.modifiers() == Qt.ShiftModifier:
                idx = self.checkMaskContains(self.file.streaksMasks, ev.position().x(), ev.position().y())
                if idx is not None:
                    self.file.streaksMasks.pop(idx)
                    self.repaint()
                    if len(self.file.streaksMasks) == 0:
                        self.signals.updateFile.emit(self.file)
                else:
                    idx = self.checkMaskContains(self.file.streaksManualMasks, ev.position().x(), ev.position().y())
                    if idx is not None:
                        self.file.streaksManualMasks.pop(idx)
                        self.repaint()
                        if len(self.file.streaksManualMasks) == 0:
                            self.signals.updateFile.emit(self.file)

            else:
                for mask in self.file.streaksMasks + self.file.streaksManualMasks:
                    polygon = self.translateAndScalePoints(mask, self.scale)
                    # nub
                    for idx, point in enumerate(mask):
                        path = QPainterPath()
                        path.addEllipse(polygon[idx], self.NUB_SIZE_TOLERANT, self.NUB_SIZE_TOLERANT)
                        if path.contains(QPointF(ev.x(), ev.y())):
                            self.selectedNub = (mask, idx, (point[0], point[1]))
                            self.draggingNub = True
                            break

                    # mask
                    path = QPainterPath()
                    path.addPolygon(polygon)
                    if not self.draggingNub and path.contains(QPointF(ev.position().x(), ev.position().y())):
                        self.selectedMask = (mask, [point.copy() for point in mask])
                        self.draggingMask = True
                        break

    def mouseMoveEvent(self, ev: QMouseEvent) -> None:
        super().mouseMoveEvent(ev)
        self.mouseX = ev.position().x()
        self.mouseY = ev.position().y()
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
                self.posX = ev.position().x() - self.dragX
                self.posY = ev.position().y() - self.dragY

        self.repaint()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        super().mouseReleaseEvent(ev)
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

            imgMousePos = self.translateAndScaleMousePoint(self.mouseX, self.mouseY, self.ratio)

            if isinstance(self.file, InputFile):
                if self.file.streaksMasks is not None:
                    for mask in self.file.streaksMasks:
                        self.drawMask(mask, QColor(0, 255, 0, 255), self.scale, painter)

                if self.file.streaksManualMasks is not None:
                    for mask in self.file.streaksManualMasks:
                        self.drawMask(mask, QColor(0, 255, 255, 255), self.scale, painter)

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
