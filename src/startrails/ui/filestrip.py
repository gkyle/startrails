from functools import partial
import time
import warnings
from typing import Dict, List
from PySide6.QtWidgets import QMenu, QPushButton, QLabel, QVBoxLayout, QFrame, QScrollArea, QSizePolicy, QApplication, QMessageBox
from PySide6.QtGui import QPixmap, QColor, QIcon, QPaintEvent, QPainter, QPalette, QFontMetrics, QFont
from PySide6.QtCore import QObject, Qt, QSize, QPoint, Signal, QTimer, QRunnable, QThreadPool, Slot
from PIL import Image
from PIL.ImageQt import ImageQt

from startrails.lib.file import File, InputFile
from startrails.ui.signals import emitLater, getSignals

FILESTRIP_CONTAINER_HEIGHT = 154
FILESTRIP_SCROLL_HEIGHT = 125
FILE_BUTTON_SIZE = 100
FILE_IMAGE_SIZE = 88


class ThumbnailLoader(QRunnable):
    def __init__(self, file_path: str, signal: Signal, size: int):
        super().__init__()
        self.file_path = file_path
        self.signal = signal
        self.size = size
        
    def run(self):
        try:
            image = Image.open(self.file_path)
            image.thumbnail((self.size, self.size))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            self.signal.emit(image)
        except Exception as e:
            print(f"[ERROR] Failed to load thumbnail for {self.file_path}: {e}")
            pass


class FileStrip:

    def __init__(self, frame: QFrame, frameContainer: QFrame, fileList: List[File], redrawSignal: Signal, maxVisibleButtons=-1):
        self.buttons: Dict[File, FileButton] = {}
        self.frame = frame
        self.frameContainer = frameContainer
        self.signals = getSignals()
        self.fileList = fileList
        self.maxVisibleButtons = maxVisibleButtons

        # Debounce timer for scroll events
        self.scrollDebounceTimer = QTimer()
        self.scrollDebounceTimer.setSingleShot(True)
        self.scrollDebounceTimer.timeout.connect(lambda: self.scheduleThumbnailLoading())

        self.scroll = self.frameContainer.findChildren(QScrollArea)[0]
        self.scroll.horizontalScrollBar().valueChanged.connect(partial(self.slotScrollbarChanged, self.frame))
        self.signals.loadThumbnailsAsync.connect(self.loadThumbnailsAsync)

        self.frameContainer.setMinimumSize(QSize(FILE_BUTTON_SIZE+8, FILESTRIP_CONTAINER_HEIGHT))
        self.frameContainer.setMaximumSize(QSize(16777215, FILESTRIP_CONTAINER_HEIGHT))
        self.scroll.setMinimumSize(QSize(FILE_BUTTON_SIZE+8, FILESTRIP_SCROLL_HEIGHT))
        self.scroll.setMaximumSize(QSize(16777215, FILESTRIP_SCROLL_HEIGHT))
        self.fileCountLabel = self.frameContainer.findChildren(QLabel)[1]

        self.signals.updateFileButton.connect(self.update)
        self.signals.focusFile.connect(self.focusFile)
        self.signals.addFileButton.connect(self.slotAddFileButton)
        redrawSignal.connect(self.drawFileList)

        self.drawFileList()
        if len(self.fileList) > 0:
            self.scheduleThumbnailLoading()

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
        if len(self.fileList) > 0:
            self.scheduleThumbnailLoading()

    def drawFileList(self, focusOnFile: File = None):
        for child in self.frame.findChildren(QLabel):
            child.setParent(None)
            child.deleteLater()
        for child in self.frame.findChildren(QPushButton):
            child.setParent(None)
            child.deleteLater()

        self.fileCountLabel.setText(f"({len(self.fileList)})")

        for idx, file in enumerate(self.fileList):
            doFocus = False
            if focusOnFile is not None:
                if file == focusOnFile:
                    doFocus = True
            else:
                if idx == 0:
                    doFocus = True
            doPriority = idx < 10 if self.maxVisibleButtons < 0 else idx < self.maxVisibleButtons
            if idx % 5 == 0:  # yield periodically to enable the frame to render with full width buttons
                QApplication.processEvents()
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
        self.frameContainer.setMinimumSize(QSize(c*(FILE_BUTTON_SIZE+8), FILESTRIP_CONTAINER_HEIGHT))

    def focusFile(self, file: File):
        if file in self.buttons:
            self.buttons[file].setFocus()
            self.scroll.ensureWidgetVisible(self.buttons[file])
            QTimer.singleShot(0, lambda: self.loadThumbnailsAsync(self.frame))

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

    def slotScrollbarChanged(self, frame, _=None):
        if frame == self.frame:
            # Only trigger thumbnail loading after scrolling has settled for 100ms
            self.scrollDebounceTimer.start(100)

    def loadThumbnailsAsync(self, frame):
        # Load thumbnails for visible buttons
        if frame == self.frame:
            all_buttons = frame.findChildren(FileButton)
            visible_buttons = [child for child in all_buttons if self._isButtonVisible(child)]

            # Stagger thumbnail loading to allow UI updates between each load
            for idx, button in enumerate(visible_buttons):
                delay_ms = idx * 10  # 10ms delay between each thumbnail
                QTimer.singleShot(delay_ms, lambda b=button: self._loadButtonThumbnail(b))

    def _loadButtonThumbnail(self, button):
        button.maybeDeferredRenderThumbnail()

    def _isButtonVisible(self, button):
        if not button.isVisible():
            return False
        
        viewport_rect = self.scroll.viewport().rect()
        button_pos = button.pos()
        button_rect = button.geometry()
        scroll_x = self.scroll.horizontalScrollBar().value()
        button_x_in_viewport = button_pos.x() - scroll_x
        
        # Check if button intersects with viewport
        button_left = button_x_in_viewport
        button_right = button_x_in_viewport + button_rect.width()
        viewport_left = 0
        viewport_right = viewport_rect.width()
        
        is_in_viewport = button_right > viewport_left and button_left < viewport_right
        
        return is_in_viewport

    def scheduleThumbnailLoading(self):
        QTimer.singleShot(100, lambda: self.signals.loadThumbnailsAsync.emit(self.frame))


