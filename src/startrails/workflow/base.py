"""Base abstract workflow defining the interface for mode-specific pipelines."""

from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import contextmanager
from threading import Event
from typing import TYPE_CHECKING, Any, Generator, Optional, Type, TypeVar

from startrails.lib.util import Observable

if TYPE_CHECKING:
    from startrails.app import App

T = TypeVar("T", bound=Observable)


class Workflow(ABC):
    """Abstract base workflow managing mode-specific operations and project data."""

    def __init__(self, app: App):
        self.app = app
        self._cancel_event = Event()
        self._session_operation: Optional[Observable] = None

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

    @contextmanager
    def operation_session(self) -> Generator[None, None, None]:
        """Scoped session providing shared cancellation across grouped operations."""
        self._cancel_event = Event()
        project = self.project
        revision = project.processing_revision
        session = Observable(
            cancel_event=self._cancel_event,
            cancel_check=lambda: (project is not self.app.project or revision != project.processing_revision),
        )
        session.startJob(1)
        self._session_operation = session
        self.app.activeOperation = session
        try:
            yield
        finally:
            self._session_operation = None
            if self.app.activeOperation is session:
                self.app.activeOperation = None

    def _new_operation(self, operation_type: Type[T], *args: Any, **kwargs: Any) -> T:
        """Instantiate an Observable operation bound to this session's cancellation contract."""
        project = self.project
        revision = project.processing_revision
        check = lambda: (project is not self.app.project or revision != project.processing_revision)
        if self._session_operation is not None:
            input_check = check
            session_check = self._session_operation.shouldInterrupt
            check = lambda: input_check() or session_check()
        token = self._cancel_event if self._session_operation is not None else Event()
        return operation_type(*args, cancel_event=token, cancel_check=check, **kwargs)
