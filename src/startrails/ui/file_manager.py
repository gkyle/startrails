"""Metadata-only file views. No image decoding or widget allocation per row."""
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal, QSignalBlocker
from PySide6.QtWidgets import QFrame, QHeaderView, QMenu

from startrails.lib.file import File, InputFile
from .ui_file_manager import Ui_FileSection


class FileModel(QAbstractTableModel):
    summaryChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.files = []
        self._rows = {}
        self._states = {}
        self.mask_files = set()
        self.manual_files = set()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.files)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else 2

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal:
            if role == Qt.DisplayRole:
                return ("Filename", "Annotations / status")[section]
            if role == Qt.ToolTipRole and section == 1:
                return "A: automatic masks · M: manual masks · D: manually deleted masks"

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.files):
            return None
        file = self.files[index.row()]
        if role == Qt.UserRole:
            return file
        if role in (Qt.ToolTipRole, Qt.AccessibleTextRole):
            if isinstance(file, InputFile):
                auto, manual, deleted, excluded = self._states[file]
                return (f"{file.path}\nAutomatic masks: {auto}\nManual masks: {manual}\n"
                        f"Manually deleted masks: {deleted}\n"
                        f"{'Excluded from' if excluded else 'Included in'} stack")
            return f"{file.path}\n{file.operation}"
        if role == Qt.DisplayRole:
            if index.column() == 0:
                return file.basename
            if not isinstance(file, InputFile):
                return file.operation
            auto, manual, deleted, excluded = self._states[file]
            parts = [f"{label}:{count}" for label, count in (("A", auto), ("M", manual), ("D", deleted)) if count]
            if excluded:
                parts.append("Excluded")
            return " · ".join(parts) or "—"

    def _record(self, file):
        if not isinstance(file, InputFile):
            return
        auto, manual, deleted = len(file.streaksMasks), len(file.streaksManualMasks), len(file.streaksManualDeletedMasks)
        self._states[file] = auto, manual, deleted, file.excludeFromStack
        (self.mask_files.add if auto or manual else self.mask_files.discard)(file)
        (self.manual_files.add if manual or deleted else self.manual_files.discard)(file)

    def set_files(self, files):
        self.beginResetModel()
        self.files = list(files)
        self._rows = {file: row for row, file in enumerate(self.files)}
        self._states.clear()
        self.mask_files.clear()
        self.manual_files.clear()
        for file in self.files:
            self._record(file)
        self.endResetModel()
        self.summaryChanged.emit()

    def sync_files(self, files):
        """Append published outputs without resetting selection or existing rows."""
        files = list(files)
        count = len(self.files)
        if files[:count] != self.files:
            self.set_files(files)
        elif len(files) > count:
            self.beginInsertRows(QModelIndex(), count, len(files) - 1)
            for row in range(count, len(files)):
                file = files[row]
                self.files.append(file)
                self._rows[file] = row
                self._record(file)
            self.endInsertRows()
            self.summaryChanged.emit()

    def update_file(self, file):
        row = self._rows.get(file)
        if row is None:
            return
        self._record(file)
        self.dataChanged.emit(self.index(row, 0), self.index(row, 1),
                              [Qt.DisplayRole, Qt.ToolTipRole, Qt.AccessibleTextRole])
        self.summaryChanged.emit()

    def remove_file(self, file):
        row = self._rows.get(file)
        if row is None:
            return
        self.beginRemoveRows(QModelIndex(), row, row)
        self.files.pop(row)
        self._rows = {item: i for i, item in enumerate(self.files)}
        self._states.pop(file, None)
        self.mask_files.discard(file)
        self.manual_files.discard(file)
        self.endRemoveRows()
        self.summaryChanged.emit()

    def index_for_file(self, file):
        row = self._rows.get(file)
        return self.index(row, 0) if row is not None else QModelIndex()


class FileSection(QFrame):
    showFile = Signal(File)
    removeFile = Signal(File)
    excludeFile = Signal(File)
    addRequested = Signal()

    def __init__(self, title, inputs=False, parent=None):
        super().__init__(parent)
        self.ui = Ui_FileSection()
        self.ui.setupUi(self)
        self.ui.toggle.setText(title)
        self.ui.files.setAccessibleName(title)
        self.ui.add.setVisible(inputs)
        self.ui.exclude.setVisible(inputs)
        self.model = FileModel(self)
        self.ui.files.setModel(self.model)
        self.ui.files.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ui.files.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.ui.files.header().resizeSection(1, 160)
        self.ui.toggle.toggled.connect(self.setExpanded)
        self.ui.add.clicked.connect(self.addRequested.emit)
        self.ui.files.selectionModel().currentChanged.connect(self._selection_changed)
        self.ui.files.customContextMenuRequested.connect(self._context_menu)
        self.ui.remove.clicked.connect(self._remove)
        self.ui.exclude.clicked.connect(self._exclude)
        self.model.summaryChanged.connect(self._refresh)
        self.setExpanded(inputs)
        self._refresh()

    def setExpanded(self, expanded):
        self.ui.toggle.setChecked(expanded)
        self.ui.toggle.setArrowType(Qt.DownArrow if expanded else Qt.RightArrow)
        self.ui.body.setVisible(expanded)

    def current_file(self):
        return self.ui.files.currentIndex().data(Qt.UserRole)

    def set_files(self, files):
        current = self.current_file()
        with QSignalBlocker(self.ui.files.selectionModel()):
            self.model.set_files(files)
            index = self.model.index_for_file(current)
            self.ui.files.setCurrentIndex(index)
        self._refresh()

    def focus_file(self, file):
        index = self.model.index_for_file(file)
        with QSignalBlocker(self.ui.files.selectionModel()):
            self.ui.files.setCurrentIndex(index)
            if not index.isValid():
                self.ui.files.clearSelection()
        if index.isValid():
            self.setExpanded(True)
            self.ui.files.scrollTo(index)
        self._refresh()

    def _selection_changed(self, current, previous):
        self._refresh()
        file = current.data(Qt.UserRole)
        if file is not None:
            self.showFile.emit(file)

    def _refresh(self):
        count = self.model.rowCount()
        self.ui.count.setText(str(count))
        self.ui.empty.setVisible(count == 0)
        self.ui.files.setVisible(count != 0)
        current = self.current_file()
        self.ui.remove.setEnabled(current is not None)
        self.ui.exclude.setEnabled(isinstance(current, InputFile))
        self.ui.exclude.setChecked(isinstance(current, InputFile) and current.excludeFromStack)

    def _remove(self):
        file = self.current_file()
        if file is not None:
            self.removeFile.emit(file)

    def _exclude(self):
        file = self.current_file()
        if isinstance(file, InputFile):
            self.excludeFile.emit(file)

    def _context_menu(self, pos):
        index = self.ui.files.indexAt(pos)
        if index.isValid():
            self.ui.files.setCurrentIndex(index)
        file = self.current_file()
        if file is None:
            return
        menu = QMenu(self)
        menu.addAction("Remove from Project", self._remove)
        if isinstance(file, InputFile):
            exclude = menu.addAction("Exclude from Stack", self._exclude)
            exclude.setCheckable(True)
            exclude.setChecked(file.excludeFromStack)
        menu.exec(self.ui.files.viewport().mapToGlobal(pos))
