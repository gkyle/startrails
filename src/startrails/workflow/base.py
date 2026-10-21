"""Base abstract workflow defining the interface for mode-specific pipelines."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from startrails.app import App


class Workflow(ABC):
    """Abstract base workflow managing mode-specific operations and project data."""

    def __init__(self, app: App):
        self.app = app

    @property
    @abstractmethod
    def mode_name(self) -> str:
        """Human-readable identifier for this workflow mode."""
        ...

    @property
    @abstractmethod
    def project(self) -> Any:
        """The active project model instance managed by this workflow."""
        ...

    def save_project(self) -> None:
        """Persist project state through the central app controller."""
        self.app.saveProject()

    def do_interrupt_operation(self) -> None:
        """Request interruption of any active long-running operation."""
        self.app.doInterruptOperation()