class IconLabel(QLabel):
    thumbnailReady = Signal(object)
    
    def __init__(self, file: File = None):
        super().__init__()
        self.file = file
        self.hasAutoMasks = False
        self.hasManualMasks = False
        self.isExcluded = False
        self.thumbnailLoaded = False
        self.threadPool = QThreadPool.globalInstance()
        self.setFixedSize(QSize(FILE_IMAGE_SIZE, FILE_IMAGE_SIZE))

        # Always start with placeholder and lazy-load the thumbnail.
        self.pixmap = QPixmap(FILE_IMAGE_SIZE, FILE_IMAGE_SIZE)
        self.pixmap.fill(QColor("#444444"))
        self.setAlignment(Qt.AlignCenter)
        self.thumbnailReady.connect(self._setThumbnailFromPIL)

    def setFile(self, file: File) -> None:
        self.file = file
        self.loadThumbnail()
        self.updateIndicators()

    def loadThumbnail(self) -> None:
        if self.file is None or self.thumbnailLoaded:
            return

        loader = ThumbnailLoader(self.file.path, self.thumbnailReady, FILE_IMAGE_SIZE)
        self.threadPool.start(loader)
    
    def _setThumbnailFromPIL(self, pil_image: Image.Image) -> None:
        try:
            if not self.thumbnailLoaded:
                qt_image = ImageQt(pil_image)
                self.pixmap = QPixmap.fromImage(qt_image)
                self.thumbnailLoaded = True
                self.update()
        except RuntimeError as e:
            pass
        except Exception as e:
            print(f"[ERROR] Failed to convert PIL image to QPixmap: {e}")
            pass

    def updateIndicators(self):
        if isinstance(self.file, InputFile):
            self.hasAutoMasks = len(self.file.streaksMasks) > 0
            self.hasManualMasks = len(self.file.streaksManualMasks) > 0
            self.isExcluded = self.file.excludeFromStack

        self.update()

    def drawIndicator(self, painter: QPainter, color: QColor, offset: int):
        painter.setBrush(color)
        painter.setPen(color)
        painter.drawEllipse(FILE_IMAGE_SIZE - 15-offset, 5, 8, 8)
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

        self.iconLabel = IconLabel()
        self.objectName = file.basename
        placeHolder = QPixmap(FILE_IMAGE_SIZE, FILE_IMAGE_SIZE)
        placeHolder.fill(QColor(0, 0, 0, 0))

        textLabel = QLabel(file.basename)
        textLabel.setAlignment(Qt.AlignCenter)
        textLabel.setFont(QFont("Arial", 9))
        metrics = QFontMetrics(textLabel.font())
        clippedText = metrics.elidedText(file.basename, Qt.TextElideMode.ElideMiddle, FILE_IMAGE_SIZE)
        textLabel.setText(clippedText)

        layout = QVBoxLayout(self)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.setFixedSize(QSize(FILE_BUTTON_SIZE, FILE_BUTTON_SIZE))
        layout.setContentsMargins(4, 9, 4, 9)
        layout.setAlignment(Qt.AlignCenter)
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
        if self.isVisible():
            # Set file association but defer thumbnail loading
            self.iconLabel.file = self.file
            self.iconLabel.updateIndicators()

            if not self.iconLabel.thumbnailLoaded:
                self.iconLabel.loadThumbnail()

            # focus first instance in list once it is available
            if forceFocus:
                self.click()
                self.setFocus()

            return True
        return False

    def updateIndicators(self):
        self.iconLabel.updateIndicators()

    def action_remove(self):
        self.signals.removeFile.emit(self.file, self)

    def action_exclude(self):
        self.signals.excludeFile.emit(self.file, self)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
