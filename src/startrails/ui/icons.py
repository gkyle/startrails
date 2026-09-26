"""Vector icon helpers matching Pyquator's clean icon style."""
import math
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def create_star_icon(color: QColor = QColor("#0284c7"), size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(color))
    cx, cy = size / 2.0, size / 2.0
    r_outer = size * 0.46
    r_inner = size * 0.20
    path = QPainterPath()
    for i in range(10):
        r = r_outer if i % 2 == 0 else r_inner
        angle = -math.pi / 2 + i * math.pi / 5
        x = cx + r * math.cos(angle)
        y = cy + r * math.sin(angle)
        if i == 0:
            path.moveTo(x, y)
        else:
            path.lineTo(x, y)
    path.closeSubpath()
    painter.drawPath(path)
    painter.end()
    return QIcon(pixmap)


def create_doc_icon(color: QColor = QColor("#64748b"), size: int = 16) -> QIcon:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)

    l = 3.0
    r = size - 3.0
    t = 1.5
    b = size - 1.5
    fold = 4.0

    path = QPainterPath()
    path.moveTo(l, t)
    path.lineTo(r - fold, t)
    path.lineTo(r, t + fold)
    path.lineTo(r, b)
    path.lineTo(l, b)
    path.closeSubpath()

    painter.setPen(QPen(color, 1.3))
    painter.setBrush(QBrush(QColor(color.red(), color.green(), color.blue(), 25)))
    painter.drawPath(path)

    fold_path = QPainterPath()
    fold_path.moveTo(r - fold, t)
    fold_path.lineTo(r - fold, t + fold)
    fold_path.lineTo(r, t + fold)
    painter.setBrush(Qt.NoBrush)
    painter.drawPath(fold_path)

    painter.end()
    return QIcon(pixmap)
