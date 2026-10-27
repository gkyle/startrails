from tqdm import tqdm
from contextlib import contextmanager
from contextvars import ContextVar
from PySide6.QtWidgets import QProgressBar, QLabel

from startrails.ui.signals import getSignals

_TASK_TOKEN = ContextVar("progress_task_token", default=None)


@contextmanager
def progress_scope(task_token):
    token = _TASK_TOKEN.set(task_token)
    try:
        yield
    finally:
        _TASK_TOKEN.reset(token)


class ProgressBarUpdater(tqdm):
    def __init__(self, qpbar: QProgressBar, qlabel: QLabel, *args, suppressStdout=True, result_guard=None, **kwargs):
        self.suppressStdout = suppressStdout
        kwargs['gui'] = suppressStdout
        tqdm.__init__(self, *args, **kwargs)
        self.qpbar = qpbar
        self.qlabel = qlabel
        self.signals = getSignals()
        self.task_token = _TASK_TOKEN.get()
        self.result_guard = result_guard

        self.total = None
        if 'total' in kwargs:
            self.total = kwargs['total']
        self.desc = None
        if 'desc' in kwargs:
            self.desc = kwargs['desc']

    def display(self, msg=None, pos=None):
        # Keep tqdm's counters and timing, but render GUI progress without requiring
        # a console stream (pythonw.exe has no stdout or stderr).
        if not self.suppressStdout:
            return super().display(msg, pos)

    def update(self, n=1):
        super().update(n)
        if self.qlabel is not None:
            self.qlabel.setText(self.desc)
        if self.qpbar is not None and self.total:
            self.qpbar.setValue(int(self.n / self.total * 100))
            f = self.format_meter(self.n, self.total, self._time() - self.start_t,
                                  bar_format="{n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}{postfix}]")
            self.qpbar.setFormat(f"{f}")

    def tick(self, *args):
        self.signals.incrementProgress.emit(self, *args)
