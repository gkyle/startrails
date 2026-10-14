"""Shared cancellation that survives transitions between denoise stages."""
from threading import Event
from startrails.lib.util import Observable


class DenoiseOperation(Observable):
    def __init__(self, cancel_event=None, cancel_check=None):
        super().__init__()
        self.cancel_event = cancel_event if cancel_event is not None else Event()
        self.cancel_check = cancel_check

    def requestInterrupt(self):  # noqa: N802 - legacy Observable interface
        self.cancel_event.set()
        super().requestInterrupt()

    def shouldInterrupt(self):  # noqa: N802 - legacy Observable interface
        return self.cancel_event.is_set() or super().shouldInterrupt() or bool(
            self.cancel_check and self.cancel_check()
        )
