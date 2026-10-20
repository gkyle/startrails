"""Progress overlay component that floats over the canvas during operations."""
import time
from typing import Optional
from PySide6.QtCore import Qt, QRectF, QTimer, QEvent
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout, QGraphicsDropShadowEffect

from .ui_progress_overlay import Ui_ProgressOverlay


class ProgressSpinner(QWidget):
    """Animated circular ring spinner with an active glowing arc."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(30, 30)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)

    def start(self):
        if not self._timer.isActive():
            self._timer.start(30)

    def stop(self):
        self._timer.stop()

    def _rotate(self):
        self._angle = (self._angle + 6) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        rect = QRectF(3, 3, 24, 24)

        # Track circle
        track_pen = QPen(QColor("#334155"), 3.5)
        track_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        # Spinning arc
        arc_pen = QPen(QColor("#38bdf8"), 3.5)
        arc_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(arc_pen)
        painter.drawArc(rect, -self._angle * 16, 100 * 16)


class ProgressOverlay(QFrame):
    """Overlay card displaying progress, status, elapsed time, and ETA."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.ui = Ui_ProgressOverlay()
        self.ui.setupUi(self)

        # Drop shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 160))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        # Add animated spinner into spinnerContainer
        spinner_layout = QVBoxLayout(self.ui.spinnerContainer)
        spinner_layout.setContentsMargins(0, 0, 0, 0)
        self.spinner = ProgressSpinner(self.ui.spinnerContainer)
        spinner_layout.addWidget(self.spinner)

        # Expose widgets directly for compatibility with existing code
        self.progressBar = self.ui.progressBar
        self.label_progressBar = self.ui.label_progressBar
        self.pushButton_cancelOp = self.ui.pushButton_cancelOp
        self.label_progressTitle = self.ui.label_progressTitle
        self.label_progressPercent = self.ui.label_progressPercent
        self.label_progressElapsed = self.ui.label_progressElapsed
        self.label_progressETA = self.ui.label_progressETA

        # Continuous heartbeat timer for elapsed and ETA updates between observable ticks
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._on_tick)
        self._start_time: Optional[float] = None
        self._target_finish_time: Optional[float] = None
        self._last_n: int = 0
        self._last_total: int = 0

        # Listen to parent resize events to stay centered
        if parent is not None:
            parent.installEventFilter(self)

        self.hide()

    def eventFilter(self, watched, event):
        if watched is self.parentWidget() and event.type() == QEvent.Resize:
            self.update_position()
        return super().eventFilter(watched, event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        if self._start_time is not None and not self._timer.isActive():
            self._timer.start()

    def update_position(self):
        parent = self.parentWidget()
        if parent is not None:
            x = max(10, (parent.width() - self.width()) // 2)
            self.move(x, 24)
            self.raise_()

    @staticmethod
    def _format_time(seconds):
        if seconds is None or seconds < 0:
            return "--:--:--"
        m, s = divmod(int(round(seconds)), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def start(self, title="Processing", total=0, desc=""):
        now = time.monotonic()
        self._start_time = now
        self._target_finish_time = None
        self._last_n = 0
        self._last_total = int(total) if total is not None else 0

        self.label_progressTitle.setText(title)
        subtitle = desc if desc else (f"Processing frame 0 of {total}" if total else "Processing...")
        self.label_progressBar.setText(subtitle)
        self.progressBar.setRange(0, 100)
        self.progressBar.setValue(0)
        self.label_progressPercent.setText("0%")
        self.label_progressElapsed.setText("Elapsed <b style='color:#f8fafc'>00:00:00</b>")
        self.label_progressETA.setText("ETA <b style='color:#f8fafc'>--:--:--</b>")
        self.pushButton_cancelOp.setEnabled(True)
        self.spinner.start()
        self._timer.start()
        self.update_position()
        self.show()
        self.raise_()

    def update_progress(self, n, total, elapsed=None, remaining=None, desc=""):
        if self.isHidden():
            self.spinner.start()
            self.update_position()
            self.show()
            self.raise_()

        now = time.monotonic()
        if elapsed is not None:
            self._start_time = now - max(0.0, float(elapsed))
        elif self._start_time is None:
            self._start_time = now

        self._last_n = int(n)
        self._last_total = int(total) if total is not None else 0

        if remaining is not None and remaining >= 0:
            self._target_finish_time = now + float(remaining)
        elif self._last_total > 0 and self._last_n > 0 and self._last_n < self._last_total:
            elapsed_sec = max(0.001, now - self._start_time)
            rate = self._last_n / elapsed_sec
            if rate > 0:
                self._target_finish_time = now + ((self._last_total - self._last_n) / rate)
        elif self._last_total > 0 and self._last_n >= self._last_total:
            self._target_finish_time = now
        else:
            self._target_finish_time = None

        if self._last_total > 0:
            pct = min(100, max(0, int(self._last_n / self._last_total * 100)))
            self.progressBar.setValue(pct)
            self.label_progressPercent.setText(f"{pct}%")
            subtitle = f"Processing frame {n} of {total}" if not desc or desc.endswith(":") else f"{desc} {n} of {total}"
            self.label_progressBar.setText(subtitle)
        else:
            self.progressBar.setValue(0)
            self.label_progressPercent.setText("0%")
            if desc:
                self.label_progressBar.setText(desc)

        # Immediate visual update for the report
        if elapsed is not None:
            elapsed_str = self._format_time(elapsed)
            self.label_progressElapsed.setText(f"Elapsed <b style='color:#f8fafc'>{elapsed_str}</b>")
        else:
            cur_elapsed = max(0.0, now - self._start_time)
            self.label_progressElapsed.setText(f"Elapsed <b style='color:#f8fafc'>{self._format_time(cur_elapsed)}</b>")

        if remaining is not None:
            eta_str = self._format_time(remaining)
            self.label_progressETA.setText(f"ETA <b style='color:#f8fafc'>{eta_str}</b>")
        elif self._target_finish_time is not None:
            eta_str = self._format_time(max(0.0, self._target_finish_time - now))
            self.label_progressETA.setText(f"ETA <b style='color:#f8fafc'>{eta_str}</b>")
        else:
            self.label_progressETA.setText("ETA <b style='color:#f8fafc'>--:--:--</b>")

        if not self._timer.isActive():
            self._timer.start()

    def _on_tick(self):
        if self.isHidden() or self._start_time is None:
            return

        now = time.monotonic()
        elapsed = max(0.0, now - self._start_time)
        elapsed_str = self._format_time(elapsed)
        self.label_progressElapsed.setText(f"Elapsed <b style='color:#f8fafc'>{elapsed_str}</b>")

        if self._target_finish_time is not None:
            rem = self._target_finish_time - now
            if rem <= 0:
                if self._last_total > 0 and 0 < self._last_n < self._last_total:
                    # Current operation took longer than estimated; dynamically recalibrate
                    rate = self._last_n / elapsed if elapsed > 0 else 0
                    if rate > 0:
                        rem = max(1.0, (self._last_total - self._last_n) / rate)
                        self._target_finish_time = now + rem
                    else:
                        rem = None
                elif self._last_total > 0 and self._last_n >= self._last_total:
                    rem = 0.0
                else:
                    rem = None

            if rem is not None:
                eta_str = self._format_time(max(0.0, rem))
                self.label_progressETA.setText(f"ETA <b style='color:#f8fafc'>{eta_str}</b>")
            else:
                self.label_progressETA.setText("ETA <b style='color:#f8fafc'>--:--:--</b>")
        else:
            self.label_progressETA.setText("ETA <b style='color:#f8fafc'>--:--:--</b>")

    def finish(self):
        self._timer.stop()
        self._start_time = None
        self._target_finish_time = None
        self._last_n = 0
        self._last_total = 0
        self.spinner.stop()
        self.pushButton_cancelOp.setEnabled(True)
        self.hide()
