from PySide6.QtCore import QObject, Signal, QEvent
from PySide6.QtCore import QThread, QRunnable

from startrails.lib.file import File


class AsyncWorker(QRunnable):
    def __init__(self, work, parent=None):
        super().__init__(parent)
        self.signals = getSignals()
        self.work = work

    def run(self):
        try:
            if not QThread.currentThread().isInterruptionRequested():
                self.work()
        finally:
            try:
                self.signals.finishProgress.emit()
            except RuntimeError:
                pass


class Signals(QObject):
    startProgress: Signal = Signal(object, object, object)
    incrementProgress: Signal = Signal(object, int, int, int, bool, object)
    finishProgress: Signal = Signal()

    showFile: Signal = Signal(File)
    updateGPUStats: Signal = Signal()
    findBrightestFrame: Signal = Signal(File, int, int)
    sourceLookupReady: Signal = Signal(object)

    updateFile: Signal = Signal(File)
    fileMetadataChanged: Signal = Signal(File)
    refreshReadiness: Signal = Signal()

    focusFile: Signal = Signal(File)
    drawInputFileList: Signal = Signal(File)
    drawOutputFileList: Signal = Signal(File)

    windowResized: Signal = Signal(QEvent)
    windowMoved: Signal = Signal(QEvent)


signals = Signals()


# global accessor for shared Signals
def getSignals():
    return signals
