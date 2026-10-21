"""Clickable labels for Designer-authored checkbox rows."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QLabel


class CheckboxLabel(QLabel):
    """Activate the checkbox declared as this label's Designer buddy."""

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton and isinstance(self.buddy(), QCheckBox):
            self._pressed = True
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt override
        if event.button() == Qt.LeftButton and getattr(self, "_pressed", False):
            self._pressed = False
            checkbox = self.buddy()
            if isinstance(checkbox, QCheckBox) and checkbox.isEnabled() and self.rect().contains(event.position().toPoint()):
                checkbox.click()
            event.accept()
            return
        super().mouseReleaseEvent(event)
