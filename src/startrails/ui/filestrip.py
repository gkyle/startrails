from functools import partial
from typing import Dict, List
from PySide6.QtWidgets import QMenu, QPushButton, QLabel, QVBoxLayout, QFrame, QScrollArea, QSizePolicy
from PySide6.QtGui import QPixmap, QColor, QIcon, QPaintEvent, QPainter, QPalette, QFontMetrics
from PySide6.QtCore import QObject, Qt, QSize, QPoint, Signal
from PIL import Image
from PIL.ImageQt import ImageQt

from startrails.lib.file import File, InputFile
from startrails.ui.signals import emitLater, getSignals


class FileStrip:

    def __init__(self, frame: QFrame, frameContainer: QFrame, fileList: List[File], redrawSignal: Signal, maxVisibleButtons=-1):
        self.buttons: Dict[File, FileButton] = {}
        self.frame = frame
        self.frameContainer = frameContainer
        self.signals = getSignals()
        self.fileList = fileList
        self.maxVisibleButtons = maxVisibleButtons

        self.scroll = self.frameContainer.findChildren(QScrollArea)[0]
        self.scroll.horizontalScrollBar().valueChanged.connect(partial(self.slotUpdateThumbnails, self.frame))
        self.signals.updateThumbnail.connect(self.slotUpdateThumbnail)

        self.signals.updateFileButton.connect(self.update)
        self.signals.focusFile.connect(self.focusFile)
        self.signals.addFileButton.connect(self.slotAddFileButton)
        redrawSignal.connect(self.drawFileList)

        self.drawFileList()

    def removeButton(self, file: File):
        button = self.buttons.pop(file)
        button.deleteLater()

    def makeFileButton(self, file, doFocus, doPriority):
        button = FileButton(self.signals, file)
        self.buttons[file] = button

        priority = 10 if doPriority else 0
        emitLater(self.signals.addFileButton.emit, self.frame, button, doFocus, priority=priority)

    def setFileList(self, fileList: List[File]):
        self.fileList = fileList
        self.drawFileList()

    def drawFileList(self, focusOnFile: File = None):
        for child in self.frame.findChildren(QLabel):
            child.setParent(None)
            child.deleteLater()
        for child in self.frame.findChildren(QPushButton):
            child.setParent(None)
            child.deleteLater()

        for idx, file in enumerate(self.fileList):
            doFocus = False
            if focusOnFile is not None:
                if file == focusOnFile:
                    doFocus = True
            else:
                if idx == 0:
                    doFocus = True
            doPriority = idx < 10 if self.maxVisibleButtons < 0 else idx < self.maxVisibleButtons
            self.makeFileButton(file, doFocus, doPriority)

        if self.maxVisibleButtons > 0:
            self.fitMaxSize()

    def update(self, file: File):
        if file in self.buttons:
            self.buttons[file].updateIndicators()

    def fitMaxSize(self):
        c = len(self.fileList)
        if c > self.maxVisibleButtons:
            c = self.maxVisibleButtons
        self.frameContainer.setMinimumSize(QSize(c*160, 196))

    def focusFile(self, file: File):
        if file in self.buttons:
            self.buttons[file].setFocus()
            self.scroll.ensureWidgetVisible(self.buttons[file])

    def slotAddFileButton(self, frame: QFrame, button: QPushButton, forceFocus=False):
        # FYI: All instances of FileStrip will receieve this signals. Make sure it's meant for this instance.
        if frame == self.frame:
            frame.layout().addWidget(button, 0, Qt.AlignTop)
            if forceFocus:
                emitLater(self.signals.focusFile.emit, button.file, priority=10)
            # force frame relayout to adjust to content
            self.frame.layout().invalidate()
            self.frame.layout().activate()
            self.frame.updateGeometry()

    def slotUpdateThumbnails(self, frame, _=None):
        if frame == self.frame:
            for child in frame.findChildren(FileButton):
                if child.isVisible() and not child.renderedThumbnail and not child.visibleRegion().isEmpty():
                    emitLater(self.signals.updateThumbnail.emit, frame, child)

    def slotUpdateThumbnail(self, frame, button):
        if frame == self.frame:
            button.showEvent(None)


