"""Metadata-only file views. No image decoding or widget allocation per row."""
from PySide6.QtCore import QAbstractTableModel, QEvent, QModelIndex, QRect, QSize, Qt, Signal, QSignalBlocker
from PySide6.QtGui import QBrush, QFont, QIcon, QPainter, QPen
from PySide6.QtWidgets import QFrame, QHeaderView, QMenu, QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from types import SimpleNamespace
from startrails.lib.file import File, InputFile
from . import resources_rc  # Register SVG icons when this module is used directly.
from .ui_file_manager import Ui_FileSection
from .theme import is_dark, themed_color


class AnnotationBadgeDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.doc_icon = QIcon(":/startrails/ui/document.svg")
        self.dark_doc_icon = QIcon(":/startrails/ui/document_dark.svg")

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        return QSize(size.width(), max(24, size.height()))

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex):
        def color(value, role="foreground"):
            return themed_color(value, option.palette, role)

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        is_selected = bool(option.state & QStyle.State_Selected)
        is_hovered = bool(option.state & QStyle.State_MouseOver)

        if is_selected:
            painter.fillRect(option.rect, color("#eff6ff", "background"))
        elif is_hovered:
            painter.fillRect(option.rect, color("#f8fafc", "background"))

        file = index.data(Qt.UserRole)
        col = index.column()

        if col == 0:
            icon_rect = QRect(option.rect.left() + 4, option.rect.top() + (option.rect.height() - 14) // 2, 14, 14)
            icon = self.dark_doc_icon if is_dark(option.palette) else self.doc_icon
            icon.paint(painter, icon_rect)

            text_rect = QRect(option.rect.left() + 24, option.rect.top(), option.rect.width() - 28, option.rect.height())
            text = index.data(Qt.DisplayRole) or ""
            font = QFont(option.font)
            font.setPointSize(9)
            if is_selected:
                font.setWeight(QFont.DemiBold)
                painter.setPen(color("#1d4ed8"))
            else:
                painter.setPen(color("#0f172a"))
            painter.setFont(font)
            metrics = painter.fontMetrics()
            elided = metrics.elidedText(text, Qt.ElideMiddle, text_rect.width())
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        elif col == 1:
            if isinstance(file, InputFile):
                model = index.model()
                states = getattr(model, "_states", {})
                auto, manual, deleted, excluded = states.get(file, (0, 0, 0, False))

                badges = []
                if auto:
                    badges.append((f"A:{auto}", color("#dcfce7", "background"), color("#15803d"), color("#bbf7d0", "border")))
                if manual:
                    badges.append((f"M:{manual}", color("#e0f2fe", "background"), color("#0369a1"), color("#bae6fd", "border")))
                if deleted:
                    badges.append((f"D:{deleted}", color("#fef3c7", "background"), color("#b45309"), color("#fde68a", "border")))
                if excluded:
                    badges.append(("Excluded", color("#fee2e2", "background"), color("#b91c1c"), color("#fecaca", "border")))

                if badges:
                    x = option.rect.left() + 4
                    badge_font = QFont(option.font)
                    badge_font.setPointSize(8)
                    badge_font.setWeight(QFont.DemiBold)
                    painter.setFont(badge_font)
                    fm = painter.fontMetrics()
                    badge_h = 16
                    y = option.rect.top() + (option.rect.height() - badge_h) // 2

                    for text, bg_col, text_col, border_col in badges:
                        text_w = fm.horizontalAdvance(text)
                        badge_w = max(18, text_w + 10)
                        if x + badge_w > option.rect.right() - 2:
                            break
                        pill_rect = QRect(x, y, badge_w, badge_h)
                        painter.setPen(QPen(border_col, 1))
                        painter.setBrush(QBrush(bg_col))
                        painter.drawRoundedRect(pill_rect, 4, 4)

                        painter.setPen(text_col)
                        painter.drawText(pill_rect, Qt.AlignCenter, text)
                        x += badge_w + 4
                else:
                    painter.setPen(color("#64748b"))
                    font = QFont(option.font)
                    font.setPointSize(9)
                    painter.setFont(font)
                    painter.drawText(option.rect, Qt.AlignVCenter | Qt.AlignLeft, "—")
            else:
                op_text = str(index.data(Qt.DisplayRole) or "")
                badge_font = QFont(option.font)
                badge_font.setPointSize(8)
                badge_font.setWeight(QFont.DemiBold)
                painter.setFont(badge_font)
                fm = painter.fontMetrics()
                badge_h = 16
                y = option.rect.top() + (option.rect.height() - badge_h) // 2
                badge_w = fm.horizontalAdvance(op_text) + 12
                pill_rect = QRect(option.rect.left() + 4, y, badge_w, badge_h)
                if op_text == "Stacked":
                    bg_col, text_col, border_col = color("#eff6ff", "background"), color("#1d4ed8"), color("#bfdbfe", "border")
                elif "FillGaps" in op_text:
                    bg_col, text_col, border_col = color("#f3e8ff", "background"), color("#6b21a8"), color("#e9d5ff", "border")
                else:
                    bg_col, text_col, border_col = color("#f1f5f9", "background"), color("#475569"), color("#e2e8f0", "border")
                painter.setPen(QPen(border_col, 1))
                painter.setBrush(QBrush(bg_col))
                painter.drawRoundedRect(pill_rect, 4, 4)
                painter.setPen(text_col)
                painter.drawText(pill_rect, Qt.AlignCenter, op_text)

        # The custom painter bypasses Qt's default focus primitive. Keep the
        # current keyboard cell distinguishable from the persistent selection.
        if option.state & QStyle.State_HasFocus:
            painter.setBrush(Qt.NoBrush)
            painter.setPen(QPen(color("#0f172a"), 2))
            painter.drawRect(option.rect.adjusted(1, 1, -1, -1))
        painter.restore()


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

    def refresh_annotations(self):
        """Reconcile completion state for files omitted from sampled previews."""
        for row, file in enumerate(self.files):
            previous = self._states.get(file)
            self._record(file)
            if previous != self._states.get(file):
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

    def __init__(self, title, inputs=False, parent=None, ui=None, prefix=None):
        super().__init__(parent)
        self._inputs = inputs
        self.frame = getattr(ui, f"{prefix}Section") if ui and prefix else self
        if ui and prefix:
            self.ui = SimpleNamespace(
                headerWidget=getattr(ui, f"{prefix}Header"),
                chevron=getattr(ui, f"{prefix}Chevron"),
                icon=getattr(ui, f"{prefix}Icon"),
                toggle=getattr(ui, f"{prefix}Toggle"),
                count=getattr(ui, f"{prefix}Count"),
                add=getattr(ui, f"{prefix}Add"),
                body=getattr(ui, f"{prefix}Body"),
                files=getattr(ui, f"{prefix}Tree"),
                empty=getattr(ui, f"{prefix}Empty"),
                legend=getattr(ui, f"{prefix}Legend", None),
            )
        else:
            self.ui = Ui_FileSection()
            self.ui.setupUi(self)
        self.ui.toggle.setText(title)
        self.ui.files.setAccessibleName(title)
        self.ui.add.setAccessibleName("Add input files")
        self.ui.add.setVisible(inputs)
        if getattr(self.ui, "legend", None) is not None:
            self.ui.legend.setVisible(inputs)

        if inputs:
            self.ui.icon.setPixmap(QIcon(":/startrails/ui/star.svg").pixmap(16, 16))
        else:
            self.ui.icon.setPixmap(QIcon(":/startrails/ui/document_output.svg").pixmap(16, 16))

        self.model = FileModel(self)
        self.ui.files.setModel(self.model)
        self.delegate = AnnotationBadgeDelegate(self.ui.files)
        self.ui.files.setItemDelegate(self.delegate)
        self.ui.files.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.ui.files.header().setSectionResizeMode(1, QHeaderView.Interactive)
        self.ui.files.header().resizeSection(1, 130)
        self.ui.toggle.toggled.connect(self.setExpanded)
        self.ui.headerWidget.mousePressEvent = self._on_header_clicked
        self.ui.add.clicked.connect(self.addRequested.emit)
        self.ui.files.selectionModel().currentChanged.connect(self._selection_changed)
        self.ui.files.customContextMenuRequested.connect(self._context_menu)
        self.ui.files.installEventFilter(self)
        self.model.summaryChanged.connect(self._refresh)
        self.setExpanded(inputs)
        self._refresh()

    def eventFilter(self, watched, event):
        if watched is self.ui.files and event.type() == QEvent.KeyPress:
            if (event.key() == Qt.Key_Menu or
                    event.key() == Qt.Key_F10 and event.modifiers() & Qt.ShiftModifier):
                index = self.ui.files.currentIndex()
                if index.isValid():
                    self._context_menu(self.ui.files.visualRect(index).center())
                return True
            if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
                self._remove()
                return True
        return super().eventFilter(watched, event)

    def _on_header_clicked(self, event):
        if event.button() == Qt.LeftButton:
            if self.ui.add.isVisible():
                add_pos = self.ui.add.mapFromGlobal(event.globalPosition().toPoint())
                if self.ui.add.rect().contains(add_pos):
                    return
            self.ui.toggle.toggle()
            event.accept()
            return
        super(QWidget, self.ui.headerWidget).mousePressEvent(event)

    def setExpanded(self, expanded):
        with QSignalBlocker(self.ui.toggle):
            self.ui.toggle.setChecked(expanded)
        self.ui.chevron.setText("▼" if expanded else "▶")
        self.ui.body.setVisible(expanded)
        target = self.frame if getattr(self, "frame", None) is not None else self
        if not expanded:
            target.setFixedHeight(36)
        else:
            target.setMaximumHeight(16777215)
            target.setMinimumHeight(0)
            self._refresh()
            target.adjustSize()
        target.updateGeometry()

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
        try:
            index = self.model.index_for_file(file)
            with QSignalBlocker(self.ui.files.selectionModel()):
                self.ui.files.setCurrentIndex(index)
                if not index.isValid():
                    self.ui.files.clearSelection()
            if index.isValid():
                self.setExpanded(True)
                self.ui.files.scrollTo(index)
            self._refresh()
        except RuntimeError:
            pass

    def _selection_changed(self, current, previous):
        self._refresh()
        file = current.data(Qt.UserRole)
        if file is not None:
            self.showFile.emit(file)

    def _refresh(self):
        count = self.model.rowCount()
        self.ui.count.setText(str(count))
        has_files = count > 0
        self.ui.empty.setVisible(not has_files)
        self.ui.files.setVisible(has_files)
        if has_files:
            hh = self.ui.files.header().height() or 26
            ideal_h = max(54, hh + min(count, 5) * 24 + 4)
            self.ui.files.setFixedHeight(ideal_h)

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
        if not index.isValid():
            return
        self.ui.files.setCurrentIndex(index)
        file = self.current_file()
        if file is None:
            return
        menu = QMenu(self.frame if getattr(self, "frame", None) is not None else self)
        if isinstance(file, InputFile):
            exclude = menu.addAction("Exclude from Stack", self._exclude)
            exclude.setCheckable(True)
            exclude.setChecked(file.excludeFromStack)
            menu.addSeparator()
        menu.addAction("Remove from Project", self._remove)
        menu.exec(self.ui.files.viewport().mapToGlobal(pos))
