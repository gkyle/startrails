"""Base class and common interface for mode-specific UI views."""

from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Tuple
from PySide6.QtCore import QObject
from PySide6.QtWidgets import QWidget

from startrails.lib.file import File

if TYPE_CHECKING:
    from startrails.app import App
    from startrails.ui.ui_wrap import Ui_AppWindow


class ModeView(QObject):
    """Abstract interface for a per-mode UI view (sidebar and workflow controller)."""

    mode_name: str = ""

    def __init__(self, app: App, shell: Any):
        super().__init__()
        self.app = app
        self.shell = shell
        self.sidebar_widget: Optional[QWidget] = None
        self._signal_connections: List[Tuple[Any, Callable]] = []

    def build_sidebar(self, parent: QWidget) -> QWidget:
        """Construct and return the sidebar widget for this mode."""
        raise NotImplementedError

    def bind(self) -> None:
        """Connect UI signals, listeners, and workflow actions."""
        raise NotImplementedError

    def teardown(self) -> None:
        """Disconnect signals and clean up state when switching modes or closing."""
        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self._signal_connections.clear()

    def connect_signal(self, signal: Any, slot: Callable) -> None:
        """Helper to track connected signals for clean teardown."""
        signal.connect(slot)
        self._signal_connections.append((signal, slot))

    def resetProjectView(self) -> None:  # noqa: N802 - shared legacy view interface
        """Reset the sidebar view state when a new or opened project is active."""
        raise NotImplementedError

    def showFile(self, file: Optional[File]) -> None:  # noqa: N802 - shared legacy view interface
        """Handle preview/file display for this mode."""
        pass

    def updateReadyStates(self, _=None) -> None:  # noqa: N802 - shared legacy view interface
        """Update button enabled states based on project readiness."""
        pass