class IconLabel(QLabel):
    def __init__(self, file: File = None):
        super().__init__()
        self.file = file
        self.hasAutoMasks = False
        self.hasManualMasks = False
        self.isExcluded = False
        self.setFixedSize(QSize(128, 128))
        if not self.file is None:
            self.pixmap = QPixmap(file.path)
        else:
            self.pixmap = QPixmap(128, 128)
            self.pixmap.fill(self.palette().color(QPalette.Window))
        self.setAlignment(Qt.AlignCenter)

    def setFile(self, file: File) -> None:
        self.file = file
        try:
            image = Image.open(file.path)
            image.thumbnail((128, 128))
            qt_image = ImageQt(image)
            self.pixmap = QPixmap.fromImage(qt_image)
        except:
            pass
        self.updateIndicators()

    def updateIndicators(self):
        if isinstance(self.file, InputFile):
            self.hasAutoMasks = len(self.file.streaksMasks) > 0
            self.hasManualMasks = len(self.file.streaksManualMasks) > 0
            self.isExcluded = self.file.excludeFromStack

        self.repaint()

    def drawIndicator(self, painter: QPainter, color: QColor, offset: int):
        painter.setBrush(color)
        painter.setPen(color)
        painter.drawEllipse(128 - 15-offset, 5, 8, 8)
        offset += 12
        return offset

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)

        painter = QPainter(self)
        painter.drawPixmap(QPoint(0, 0), self.pixmap)

        offset = 0
        if self.hasAutoMasks:
            offset = self.drawIndicator(painter, QColor(0, 255, 0), offset)
        if self.hasManualMasks:
            offset = self.drawIndicator(painter, QColor(0, 255, 255), offset)
        if self.isExcluded:
            offset = self.drawIndicator(painter, QColor(255, 0, 0), offset)


class FileButton(QPushButton):
    def __init__(self, signals: QObject, file: File):
        super().__init__()
        self.file = file
        self.signals = signals
        self.renderedThumbnail = False

        self.iconLabel = IconLabel()
        self.objectName = file.basename
        placeHolder = QPixmap(128, 128)
        placeHolder.fill(QColor(0, 0, 0, 0))

        textLabel = QLabel(file.basename)
        textLabel.setAlignment(Qt.AlignCenter)
        metrics = QFontMetrics(textLabel.font())
        clippedText = metrics.elidedText(file.basename, Qt.TextElideMode.ElideMiddle, 128)
        textLabel.setText(clippedText)

        layout = QVBoxLayout(self)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.setFixedSize(QSize(140, 140))
        layout.addWidget(self.iconLabel)
        layout.addWidget(textLabel)

    def focusInEvent(self, arg__1):
        self.signals.showFile.emit(self.file)
        self.setStyleSheet("background-color: dimgray;")
        return super().focusInEvent(arg__1)

    def focusOutEvent(self, arg__1):
        self.setStyleSheet("")
        return super().focusOutEvent(arg__1)

    def mousePressEvent(self, e):
        if e.button() == Qt.RightButton:
            menu = QMenu(self)
            actionRemove = menu.addAction("Remove from Project")
            actionRemove.triggered.connect(self.action_remove)
            if isinstance(self.file, InputFile):
                actionExclude = menu.addAction("Exclude from Stack")
                actionExclude.setCheckable(True)
                actionExclude.setChecked(self.file.excludeFromStack)
                actionExclude.triggered.connect(self.action_exclude)

            menu.exec_(e.globalPos())
        else:
            return super().mousePressEvent(e)

    def maybeDeferredRenderThumbnail(self, forceFocus=False):

        if self.isVisible() and not self.renderedThumbnail and not self.iconLabel.visibleRegion().isEmpty():
            self.iconLabel.setFile(self.file)
            self.renderedThumbnail = True

            # focus first instance in list once it is available
            if forceFocus:
                self.click()
                self.setFocus()

            return True
        return False

    def updateIndicators(self):
        self.iconLabel.updateIndicators()

    def showEvent(self, event):
        self.maybeDeferredRenderThumbnail()
        return super().showEvent(event)

    def action_remove(self):
        self.signals.removeFile.emit(self.file, self)

    def action_exclude(self):
        self.signals.excludeFile.emit(self.file, self)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
