from functools import partial
from PySide6.QtCore import QObject, Signal, QThreadPool, SignalInstance
from PySide6.QtWidgets import QWidget, QPushButton, QFrame

from startrails.ui.file import File

import time
from PySide6.QtCore import QThread, QRunnable


class AsyncWorker(QRunnable):
    def __init__(self, work, parent=None):
        super().__init__(parent)
        self.signals = getSignals()
        self.work = work

    def run(self):
        if not QThread.currentThread().isInterruptionRequested():
            self.work()
            time.sleep(0.01)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Signals(QObject):
    startProgress: Signal = Signal(int, str)
    incrementProgress: Signal = Signal(object, int, int, int, bool, object)

    showFile: Signal = Signal(File)
    updateGPUStats: Signal = Signal()
    findBrightestFrame: Signal = Signal(File, int, int)

    updateFile: Signal = Signal(File)
    updateFileButton: Signal = Signal(File)

    makeButton: Signal = Signal(File, QWidget, int)
    addFileButton: Signal = Signal(QWidget, QPushButton, bool)
    focusFile: Signal = Signal(File)
    updateThumbnails: Signal = Signal(QWidget)
    updateThumbnail: Signal = Signal(QFrame, QWidget)
    drawInputFileList: Signal = Signal(File)
    drawOutputFileList: Signal = Signal(File)

    removeFile: Signal = Signal(File, QPushButton)
    excludeFile: Signal = Signal(File, QPushButton)


lowpri_threadpool = QThreadPool()
lowpri_threadpool.setMaxThreadCount(1)


def emitLater(emit, *args, priority=0):
    worker = AsyncWorker(partial(emit, *args))
    pool = lowpri_threadpool
    pool.start(worker, priority=priority)


signals = Signals()


# global accessor for shared Signals
def getSignals():
    return signals
