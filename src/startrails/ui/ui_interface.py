# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'interface.ui'
##
## Created by: Qt User Interface Compiler version 6.8.2
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide6.QtCore import (QCoreApplication, QDate, QDateTime, QLocale,
    QMetaObject, QObject, QPoint, QRect,
    QSize, QTime, QUrl, Qt)
from PySide6.QtGui import (QBrush, QColor, QConicalGradient, QCursor,
    QFont, QFontDatabase, QGradient, QIcon,
    QImage, QKeySequence, QLinearGradient, QPainter,
    QPalette, QPixmap, QRadialGradient, QTransform)
from PySide6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox,
    QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
    QHeaderView, QLabel, QLayout, QMainWindow,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QSpacerItem, QSpinBox, QSplitter, QToolButton,
    QTreeView, QVBoxLayout, QWidget)
from . import resources_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1600, 1200)
        MainWindow.setMinimumSize(QSize(300, 0))
        MainWindow.setStyleSheet(u"QMainWindow {\n"
"    background-color: #f8fafc;\n"
"}")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.centralwidget.setStyleSheet(u"QWidget#centralwidget {\n"
"    background-color: #f8fafc;\n"
"}")
        self.horizontalLayout_5 = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_5.setSpacing(0)
        self.horizontalLayout_5.setObjectName(u"horizontalLayout_5")
        self.horizontalLayout_5.setSizeConstraint(QLayout.SetNoConstraint)
        self.horizontalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.vframe = QFrame(self.centralwidget)
        self.vframe.setObjectName(u"vframe")
        self.vframe.setFrameShape(QFrame.NoFrame)
        self.vframe.setFrameShadow(QFrame.Raised)
        self.vframe.setLineWidth(0)
        self.verticalLayout_5 = QVBoxLayout(self.vframe)
        self.verticalLayout_5.setSpacing(2)
        self.verticalLayout_5.setObjectName(u"verticalLayout_5")
        self.verticalLayout_5.setSizeConstraint(QLayout.SetNoConstraint)
        self.verticalLayout_5.setContentsMargins(0, 0, 0, 0)
        self.toolbar = QFrame(self.vframe)
        self.toolbar.setObjectName(u"toolbar")
        sizePolicy.setHeightForWidth(self.toolbar.sizePolicy().hasHeightForWidth())
        self.toolbar.setSizePolicy(sizePolicy)
        self.toolbar.setMaximumSize(QSize(16777215, 50))
        self.toolbar.setStyleSheet(u"QFrame#toolbar {\n"
"    background-color: #ffffff;\n"
"    border-bottom: 1px solid #e2e8f0;\n"
"}")
        self.toolbar.setFrameShape(QFrame.NoFrame)
        self.toolbar.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.toolbar)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setHorizontalSpacing(0)
        self.gridLayout.setContentsMargins(0, 4, 6, 4)
        self.frame = QFrame(self.toolbar)
        self.frame.setObjectName(u"frame")
        sizePolicy.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy)
        self.frame.setMinimumSize(QSize(300, 0))
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_9 = QHBoxLayout(self.frame)
        self.horizontalLayout_9.setObjectName(u"horizontalLayout_9")
        self.label_4 = QLabel(self.frame)
        self.label_4.setObjectName(u"label_4")
        font = QFont()
        font.setBold(True)
        self.label_4.setFont(font)
        self.label_4.setStyleSheet(u"QLabel#label_4 {\n"
"    font-size: 15px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}")

        self.horizontalLayout_9.addWidget(self.label_4)


        self.gridLayout.addWidget(self.frame, 0, 0, 1, 1)

        self.frame_3 = QFrame(self.toolbar)
        self.frame_3.setObjectName(u"frame_3")
        sizePolicy.setHeightForWidth(self.frame_3.sizePolicy().hasHeightForWidth())
        self.frame_3.setSizePolicy(sizePolicy)
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_10 = QHBoxLayout(self.frame_3)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.label_imageName = QLabel(self.frame_3)
        self.label_imageName.setObjectName(u"label_imageName")
        self.label_imageName.setFont(font)
        self.label_imageName.setStyleSheet(u"QLabel#label_imageName {\n"
"    font-size: 12px;\n"
"    font-weight: 600;\n"
"    color: #334155;\n"
"}")

        self.horizontalLayout_10.addWidget(self.label_imageName)


        self.gridLayout.addWidget(self.frame_3, 0, 1, 1, 1)

        self.frame_4 = QFrame(self.toolbar)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setMinimumSize(QSize(244, 0))
        self.frame_4.setMaximumSize(QSize(244, 16777215))
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_7 = QHBoxLayout(self.frame_4)
        self.horizontalLayout_7.setSpacing(6)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(9, 0, 0, 0)
        self.frame_gpu = QFrame(self.frame_4)
        self.frame_gpu.setObjectName(u"frame_gpu")
        self.frame_gpu.setFrameShape(QFrame.NoFrame)
        self.frame_gpu.setFrameShadow(QFrame.Raised)
        self.verticalLayout_15 = QVBoxLayout(self.frame_gpu)
        self.verticalLayout_15.setObjectName(u"verticalLayout_15")
        self.verticalLayout_15.setContentsMargins(0, 0, 0, 0)
        self.frame_gpu_label = QFrame(self.frame_gpu)
        self.frame_gpu_label.setObjectName(u"frame_gpu_label")
        self.frame_gpu_label.setMinimumSize(QSize(0, 0))
        self.frame_gpu_label.setFrameShape(QFrame.StyledPanel)
        self.frame_gpu_label.setFrameShadow(QFrame.Raised)
        self.verticalLayout_7 = QVBoxLayout(self.frame_gpu_label)
        self.verticalLayout_7.setObjectName(u"verticalLayout_7")
        self.verticalLayout_7.setContentsMargins(-1, 9, -1, 9)
        self.label_gpu = QLabel(self.frame_gpu_label)
        self.label_gpu.setObjectName(u"label_gpu")
        self.label_gpu.setStyleSheet(u"QLabel#label_gpu {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #64748b;\n"
"}")

        self.verticalLayout_7.addWidget(self.label_gpu)


        self.verticalLayout_15.addWidget(self.frame_gpu_label)

        self.frame_gpu_util = QFrame(self.frame_gpu)
        self.frame_gpu_util.setObjectName(u"frame_gpu_util")
        self.frame_gpu_util.setFrameShape(QFrame.NoFrame)
        self.frame_gpu_util.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_19 = QHBoxLayout(self.frame_gpu_util)
        self.horizontalLayout_19.setObjectName(u"horizontalLayout_19")
        self.horizontalLayout_19.setContentsMargins(0, 0, 0, 0)
        self.progressBar_gpu_util = QProgressBar(self.frame_gpu_util)
        self.progressBar_gpu_util.setObjectName(u"progressBar_gpu_util")
        self.progressBar_gpu_util.setMinimumSize(QSize(0, 16))
        font1 = QFont()
        self.progressBar_gpu_util.setFont(font1)
        self.progressBar_gpu_util.setStyleSheet(u"QProgressBar#progressBar_gpu_util {\n"
"    background-color: #f1f5f9;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 3px;\n"
"    font-size: 9px;\n"
"    color: #334155;\n"
"    max-height: 14px;\n"
"    min-height: 14px;\n"
"}\n"
"QProgressBar#progressBar_gpu_util::chunk {\n"
"    background-color: green;\n"
"    border-radius: 2px;\n"
"}")
        self.progressBar_gpu_util.setValue(0)
        self.progressBar_gpu_util.setAlignment(Qt.AlignCenter)
        self.progressBar_gpu_util.setTextVisible(True)
        self.progressBar_gpu_util.setInvertedAppearance(False)
        self.progressBar_gpu_util.setTextDirection(QProgressBar.TopToBottom)

        self.horizontalLayout_19.addWidget(self.progressBar_gpu_util)


        self.verticalLayout_15.addWidget(self.frame_gpu_util)

        self.frame_gpu_mem = QFrame(self.frame_gpu)
        self.frame_gpu_mem.setObjectName(u"frame_gpu_mem")
        self.frame_gpu_mem.setFrameShape(QFrame.NoFrame)
        self.frame_gpu_mem.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_18 = QHBoxLayout(self.frame_gpu_mem)
        self.horizontalLayout_18.setObjectName(u"horizontalLayout_18")
        self.horizontalLayout_18.setContentsMargins(0, 0, 0, 0)
        self.progressBar_gpu_mem = QProgressBar(self.frame_gpu_mem)
        self.progressBar_gpu_mem.setObjectName(u"progressBar_gpu_mem")
        self.progressBar_gpu_mem.setFont(font1)
        self.progressBar_gpu_mem.setStyleSheet(u"QProgressBar#progressBar_gpu_mem {\n"
"    background-color: #f1f5f9;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 3px;\n"
"    font-size: 9px;\n"
"    color: #334155;\n"
"    max-height: 14px;\n"
"    min-height: 14px;\n"
"}\n"
"QProgressBar#progressBar_gpu_mem::chunk {\n"
"    background-color: green;\n"
"    border-radius: 2px;\n"
"}")
        self.progressBar_gpu_mem.setValue(0)
        self.progressBar_gpu_mem.setAlignment(Qt.AlignCenter)
        self.progressBar_gpu_mem.setTextVisible(True)
        self.progressBar_gpu_mem.setInvertedAppearance(False)

        self.horizontalLayout_18.addWidget(self.progressBar_gpu_mem)


        self.verticalLayout_15.addWidget(self.frame_gpu_mem)


        self.horizontalLayout_7.addWidget(self.frame_gpu)


        self.gridLayout.addWidget(self.frame_4, 0, 2, 1, 1, Qt.AlignRight)


        self.verticalLayout_5.addWidget(self.toolbar)

        self.bodySplitter = QSplitter(self.vframe)
        self.bodySplitter.setObjectName(u"bodySplitter")
        self.bodySplitter.setHandleWidth(0)
        self.bodySplitter.setOrientation(Qt.Horizontal)
        self.bodySplitter.setChildrenCollapsible(False)
        self.sidebar = QWidget(self.bodySplitter)
        self.sidebar.setObjectName(u"sidebar")
        self.sidebar.setMinimumSize(QSize(320, 0))
        self.sidebar.setMaximumSize(QSize(320, 16777215))
        self.sidebarLayout = QVBoxLayout(self.sidebar)
        self.sidebarLayout.setSpacing(0)
        self.sidebarLayout.setObjectName(u"sidebarLayout")
        self.sidebarLayout.setContentsMargins(1, 1, 1, 1)
        self.scroll = QScrollArea(self.sidebar)
        self.scroll.setObjectName(u"scroll")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.scroll.sizePolicy().hasHeightForWidth())
        self.scroll.setSizePolicy(sizePolicy1)
        self.scroll.setMinimumSize(QSize(0, 0))
        self.scroll.setMaximumSize(QSize(16777215, 16777215))
        self.scroll.setStyleSheet(u"QScrollArea#scroll {\n"
"    border: none;\n"
"    background: transparent;\n"
"}\n"
"QScrollBar:vertical {\n"
"    border: none;\n"
"    background: #f1f5f9;\n"
"    width: 6px;\n"
"    border-radius: 3px;\n"
"    margin: 2px 0px 2px 0px;\n"
"}\n"
"QScrollBar::handle:vertical {\n"
"    background: #cbd5e1;\n"
"    min-height: 24px;\n"
"    border-radius: 3px;\n"
"}\n"
"QScrollBar::handle:vertical:hover {\n"
"    background: #94a3b8;\n"
"}\n"
"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {\n"
"    height: 0px;\n"
"}\n"
"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {\n"
"    background: none;\n"
"}\n"
"QScrollBar:horizontal {\n"
"    height: 0px;\n"
"}")
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName(u"content")
        self.content.setGeometry(QRect(0, -619, 381, 1765))
        self.content.setMinimumSize(QSize(0, 0))
        self.content.setStyleSheet(u"QWidget#content {\n"
"    background-color: #f8fafc;\n"
"}")
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setSpacing(8)
        self.contentLayout.setObjectName(u"contentLayout")
        self.contentLayout.setContentsMargins(8, 8, 8, 8)
        self.projectTitle = QLabel(self.content)
        self.projectTitle.setObjectName(u"projectTitle")
        self.projectTitle.setStyleSheet(u"QLabel#projectTitle {\n"
"    font-size: 15px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}")

        self.contentLayout.addWidget(self.projectTitle)

        self.projectActions = QHBoxLayout()
        self.projectActions.setSpacing(6)
        self.projectActions.setObjectName(u"projectActions")
        self.newProject = QPushButton(self.content)
        self.newProject.setObjectName(u"newProject")
        self.newProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.newProject.setStyleSheet(u"QPushButton#newProject {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#newProject:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#newProject:pressed {\n"
"    background-color: #e2e8f0;\n"
"}\n"
"QPushButton#newProject:focus:enabled { border-color: #0f172a; }")

        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton(self.content)
        self.openProject.setObjectName(u"openProject")
        self.openProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.openProject.setStyleSheet(u"QPushButton#openProject {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#openProject:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#openProject:pressed {\n"
"    background-color: #e2e8f0;\n"
"}\n"
"QPushButton#openProject:focus:enabled { border-color: #0f172a; }")

        self.projectActions.addWidget(self.openProject)


        self.contentLayout.addLayout(self.projectActions)

        self.inputFilesSection = QFrame(self.content)
        self.inputFilesSection.setObjectName(u"inputFilesSection")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.inputFilesSection.sizePolicy().hasHeightForWidth())
        self.inputFilesSection.setSizePolicy(sizePolicy2)
        self.inputFilesSection.setStyleSheet(u"QFrame#inputFilesSection {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#inputFilesSection:hover {\n"
"    border-color: #cbd5e1;\n"
"}")
        self.inputFilesLayout = QVBoxLayout(self.inputFilesSection)
        self.inputFilesLayout.setSpacing(2)
        self.inputFilesLayout.setObjectName(u"inputFilesLayout")
        self.inputFilesLayout.setContentsMargins(4, 4, 4, 4)
        self.inputFilesHeader = QWidget(self.inputFilesSection)
        self.inputFilesHeader.setObjectName(u"inputFilesHeader")
        sizePolicy3 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy3.setHorizontalStretch(0)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.inputFilesHeader.sizePolicy().hasHeightForWidth())
        self.inputFilesHeader.setSizePolicy(sizePolicy3)
        self.inputFilesHeader.setMaximumSize(QSize(16777215, 32))
        self.inputFilesHeader.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.inputFilesHeaderLayout = QHBoxLayout(self.inputFilesHeader)
        self.inputFilesHeaderLayout.setSpacing(6)
        self.inputFilesHeaderLayout.setObjectName(u"inputFilesHeaderLayout")
        self.inputFilesHeaderLayout.setContentsMargins(6, 4, 6, 4)
        self.inputFilesChevron = QLabel(self.inputFilesHeader)
        self.inputFilesChevron.setObjectName(u"inputFilesChevron")
        self.inputFilesChevron.setStyleSheet(u"QLabel#inputFilesChevron {\n"
"    font-size: 10px;\n"
"    color: #64748b;\n"
"    font-weight: bold;\n"
"}")

        self.inputFilesHeaderLayout.addWidget(self.inputFilesChevron)

        self.inputFilesIcon = QLabel(self.inputFilesHeader)
        self.inputFilesIcon.setObjectName(u"inputFilesIcon")
        self.inputFilesIcon.setMinimumSize(QSize(16, 16))
        self.inputFilesIcon.setMaximumSize(QSize(16, 16))
        self.inputFilesIcon.setAlignment(Qt.AlignCenter)

        self.inputFilesHeaderLayout.addWidget(self.inputFilesIcon)

        self.inputFilesToggle = QToolButton(self.inputFilesHeader)
        self.inputFilesToggle.setObjectName(u"inputFilesToggle")
        self.inputFilesToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.inputFilesToggle.setStyleSheet(u"QToolButton#inputFilesToggle {\n"
"    border: 2px solid transparent;\n"
"    background: transparent;\n"
"    font-weight: bold;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    padding: 0px;\n"
"}\n"
"QToolButton#inputFilesToggle:focus:enabled { border-color: #0f172a; }")
        self.inputFilesToggle.setCheckable(True)
        self.inputFilesToggle.setChecked(True)

        self.inputFilesHeaderLayout.addWidget(self.inputFilesToggle)

        self.inputFilesCount = QLabel(self.inputFilesHeader)
        self.inputFilesCount.setObjectName(u"inputFilesCount")
        sizePolicy4 = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy4.setHorizontalStretch(0)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.inputFilesCount.sizePolicy().hasHeightForWidth())
        self.inputFilesCount.setSizePolicy(sizePolicy4)
        self.inputFilesCount.setMaximumSize(QSize(16777215, 18))
        self.inputFilesCount.setStyleSheet(u"QLabel#inputFilesCount {\n"
"    background-color: #f1f5f9;\n"
"    color: #475569;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 1px 7px;\n"
"    border-radius: 9px;\n"
"    min-width: 14px;\n"
"}")
        self.inputFilesCount.setAlignment(Qt.AlignCenter)

        self.inputFilesHeaderLayout.addWidget(self.inputFilesCount)

        self.inputFilesSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.inputFilesHeaderLayout.addItem(self.inputFilesSpacer)

        self.inputFilesAdd = QPushButton(self.inputFilesHeader)
        self.inputFilesAdd.setObjectName(u"inputFilesAdd")
        self.inputFilesAdd.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.inputFilesAdd.setStyleSheet(u"QPushButton#inputFilesAdd {\n"
"    border: 2px solid transparent;\n"
"    border-radius: 3px;\n"
"    font-weight: bold;\n"
"    font-size: 13px;\n"
"    color: #475569;\n"
"    background: transparent;\n"
"    min-width: 20px;\n"
"    max-width: 20px;\n"
"    min-height: 20px;\n"
"    max-height: 20px;\n"
"}\n"
"QPushButton#inputFilesAdd:hover {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#inputFilesAdd:focus:enabled { border-color: #0f172a; }")

        self.inputFilesHeaderLayout.addWidget(self.inputFilesAdd)


        self.inputFilesLayout.addWidget(self.inputFilesHeader)

        self.inputFilesBody = QWidget(self.inputFilesSection)
        self.inputFilesBody.setObjectName(u"inputFilesBody")
        sizePolicy2.setHeightForWidth(self.inputFilesBody.sizePolicy().hasHeightForWidth())
        self.inputFilesBody.setSizePolicy(sizePolicy2)
        self.inputFilesBodyLayout = QVBoxLayout(self.inputFilesBody)
        self.inputFilesBodyLayout.setSpacing(6)
        self.inputFilesBodyLayout.setObjectName(u"inputFilesBodyLayout")
        self.inputFilesBodyLayout.setContentsMargins(4, 2, 4, 4)
        self.inputFilesTree = QTreeView(self.inputFilesBody)
        self.inputFilesTree.setObjectName(u"inputFilesTree")
        sizePolicy3.setHeightForWidth(self.inputFilesTree.sizePolicy().hasHeightForWidth())
        self.inputFilesTree.setSizePolicy(sizePolicy3)
        self.inputFilesTree.setMaximumSize(QSize(16777215, 220))
        self.inputFilesTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.inputFilesTree.setStyleSheet(u"QTreeView#inputFilesTree {\n"
"    border: none;\n"
"    background: transparent;\n"
"}\n"
"QTreeView#inputFilesTree::item {\n"
"    padding: 2px 0px;\n"
"    border-radius: 4px;\n"
"}\n"
"QTreeView#inputFilesTree::item:hover {\n"
"    background-color: #f8fafc;\n"
"}\n"
"QTreeView#inputFilesTree::item:selected {\n"
"    background-color: #eff6ff;\n"
"    color: #1d4ed8;\n"
"}\n"
"QHeaderView::section {\n"
"    background-color: #f8fafc;\n"
"    color: #64748b;\n"
"    font-weight: 600;\n"
"    font-size: 11px;\n"
"    border: none;\n"
"    border-bottom: 1px solid #e2e8f0;\n"
"    padding: 3px 6px;\n"
"}")
        self.inputFilesTree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.inputFilesTree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.inputFilesTree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.inputFilesTree.setTextElideMode(Qt.ElideMiddle)
        self.inputFilesTree.setRootIsDecorated(False)
        self.inputFilesTree.setUniformRowHeights(True)

        self.inputFilesBodyLayout.addWidget(self.inputFilesTree)

        self.inputFilesEmpty = QLabel(self.inputFilesBody)
        self.inputFilesEmpty.setObjectName(u"inputFilesEmpty")
        self.inputFilesEmpty.setStyleSheet(u"QLabel#inputFilesEmpty {\n"
"    color: #64748b;\n"
"    font-size: 12px;\n"
"    font-style: italic;\n"
"    padding: 12px;\n"
"}")
        self.inputFilesEmpty.setAlignment(Qt.AlignCenter)
        self.inputFilesEmpty.setWordWrap(True)

        self.inputFilesBodyLayout.addWidget(self.inputFilesEmpty)

        self.line = QFrame(self.inputFilesBody)
        self.line.setObjectName(u"line")
        self.line.setAutoFillBackground(False)
        self.line.setStyleSheet(u"QFrame[frameShape=\"4\"] {\n"
"    border-top: 1px solid #CCC;\n"
"}")
        self.line.setFrameShadow(QFrame.Plain)
        self.line.setLineWidth(1)
        self.line.setMidLineWidth(0)
        self.line.setFrameShape(QFrame.Shape.HLine)

        self.inputFilesBodyLayout.addWidget(self.line)

        self.inputFilesLegend = QWidget(self.inputFilesBody)
        self.inputFilesLegend.setObjectName(u"inputFilesLegend")
        sizePolicy3.setHeightForWidth(self.inputFilesLegend.sizePolicy().hasHeightForWidth())
        self.inputFilesLegend.setSizePolicy(sizePolicy3)
        self.inputFilesLegend.setMinimumSize(QSize(0, 20))
        self.inputFilesLegend.setMaximumSize(QSize(16777215, 24))
        self.inputFilesLegendLayout = QHBoxLayout(self.inputFilesLegend)
        self.inputFilesLegendLayout.setSpacing(6)
        self.inputFilesLegendLayout.setObjectName(u"inputFilesLegendLayout")
        self.inputFilesLegendLayout.setContentsMargins(4, 0, 4, 2)
        self.horizontalSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.inputFilesLegendLayout.addItem(self.horizontalSpacer)

        self.inputFilesLegendAuto = QLabel(self.inputFilesLegend)
        self.inputFilesLegendAuto.setObjectName(u"inputFilesLegendAuto")
        self.inputFilesLegendAuto.setStyleSheet(u"QLabel#inputFilesLegendAuto {\n"
"    background-color: #dcfce7;\n"
"    color: #15803d;\n"
"    border: 1px solid #bbf7d0;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 0px 6px;\n"
"    min-height: 16px;\n"
"    max-height: 16px;\n"
"}")
        self.inputFilesLegendAuto.setAlignment(Qt.AlignCenter)

        self.inputFilesLegendLayout.addWidget(self.inputFilesLegendAuto)

        self.inputFilesLegendManual = QLabel(self.inputFilesLegend)
        self.inputFilesLegendManual.setObjectName(u"inputFilesLegendManual")
        self.inputFilesLegendManual.setStyleSheet(u"QLabel#inputFilesLegendManual {\n"
"    background-color: #e0f2fe;\n"
"    color: #0369a1;\n"
"    border: 1px solid #bae6fd;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 0px 6px;\n"
"    min-height: 16px;\n"
"    max-height: 16px;\n"
"}")
        self.inputFilesLegendManual.setAlignment(Qt.AlignCenter)

        self.inputFilesLegendLayout.addWidget(self.inputFilesLegendManual)

        self.inputFilesLegendDeleted = QLabel(self.inputFilesLegend)
        self.inputFilesLegendDeleted.setObjectName(u"inputFilesLegendDeleted")
        self.inputFilesLegendDeleted.setStyleSheet(u"QLabel#inputFilesLegendDeleted {\n"
"    background-color: #fef3c7;\n"
"    color: #b45309;\n"
"    border: 1px solid #fde68a;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 0px 6px;\n"
"    min-height: 16px;\n"
"    max-height: 16px;\n"
"}")
        self.inputFilesLegendDeleted.setAlignment(Qt.AlignCenter)

        self.inputFilesLegendLayout.addWidget(self.inputFilesLegendDeleted)

        self.inputFilesLegendSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.inputFilesLegendLayout.addItem(self.inputFilesLegendSpacer)


        self.inputFilesBodyLayout.addWidget(self.inputFilesLegend)


        self.inputFilesLayout.addWidget(self.inputFilesBody)


        self.contentLayout.addWidget(self.inputFilesSection)

        self.outputFilesSection = QFrame(self.content)
        self.outputFilesSection.setObjectName(u"outputFilesSection")
        sizePolicy2.setHeightForWidth(self.outputFilesSection.sizePolicy().hasHeightForWidth())
        self.outputFilesSection.setSizePolicy(sizePolicy2)
        self.outputFilesSection.setStyleSheet(u"QFrame#outputFilesSection {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#outputFilesSection:hover {\n"
"    border-color: #cbd5e1;\n"
"}")
        self.outputFilesLayout = QVBoxLayout(self.outputFilesSection)
        self.outputFilesLayout.setSpacing(2)
        self.outputFilesLayout.setObjectName(u"outputFilesLayout")
        self.outputFilesLayout.setContentsMargins(4, 4, 4, 4)
        self.outputFilesHeader = QWidget(self.outputFilesSection)
        self.outputFilesHeader.setObjectName(u"outputFilesHeader")
        sizePolicy3.setHeightForWidth(self.outputFilesHeader.sizePolicy().hasHeightForWidth())
        self.outputFilesHeader.setSizePolicy(sizePolicy3)
        self.outputFilesHeader.setMaximumSize(QSize(16777215, 32))
        self.outputFilesHeader.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.outputFilesHeaderLayout = QHBoxLayout(self.outputFilesHeader)
        self.outputFilesHeaderLayout.setSpacing(6)
        self.outputFilesHeaderLayout.setObjectName(u"outputFilesHeaderLayout")
        self.outputFilesHeaderLayout.setContentsMargins(6, 4, 6, 4)
        self.outputFilesChevron = QLabel(self.outputFilesHeader)
        self.outputFilesChevron.setObjectName(u"outputFilesChevron")
        self.outputFilesChevron.setStyleSheet(u"QLabel#outputFilesChevron {\n"
"    font-size: 10px;\n"
"    color: #64748b;\n"
"    font-weight: bold;\n"
"}")

        self.outputFilesHeaderLayout.addWidget(self.outputFilesChevron)

        self.outputFilesIcon = QLabel(self.outputFilesHeader)
        self.outputFilesIcon.setObjectName(u"outputFilesIcon")
        self.outputFilesIcon.setMinimumSize(QSize(16, 16))
        self.outputFilesIcon.setMaximumSize(QSize(16, 16))
        self.outputFilesIcon.setAlignment(Qt.AlignCenter)

        self.outputFilesHeaderLayout.addWidget(self.outputFilesIcon)

        self.outputFilesToggle = QToolButton(self.outputFilesHeader)
        self.outputFilesToggle.setObjectName(u"outputFilesToggle")
        self.outputFilesToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.outputFilesToggle.setStyleSheet(u"QToolButton#outputFilesToggle {\n"
"    border: 2px solid transparent;\n"
"    background: transparent;\n"
"    font-weight: bold;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    padding: 0px;\n"
"}\n"
"QToolButton#outputFilesToggle:focus:enabled { border-color: #0f172a; }")
        self.outputFilesToggle.setCheckable(True)
        self.outputFilesToggle.setChecked(False)

        self.outputFilesHeaderLayout.addWidget(self.outputFilesToggle)

        self.outputFilesCount = QLabel(self.outputFilesHeader)
        self.outputFilesCount.setObjectName(u"outputFilesCount")
        sizePolicy4.setHeightForWidth(self.outputFilesCount.sizePolicy().hasHeightForWidth())
        self.outputFilesCount.setSizePolicy(sizePolicy4)
        self.outputFilesCount.setMaximumSize(QSize(16777215, 18))
        self.outputFilesCount.setStyleSheet(u"QLabel#outputFilesCount {\n"
"    background-color: #f1f5f9;\n"
"    color: #475569;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    padding: 1px 7px;\n"
"    border-radius: 9px;\n"
"    min-width: 14px;\n"
"}")
        self.outputFilesCount.setAlignment(Qt.AlignCenter)

        self.outputFilesHeaderLayout.addWidget(self.outputFilesCount)

        self.outputFilesSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.outputFilesHeaderLayout.addItem(self.outputFilesSpacer)

        self.outputFilesAdd = QPushButton(self.outputFilesHeader)
        self.outputFilesAdd.setObjectName(u"outputFilesAdd")
        self.outputFilesAdd.setVisible(False)

        self.outputFilesHeaderLayout.addWidget(self.outputFilesAdd)


        self.outputFilesLayout.addWidget(self.outputFilesHeader)

        self.outputFilesBody = QWidget(self.outputFilesSection)
        self.outputFilesBody.setObjectName(u"outputFilesBody")
        sizePolicy2.setHeightForWidth(self.outputFilesBody.sizePolicy().hasHeightForWidth())
        self.outputFilesBody.setSizePolicy(sizePolicy2)
        self.outputFilesBody.setVisible(False)
        self.outputFilesBodyLayout = QVBoxLayout(self.outputFilesBody)
        self.outputFilesBodyLayout.setSpacing(6)
        self.outputFilesBodyLayout.setObjectName(u"outputFilesBodyLayout")
        self.outputFilesBodyLayout.setContentsMargins(4, 2, 4, 4)
        self.outputFilesTree = QTreeView(self.outputFilesBody)
        self.outputFilesTree.setObjectName(u"outputFilesTree")
        sizePolicy3.setHeightForWidth(self.outputFilesTree.sizePolicy().hasHeightForWidth())
        self.outputFilesTree.setSizePolicy(sizePolicy3)
        self.outputFilesTree.setMaximumSize(QSize(16777215, 220))
        self.outputFilesTree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.outputFilesTree.setStyleSheet(u"QTreeView#outputFilesTree {\n"
"    border: none;\n"
"    background: transparent;\n"
"}\n"
"QTreeView#outputFilesTree::item {\n"
"    padding: 2px 0px;\n"
"    border-radius: 4px;\n"
"}\n"
"QTreeView#outputFilesTree::item:hover {\n"
"    background-color: #f8fafc;\n"
"}\n"
"QTreeView#outputFilesTree::item:selected {\n"
"    background-color: #eff6ff;\n"
"    color: #1d4ed8;\n"
"}\n"
"QHeaderView::section {\n"
"    background-color: #f8fafc;\n"
"    color: #64748b;\n"
"    font-weight: 600;\n"
"    font-size: 11px;\n"
"    border: none;\n"
"    border-bottom: 1px solid #e2e8f0;\n"
"    padding: 3px 6px;\n"
"}")
        self.outputFilesTree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.outputFilesTree.setSelectionMode(QAbstractItemView.SingleSelection)
        self.outputFilesTree.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.outputFilesTree.setTextElideMode(Qt.ElideMiddle)
        self.outputFilesTree.setRootIsDecorated(False)
        self.outputFilesTree.setUniformRowHeights(True)

        self.outputFilesBodyLayout.addWidget(self.outputFilesTree)

        self.outputFilesEmpty = QLabel(self.outputFilesBody)
        self.outputFilesEmpty.setObjectName(u"outputFilesEmpty")
        self.outputFilesEmpty.setStyleSheet(u"QLabel#outputFilesEmpty {\n"
"    color: #64748b;\n"
"    font-size: 12px;\n"
"    font-style: italic;\n"
"    padding: 12px;\n"
"}")
        self.outputFilesEmpty.setAlignment(Qt.AlignCenter)
        self.outputFilesEmpty.setWordWrap(True)

        self.outputFilesBodyLayout.addWidget(self.outputFilesEmpty)


        self.outputFilesLayout.addWidget(self.outputFilesBody)


        self.contentLayout.addWidget(self.outputFilesSection)

        self.operationsHeaderWidget = QWidget(self.content)
        self.operationsHeaderWidget.setObjectName(u"operationsHeaderWidget")
        self.operationsHeaderLayout = QVBoxLayout(self.operationsHeaderWidget)
        self.operationsHeaderLayout.setSpacing(3)
        self.operationsHeaderLayout.setObjectName(u"operationsHeaderLayout")
        self.operationsHeaderLayout.setContentsMargins(0, 4, 0, 0)
        self.operationsTitle = QLabel(self.operationsHeaderWidget)
        self.operationsTitle.setObjectName(u"operationsTitle")
        self.operationsTitle.setStyleSheet(u"QLabel#operationsTitle {\n"
"    font-size: 15px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}")

        self.operationsHeaderLayout.addWidget(self.operationsTitle)

        self.operationsProgressLabel = QLabel(self.operationsHeaderWidget)
        self.operationsProgressLabel.setObjectName(u"operationsProgressLabel")
        self.operationsProgressLabel.setStyleSheet(u"QLabel#operationsProgressLabel {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    font-weight: 500;\n"
"}")

        self.operationsHeaderLayout.addWidget(self.operationsProgressLabel)

        self.operationsProgress = QProgressBar(self.operationsHeaderWidget)
        self.operationsProgress.setObjectName(u"operationsProgress")
        self.operationsProgress.setStyleSheet(u"QProgressBar#operationsProgress {\n"
"    background-color: #e2e8f0;\n"
"    border-radius: 3px;\n"
"    max-height: 6px;\n"
"    min-height: 6px;\n"
"    border: none;\n"
"}\n"
"QProgressBar#operationsProgress::chunk {\n"
"    background-color: #16a34a;\n"
"    border-radius: 3px;\n"
"}")
        self.operationsProgress.setMaximum(4)
        self.operationsProgress.setValue(0)
        self.operationsProgress.setTextVisible(False)

        self.operationsHeaderLayout.addWidget(self.operationsProgress)


        self.contentLayout.addWidget(self.operationsHeaderWidget)

        self.stepDetect = QFrame(self.content)
        self.stepDetect.setObjectName(u"stepDetect")
        sizePolicy2.setHeightForWidth(self.stepDetect.sizePolicy().hasHeightForWidth())
        self.stepDetect.setSizePolicy(sizePolicy2)
        self.stepDetect.setStyleSheet(u"QFrame#stepDetect {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#stepDetect:hover {\n"
"    border-color: #cbd5e1;\n"
"}")
        self.stepDetectLayout = QVBoxLayout(self.stepDetect)
        self.stepDetectLayout.setSpacing(0)
        self.stepDetectLayout.setObjectName(u"stepDetectLayout")
        self.stepDetectLayout.setContentsMargins(0, 0, 0, 0)
        self.stepDetectHeader = QWidget(self.stepDetect)
        self.stepDetectHeader.setObjectName(u"stepDetectHeader")
        sizePolicy3.setHeightForWidth(self.stepDetectHeader.sizePolicy().hasHeightForWidth())
        self.stepDetectHeader.setSizePolicy(sizePolicy3)
        self.stepDetectHeader.setMaximumSize(QSize(16777215, 46))
        self.stepDetectHeader.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepDetectHeaderLayout = QHBoxLayout(self.stepDetectHeader)
        self.stepDetectHeaderLayout.setSpacing(8)
        self.stepDetectHeaderLayout.setObjectName(u"stepDetectHeaderLayout")
        self.stepDetectHeaderLayout.setContentsMargins(8, 4, 8, 4)
        self.stepDetectNumber = QLabel(self.stepDetectHeader)
        self.stepDetectNumber.setObjectName(u"stepDetectNumber")
        self.stepDetectNumber.setMinimumSize(QSize(30, 30))
        self.stepDetectNumber.setMaximumSize(QSize(30, 30))
        self.stepDetectNumber.setStyleSheet(u"QLabel#stepDetectNumber {\n"
"                          background-color: #64748b;\n"
"                          color: #ffffff;\n"
"                          border: none;\n"
"                          border-radius: 15px;\n"
"                          font-weight: bold;\n"
"                          font-size: 13px;\n"
"                      }\n"
"                      QLabel#stepDetectNumber[stepStatus=\"ready\"] { background-color: #0369a1; }\n"
"                      QLabel#stepDetectNumber[stepStatus=\"done\"] { background-color: #1e293b; }\n"
"                      QLabel#stepDetectNumber[stepStatus=\"running\"] { background-color: #b45309; }")
        self.stepDetectNumber.setAlignment(Qt.AlignCenter)
        self.stepDetectNumber.setProperty(u"stepStatus", u"ready")

        self.stepDetectHeaderLayout.addWidget(self.stepDetectNumber)

        self.stepDetectTextColumn = QVBoxLayout()
        self.stepDetectTextColumn.setSpacing(2)
        self.stepDetectTextColumn.setObjectName(u"stepDetectTextColumn")
        self.stepDetectTextColumn.setContentsMargins(0, 0, 0, 0)
        self.stepDetectToggle = QPushButton(self.stepDetectHeader)
        self.stepDetectToggle.setObjectName(u"stepDetectToggle")
        sizePolicy5 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy5.setHorizontalStretch(1)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.stepDetectToggle.sizePolicy().hasHeightForWidth())
        self.stepDetectToggle.setSizePolicy(sizePolicy5)
        self.stepDetectToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepDetectToggle.setStyleSheet(u"QPushButton#stepDetectToggle {\n"
"    border: 2px solid transparent;\n"
"    background: transparent;\n"
"    text-align: left;\n"
"    padding: 0px;\n"
"    font-size: 13px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stepDetectToggle:focus:enabled { border-color: #0f172a; }")
        self.stepDetectToggle.setCheckable(True)
        self.stepDetectToggle.setChecked(True)

        self.stepDetectTextColumn.addWidget(self.stepDetectToggle)

        self.stepDetectSubtitle = QLabel(self.stepDetectHeader)
        self.stepDetectSubtitle.setObjectName(u"stepDetectSubtitle")
        self.stepDetectSubtitle.setStyleSheet(u"QLabel#stepDetectSubtitle {\n"
"    font-size: 10px;\n"
"    color: #64748b;\n"
"}")
        self.stepDetectSubtitle.setWordWrap(True)

        self.stepDetectTextColumn.addWidget(self.stepDetectSubtitle)


        self.stepDetectHeaderLayout.addLayout(self.stepDetectTextColumn)

        self.stepDetectStatusBadge = QLabel(self.stepDetectHeader)
        self.stepDetectStatusBadge.setObjectName(u"stepDetectStatusBadge")
        self.stepDetectStatusBadge.setStyleSheet(u"QLabel#stepDetectStatusBadge {\n"
"                          background-color: #e0f2fe;\n"
"                          color: #0369a1;\n"
"                          border-radius: 9px;\n"
"                          font-weight: 600;\n"
"                          font-size: 10px;\n"
"                          padding: 2px 8px;\n"
"                      }\n"
"                      QLabel#stepDetectStatusBadge[stepStatus=\"done\"] { background-color: #dcfce7; color: #15803d; }\n"
"                      QLabel#stepDetectStatusBadge[stepStatus=\"running\"] { background-color: #fef3c7; color: #b45309; }")
        self.stepDetectStatusBadge.setAlignment(Qt.AlignCenter)
        self.stepDetectStatusBadge.setProperty(u"stepStatus", u"ready")

        self.stepDetectHeaderLayout.addWidget(self.stepDetectStatusBadge)

        self.stepDetectChevron = QLabel(self.stepDetectHeader)
        self.stepDetectChevron.setObjectName(u"stepDetectChevron")
        self.stepDetectChevron.setMinimumSize(QSize(14, 0))
        self.stepDetectChevron.setMaximumSize(QSize(14, 16777215))
        self.stepDetectChevron.setStyleSheet(u"QLabel#stepDetectChevron {\n"
"    font-size: 9px;\n"
"    font-weight: bold;\n"
"    color: #64748b;\n"
"}")
        self.stepDetectChevron.setAlignment(Qt.AlignCenter)

        self.stepDetectHeaderLayout.addWidget(self.stepDetectChevron)


        self.stepDetectLayout.addWidget(self.stepDetectHeader)

        self.stepDetectBody = QWidget(self.stepDetect)
        self.stepDetectBody.setObjectName(u"stepDetectBody")
        self.stepDetectBody.setStyleSheet(u"QWidget#stepDetectBody {\n"
"    border-top: 1px solid #f1f5f9;\n"
"    background: transparent;\n"
"}")
        self.stepDetectBodyLayout = QVBoxLayout(self.stepDetectBody)
        self.stepDetectBodyLayout.setSpacing(6)
        self.stepDetectBodyLayout.setObjectName(u"stepDetectBodyLayout")
        self.stepDetectBodyLayout.setContentsMargins(16, 8, 16, 10)
        self.stepDetectFields = QGridLayout()
        self.stepDetectFields.setSpacing(8)
        self.stepDetectFields.setObjectName(u"stepDetectFields")
        self.stepDetectFields.setContentsMargins(0, 0, 0, 0)
        self.detectConfidenceLabel = QLabel(self.stepDetectBody)
        self.detectConfidenceLabel.setObjectName(u"detectConfidenceLabel")
        self.detectConfidenceLabel.setStyleSheet(u"QLabel#detectConfidenceLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepDetectFields.addWidget(self.detectConfidenceLabel, 0, 0, 1, 1)

        self.detectConfidence = QDoubleSpinBox(self.stepDetectBody)
        self.detectConfidence.setObjectName(u"detectConfidence")
        self.detectConfidence.setStyleSheet(u"QDoubleSpinBox#detectConfidence {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #64748b;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    min-width: 75px;\n"
"    max-width: 75px;\n"
"}\n"
"QDoubleSpinBox#detectConfidence:focus {\n"
"    border: 2px solid #0369a1;\n"
"    padding: 3px 5px;\n"
"}\n"
"QDoubleSpinBox#detectConfidence::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QDoubleSpinBox#detectConfidence::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.detectConfidence.setMaximum(1.000000000000000)
        self.detectConfidence.setSingleStep(0.050000000000000)
        self.detectConfidence.setValue(0.300000000000000)

        self.stepDetectFields.addWidget(self.detectConfidence, 0, 1, 1, 1, Qt.AlignRight)

        self.detectMergeLabel = QLabel(self.stepDetectBody)
        self.detectMergeLabel.setObjectName(u"detectMergeLabel")
        self.detectMergeLabel.setStyleSheet(u"QLabel#detectMergeLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepDetectFields.addWidget(self.detectMergeLabel, 1, 0, 1, 1)

        self.detectMergeContainer = QFrame(self.stepDetectBody)
        self.detectMergeContainer.setObjectName(u"detectMergeContainer")
        self.detectMergeContainer.setStyleSheet(u"QFrame#detectMergeContainer {\n"
"    background-color: #f1f5f9;\n"
"    border-radius: 5px;\n"
"    padding: 2px;\n"
"}\n"
"QPushButton#detectMergeNMS, QPushButton#detectMergeNMM {\n"
"    background-color: transparent;\n"
"    color: #334155;\n"
"    border: 2px solid transparent;\n"
"    border-radius: 4px;\n"
"    font-size: 12px;\n"
"    font-weight: 500;\n"
"    padding: 4px 12px;\n"
"    min-height: 18px;\n"
"}\n"
"QPushButton#detectMergeNMS:checked, QPushButton#detectMergeNMM:checked {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: 600;\n"
"}\n"
"QPushButton#detectMergeNMS:hover:!checked, QPushButton#detectMergeNMM:hover:!checked {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#detectMergeNMS:focus:enabled, QPushButton#detectMergeNMM:focus:enabled { border-color: #0f172a; }\n"
"QPushButton#detectMergeNMS:checked:focus:enabled, QPushButton#detectMergeNMM:checked:focus:enabled { border-color: #ffffff; }")
        self.detectMergeLayout = QHBoxLayout(self.detectMergeContainer)
        self.detectMergeLayout.setSpacing(2)
        self.detectMergeLayout.setObjectName(u"detectMergeLayout")
        self.detectMergeLayout.setContentsMargins(0, 0, 0, 0)
        self.detectMergeNMS = QPushButton(self.detectMergeContainer)
        self.detectMergeGroup = QButtonGroup(MainWindow)
        self.detectMergeGroup.setObjectName(u"detectMergeGroup")
        self.detectMergeGroup.addButton(self.detectMergeNMS)
        self.detectMergeNMS.setObjectName(u"detectMergeNMS")
        self.detectMergeNMS.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.detectMergeNMS.setCheckable(True)
        self.detectMergeNMS.setChecked(True)

        self.detectMergeLayout.addWidget(self.detectMergeNMS)

        self.detectMergeNMM = QPushButton(self.detectMergeContainer)
        self.detectMergeGroup.addButton(self.detectMergeNMM)
        self.detectMergeNMM.setObjectName(u"detectMergeNMM")
        self.detectMergeNMM.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.detectMergeNMM.setCheckable(True)

        self.detectMergeLayout.addWidget(self.detectMergeNMM)


        self.stepDetectFields.addWidget(self.detectMergeContainer, 1, 1, 1, 1, Qt.AlignRight)

        self.detectThresholdLabel = QLabel(self.stepDetectBody)
        self.detectThresholdLabel.setObjectName(u"detectThresholdLabel")
        self.detectThresholdLabel.setStyleSheet(u"QLabel#detectThresholdLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"    margin-left: 12px;\n"
"    border-left: 2px solid #cbd5e1;\n"
"    padding-left: 8px;\n"
"}")

        self.stepDetectFields.addWidget(self.detectThresholdLabel, 2, 0, 1, 1)

        self.detectMergeThreshold = QDoubleSpinBox(self.stepDetectBody)
        self.detectMergeThreshold.setObjectName(u"detectMergeThreshold")
        self.detectMergeThreshold.setStyleSheet(u"QDoubleSpinBox#detectMergeThreshold {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #64748b;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    min-width: 75px;\n"
"    max-width: 75px;\n"
"}\n"
"QDoubleSpinBox#detectMergeThreshold:focus {\n"
"    border: 2px solid #0369a1;\n"
"    padding: 3px 5px;\n"
"}\n"
"QDoubleSpinBox#detectMergeThreshold::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QDoubleSpinBox#detectMergeThreshold::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.detectMergeThreshold.setMaximum(1.000000000000000)
        self.detectMergeThreshold.setSingleStep(0.050000000000000)
        self.detectMergeThreshold.setValue(0.200000000000000)

        self.stepDetectFields.addWidget(self.detectMergeThreshold, 2, 1, 1, 1, Qt.AlignRight)

        self.detectUseGPULabel = QLabel(self.stepDetectBody)
        self.detectUseGPULabel.setObjectName(u"detectUseGPULabel")
        self.detectUseGPULabel.setStyleSheet(u"QLabel#detectUseGPULabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepDetectFields.addWidget(self.detectUseGPULabel, 3, 0, 1, 1)

        self.detectUseGPU = QCheckBox(self.stepDetectBody)
        self.detectUseGPU.setObjectName(u"detectUseGPU")
        sizePolicy6 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        sizePolicy6.setHorizontalStretch(0)
        sizePolicy6.setVerticalStretch(0)
        sizePolicy6.setHeightForWidth(self.detectUseGPU.sizePolicy().hasHeightForWidth())
        self.detectUseGPU.setSizePolicy(sizePolicy6)
        self.detectUseGPU.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.detectUseGPU.setStyleSheet(u"QCheckBox#detectUseGPU { spacing: 0px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"                        QCheckBox#detectUseGPU::indicator { width: 36px; height: 20px;  border: 1px solid #64748b; border-radius: 10px; }\n"
"                        QCheckBox#detectUseGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.png); }\n"
"                        QCheckBox#detectUseGPU::indicator:checked { image: url(:/startrails/ui/switch_on.png); }\n"
"QCheckBox#detectUseGPU:focus:enabled { border-color: #0f172a; }")
        self.detectUseGPU.setChecked(True)

        self.stepDetectFields.addWidget(self.detectUseGPU, 3, 1, 1, 1, Qt.AlignRight)

        self.stepDetectFields.setColumnStretch(0, 1)
        self.stepDetectFields.setColumnStretch(1, 2)

        self.stepDetectBodyLayout.addLayout(self.stepDetectFields)

        self.detectError = QLabel(self.stepDetectBody)
        self.detectError.setObjectName(u"detectError")
        self.detectError.setStyleSheet(u"QLabel#detectError {\n"
"    font-size: 11px;\n"
"    color: #b91c1c;\n"
"}")
        self.detectError.setWordWrap(True)

        self.stepDetectBodyLayout.addWidget(self.detectError)

        self.detectRun = QPushButton(self.stepDetectBody)
        self.detectRun.setObjectName(u"detectRun")
        self.detectRun.setEnabled(False)
        self.detectRun.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.detectRun.setStyleSheet(u"QPushButton#detectRun {\n"
"    font-weight: bold;\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    padding: 7px 12px;\n"
"    border-radius: 6px;\n"
"    font-size: 13px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"QPushButton#detectRun:hover {\n"
"    background-color: #075985;\n"
"}\n"
"QPushButton#detectRun:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#detectRun:focus:enabled { border-color: #ffffff; }")

        self.stepDetectBodyLayout.addWidget(self.detectRun)


        self.stepDetectLayout.addWidget(self.stepDetectBody)


        self.contentLayout.addWidget(self.stepDetect)

        self.stepStack = QFrame(self.content)
        self.stepStack.setObjectName(u"stepStack")
        sizePolicy2.setHeightForWidth(self.stepStack.sizePolicy().hasHeightForWidth())
        self.stepStack.setSizePolicy(sizePolicy2)
        self.stepStack.setStyleSheet(u"QFrame#stepStack {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#stepStack:hover {\n"
"    border-color: #cbd5e1;\n"
"}")
        self.stepStackLayout = QVBoxLayout(self.stepStack)
        self.stepStackLayout.setSpacing(0)
        self.stepStackLayout.setObjectName(u"stepStackLayout")
        self.stepStackLayout.setContentsMargins(0, 0, 0, 0)
        self.stepStackHeader = QWidget(self.stepStack)
        self.stepStackHeader.setObjectName(u"stepStackHeader")
        sizePolicy3.setHeightForWidth(self.stepStackHeader.sizePolicy().hasHeightForWidth())
        self.stepStackHeader.setSizePolicy(sizePolicy3)
        self.stepStackHeader.setMaximumSize(QSize(16777215, 46))
        self.stepStackHeader.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepStackHeaderLayout = QHBoxLayout(self.stepStackHeader)
        self.stepStackHeaderLayout.setSpacing(8)
        self.stepStackHeaderLayout.setObjectName(u"stepStackHeaderLayout")
        self.stepStackHeaderLayout.setContentsMargins(8, 4, 8, 4)
        self.stepStackNumber = QLabel(self.stepStackHeader)
        self.stepStackNumber.setObjectName(u"stepStackNumber")
        self.stepStackNumber.setMinimumSize(QSize(30, 30))
        self.stepStackNumber.setMaximumSize(QSize(30, 30))
        self.stepStackNumber.setStyleSheet(u"QLabel#stepStackNumber {\n"
"                          background-color: #64748b;\n"
"                          color: #ffffff;\n"
"                          border: none;\n"
"                          border-radius: 15px;\n"
"                          font-weight: bold;\n"
"                          font-size: 13px;\n"
"                      }\n"
"                      QLabel#stepStackNumber[stepStatus=\"ready\"] { background-color: #0369a1; }\n"
"                      QLabel#stepStackNumber[stepStatus=\"done\"] { background-color: #1e293b; }\n"
"                      QLabel#stepStackNumber[stepStatus=\"running\"] { background-color: #b45309; }")
        self.stepStackNumber.setAlignment(Qt.AlignCenter)
        self.stepStackNumber.setProperty(u"stepStatus", u"ready")

        self.stepStackHeaderLayout.addWidget(self.stepStackNumber)

        self.stepStackTextColumn = QVBoxLayout()
        self.stepStackTextColumn.setSpacing(2)
        self.stepStackTextColumn.setObjectName(u"stepStackTextColumn")
        self.stepStackTextColumn.setContentsMargins(0, 0, 0, 0)
        self.stepStackToggle = QPushButton(self.stepStackHeader)
        self.stepStackToggle.setObjectName(u"stepStackToggle")
        sizePolicy5.setHeightForWidth(self.stepStackToggle.sizePolicy().hasHeightForWidth())
        self.stepStackToggle.setSizePolicy(sizePolicy5)
        self.stepStackToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepStackToggle.setStyleSheet(u"QPushButton#stepStackToggle {\n"
"    border: 2px solid transparent;\n"
"    background: transparent;\n"
"    text-align: left;\n"
"    padding: 0px;\n"
"    font-size: 13px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stepStackToggle:focus:enabled { border-color: #0f172a; }")
        self.stepStackToggle.setCheckable(True)
        self.stepStackToggle.setChecked(True)

        self.stepStackTextColumn.addWidget(self.stepStackToggle)

        self.stepStackSubtitle = QLabel(self.stepStackHeader)
        self.stepStackSubtitle.setObjectName(u"stepStackSubtitle")
        self.stepStackSubtitle.setStyleSheet(u"QLabel#stepStackSubtitle {\n"
"    font-size: 10px;\n"
"    color: #64748b;\n"
"}")
        self.stepStackSubtitle.setWordWrap(True)

        self.stepStackTextColumn.addWidget(self.stepStackSubtitle)


        self.stepStackHeaderLayout.addLayout(self.stepStackTextColumn)

        self.stepStackStatusBadge = QLabel(self.stepStackHeader)
        self.stepStackStatusBadge.setObjectName(u"stepStackStatusBadge")
        self.stepStackStatusBadge.setStyleSheet(u"QLabel#stepStackStatusBadge {\n"
"                          background-color: #e0f2fe;\n"
"                          color: #0369a1;\n"
"                          border-radius: 9px;\n"
"                          font-weight: 600;\n"
"                          font-size: 10px;\n"
"                          padding: 2px 8px;\n"
"                      }\n"
"                      QLabel#stepStackStatusBadge[stepStatus=\"done\"] { background-color: #dcfce7; color: #15803d; }\n"
"                      QLabel#stepStackStatusBadge[stepStatus=\"running\"] { background-color: #fef3c7; color: #b45309; }")
        self.stepStackStatusBadge.setAlignment(Qt.AlignCenter)
        self.stepStackStatusBadge.setProperty(u"stepStatus", u"ready")

        self.stepStackHeaderLayout.addWidget(self.stepStackStatusBadge)

        self.stepStackChevron = QLabel(self.stepStackHeader)
        self.stepStackChevron.setObjectName(u"stepStackChevron")
        self.stepStackChevron.setMinimumSize(QSize(14, 0))
        self.stepStackChevron.setMaximumSize(QSize(14, 16777215))
        self.stepStackChevron.setStyleSheet(u"QLabel#stepStackChevron {\n"
"    font-size: 9px;\n"
"    font-weight: bold;\n"
"    color: #64748b;\n"
"}")
        self.stepStackChevron.setAlignment(Qt.AlignCenter)

        self.stepStackHeaderLayout.addWidget(self.stepStackChevron)


        self.stepStackLayout.addWidget(self.stepStackHeader)

        self.stepStackBody = QWidget(self.stepStack)
        self.stepStackBody.setObjectName(u"stepStackBody")
        self.stepStackBody.setStyleSheet(u"QWidget#stepStackBody {\n"
"    border-top: 1px solid #f1f5f9;\n"
"    background: transparent;\n"
"}")
        self.stepStackBodyLayout = QVBoxLayout(self.stepStackBody)
        self.stepStackBodyLayout.setSpacing(6)
        self.stepStackBodyLayout.setObjectName(u"stepStackBodyLayout")
        self.stepStackBodyLayout.setContentsMargins(16, 8, 16, 10)
        self.stepStackFields = QGridLayout()
        self.stepStackFields.setSpacing(8)
        self.stepStackFields.setObjectName(u"stepStackFields")
        self.stepStackFields.setContentsMargins(0, 0, 0, 0)
        self.stackMethodLabel = QLabel(self.stepStackBody)
        self.stackMethodLabel.setObjectName(u"stackMethodLabel")
        self.stackMethodLabel.setStyleSheet(u"QLabel#stackMethodLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepStackFields.addWidget(self.stackMethodLabel, 0, 0, 1, 1)

        self.stackMethod = QLabel(self.stepStackBody)
        self.stackMethod.setObjectName(u"stackMethod")
        self.stackMethod.setStyleSheet(u"QLabel#stackMethod {\n"
"    color: #0f172a;\n"
"    font-size: 12px;\n"
"    font-weight: 500;\n"
"    background-color: #f8fafc;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 4px;\n"
"    padding: 3px 12px;\n"
"}")
        self.stackMethod.setAlignment(Qt.AlignCenter)

        self.stepStackFields.addWidget(self.stackMethod, 0, 1, 1, 1, Qt.AlignRight)

        self.stackStreaksLabel = QLabel(self.stepStackBody)
        self.stackStreaksLabel.setObjectName(u"stackStreaksLabel")
        self.stackStreaksLabel.setStyleSheet(u"QLabel#stackStreaksLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepStackFields.addWidget(self.stackStreaksLabel, 1, 0, 1, 1)

        self.stackStreaksContainer = QFrame(self.stepStackBody)
        self.stackStreaksContainer.setObjectName(u"stackStreaksContainer")
        self.stackStreaksContainer.setStyleSheet(u"QFrame#stackStreaksContainer {\n"
"    background-color: #f1f5f9;\n"
"    border-radius: 5px;\n"
"    padding: 2px;\n"
"}\n"
"QPushButton#stackStreaksKeep, QPushButton#stackStreaksRemove {\n"
"    background-color: transparent;\n"
"    color: #334155;\n"
"    border: 2px solid transparent;\n"
"    border-radius: 4px;\n"
"    font-size: 12px;\n"
"    font-weight: 500;\n"
"    padding: 4px 14px;\n"
"    min-height: 18px;\n"
"}\n"
"QPushButton#stackStreaksKeep:checked, QPushButton#stackStreaksRemove:checked {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: 600;\n"
"}\n"
"QPushButton#stackStreaksKeep:hover:!checked, QPushButton#stackStreaksRemove:hover:!checked {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stackStreaksRemove:disabled {\n"
"    color: #94a3b8;\n"
"    background-color: transparent;\n"
"}\n"
"QPushButton#stackStreaksKeep:focus:enabled, QPushButton#stackStreaksRemove:focus:enabled { border-color: #0f172a; }\n"
"QPushButton#stackStre"
                        "aksKeep:checked:focus:enabled, QPushButton#stackStreaksRemove:checked:focus:enabled { border-color: #ffffff; }")
        self.stackStreaksLayout = QHBoxLayout(self.stackStreaksContainer)
        self.stackStreaksLayout.setSpacing(2)
        self.stackStreaksLayout.setObjectName(u"stackStreaksLayout")
        self.stackStreaksLayout.setContentsMargins(0, 0, 0, 0)
        self.stackStreaksKeep = QPushButton(self.stackStreaksContainer)
        self.stackStreaksGroup = QButtonGroup(MainWindow)
        self.stackStreaksGroup.setObjectName(u"stackStreaksGroup")
        self.stackStreaksGroup.addButton(self.stackStreaksKeep)
        self.stackStreaksKeep.setObjectName(u"stackStreaksKeep")
        self.stackStreaksKeep.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackStreaksKeep.setCheckable(True)
        self.stackStreaksKeep.setChecked(True)

        self.stackStreaksLayout.addWidget(self.stackStreaksKeep)

        self.stackStreaksRemove = QPushButton(self.stackStreaksContainer)
        self.stackStreaksGroup.addButton(self.stackStreaksRemove)
        self.stackStreaksRemove.setObjectName(u"stackStreaksRemove")
        self.stackStreaksRemove.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackStreaksRemove.setCheckable(True)

        self.stackStreaksLayout.addWidget(self.stackStreaksRemove)


        self.stepStackFields.addWidget(self.stackStreaksContainer, 1, 1, 1, 1, Qt.AlignRight)

        self.stackFadeLabel = QLabel(self.stepStackBody)
        self.stackFadeLabel.setObjectName(u"stackFadeLabel")
        self.stackFadeLabel.setStyleSheet(u"QLabel#stackFadeLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepStackFields.addWidget(self.stackFadeLabel, 2, 0, 1, 1)

        self.stackFadeContainer = QFrame(self.stepStackBody)
        self.stackFadeContainer.setObjectName(u"stackFadeContainer")
        self.stackFadeContainer.setStyleSheet(u"QFrame#stackFadeContainer {\n"
"    background-color: #f1f5f9;\n"
"    border-radius: 5px;\n"
"    padding: 2px;\n"
"}\n"
"QPushButton#stackFadeOff, QPushButton#stackFadeStart, QPushButton#stackFadeEnd, QPushButton#stackFadeBoth {\n"
"    background-color: transparent;\n"
"    color: #334155;\n"
"    border: 2px solid transparent;\n"
"    border-radius: 4px;\n"
"    font-size: 11px;\n"
"    font-weight: 500;\n"
"    padding: 4px 8px;\n"
"    min-height: 18px;\n"
"}\n"
"QPushButton#stackFadeOff:checked, QPushButton#stackFadeStart:checked, QPushButton#stackFadeEnd:checked, QPushButton#stackFadeBoth:checked {\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    font-weight: 600;\n"
"}\n"
"QPushButton#stackFadeOff:hover:!checked, QPushButton#stackFadeStart:hover:!checked, QPushButton#stackFadeEnd:hover:!checked, QPushButton#stackFadeBoth:hover:!checked {\n"
"    background-color: #e2e8f0;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stackFadeOff:focus:enabled, QPushButton#stackFadeStart:focus:enable"
                        "d, QPushButton#stackFadeEnd:focus:enabled, QPushButton#stackFadeBoth:focus:enabled { border-color: #0f172a; }\n"
"QPushButton#stackFadeOff:checked:focus:enabled, QPushButton#stackFadeStart:checked:focus:enabled, QPushButton#stackFadeEnd:checked:focus:enabled, QPushButton#stackFadeBoth:checked:focus:enabled { border-color: #ffffff; }")
        self.stackFadeLayout = QHBoxLayout(self.stackFadeContainer)
        self.stackFadeLayout.setSpacing(2)
        self.stackFadeLayout.setObjectName(u"stackFadeLayout")
        self.stackFadeLayout.setContentsMargins(0, 0, 0, 0)
        self.stackFadeOff = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup = QButtonGroup(MainWindow)
        self.stackFadeGroup.setObjectName(u"stackFadeGroup")
        self.stackFadeGroup.addButton(self.stackFadeOff)
        self.stackFadeOff.setObjectName(u"stackFadeOff")
        self.stackFadeOff.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeOff.setCheckable(True)

        self.stackFadeLayout.addWidget(self.stackFadeOff)

        self.stackFadeStart = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup.addButton(self.stackFadeStart)
        self.stackFadeStart.setObjectName(u"stackFadeStart")
        self.stackFadeStart.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeStart.setCheckable(True)

        self.stackFadeLayout.addWidget(self.stackFadeStart)

        self.stackFadeEnd = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup.addButton(self.stackFadeEnd)
        self.stackFadeEnd.setObjectName(u"stackFadeEnd")
        self.stackFadeEnd.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeEnd.setCheckable(True)

        self.stackFadeLayout.addWidget(self.stackFadeEnd)

        self.stackFadeBoth = QPushButton(self.stackFadeContainer)
        self.stackFadeGroup.addButton(self.stackFadeBoth)
        self.stackFadeBoth.setObjectName(u"stackFadeBoth")
        self.stackFadeBoth.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackFadeBoth.setCheckable(True)
        self.stackFadeBoth.setChecked(True)

        self.stackFadeLayout.addWidget(self.stackFadeBoth)


        self.stepStackFields.addWidget(self.stackFadeContainer, 2, 1, 1, 1, Qt.AlignRight)

        self.stackAmountLabel = QLabel(self.stepStackBody)
        self.stackAmountLabel.setObjectName(u"stackAmountLabel")
        self.stackAmountLabel.setStyleSheet(u"QLabel#stackAmountLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"    margin-left: 12px;\n"
"    border-left: 2px solid #cbd5e1;\n"
"    padding-left: 8px;\n"
"}")

        self.stepStackFields.addWidget(self.stackAmountLabel, 3, 0, 1, 1)

        self.stackFadeAmount = QSpinBox(self.stepStackBody)
        self.stackFadeAmount.setObjectName(u"stackFadeAmount")
        self.stackFadeAmount.setStyleSheet(u"QSpinBox#stackFadeAmount {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #64748b;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    min-width: 75px;\n"
"    max-width: 75px;\n"
"}\n"
"QSpinBox#stackFadeAmount:focus {\n"
"    border: 2px solid #0369a1;\n"
"    padding: 3px 5px;\n"
"}\n"
"QSpinBox#stackFadeAmount:disabled {\n"
"    background-color: #f1f5f9;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QSpinBox#stackFadeAmount::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QSpinBox#stackFadeAmount::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.stackFadeAmount.setMaximum(100)
        self.stackFadeAmount.setValue(20)

        self.stepStackFields.addWidget(self.stackFadeAmount, 3, 1, 1, 1, Qt.AlignRight)

        self.stackUseGPULabel = QLabel(self.stepStackBody)
        self.stackUseGPULabel.setObjectName(u"stackUseGPULabel")
        self.stackUseGPULabel.setStyleSheet(u"QLabel#stackUseGPULabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepStackFields.addWidget(self.stackUseGPULabel, 4, 0, 1, 1)

        self.stackUseGPU = QCheckBox(self.stepStackBody)
        self.stackUseGPU.setObjectName(u"stackUseGPU")
        sizePolicy6.setHeightForWidth(self.stackUseGPU.sizePolicy().hasHeightForWidth())
        self.stackUseGPU.setSizePolicy(sizePolicy6)
        self.stackUseGPU.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackUseGPU.setStyleSheet(u"QCheckBox#stackUseGPU { spacing: 0px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"                        QCheckBox#stackUseGPU::indicator { width: 36px; height: 20px;  border: 1px solid #64748b; border-radius: 10px; }\n"
"                        QCheckBox#stackUseGPU::indicator:unchecked { image: url(:/startrails/ui/switch_off.png); }\n"
"                        QCheckBox#stackUseGPU::indicator:checked { image: url(:/startrails/ui/switch_on.png); }\n"
"QCheckBox#stackUseGPU:focus:enabled { border-color: #0f172a; }")
        self.stackUseGPU.setChecked(True)

        self.stepStackFields.addWidget(self.stackUseGPU, 4, 1, 1, 1, Qt.AlignRight)

        self.stackBatchLabel = QLabel(self.stepStackBody)
        self.stackBatchLabel.setObjectName(u"stackBatchLabel")
        self.stackBatchLabel.setStyleSheet(u"QLabel#stackBatchLabel {\n"
"    color: #334155;\n"
"    font-size: 12px;\n"
"}")

        self.stepStackFields.addWidget(self.stackBatchLabel, 5, 0, 1, 1)

        self.stackBatchSize = QSpinBox(self.stepStackBody)
        self.stackBatchSize.setObjectName(u"stackBatchSize")
        self.stackBatchSize.setStyleSheet(u"QSpinBox#stackBatchSize {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #64748b;\n"
"    border-radius: 4px;\n"
"    padding: 4px 6px;\n"
"    font-size: 12px;\n"
"    color: #0f172a;\n"
"    min-width: 75px;\n"
"    max-width: 75px;\n"
"}\n"
"QSpinBox#stackBatchSize:focus {\n"
"    border: 2px solid #0369a1;\n"
"    padding: 3px 5px;\n"
"}\n"
"QSpinBox#stackBatchSize::up-arrow { image: url(:/startrails/ui/arrow_up.svg); width: 10px; height: 6px; }\n"
"QSpinBox#stackBatchSize::down-arrow { image: url(:/startrails/ui/arrow_down.svg); width: 10px; height: 6px; }")
        self.stackBatchSize.setMinimum(1)
        self.stackBatchSize.setMaximum(2147483647)
        self.stackBatchSize.setValue(16)

        self.stepStackFields.addWidget(self.stackBatchSize, 5, 1, 1, 1, Qt.AlignRight)

        self.stepStackFields.setColumnStretch(0, 1)
        self.stepStackFields.setColumnStretch(1, 2)

        self.stepStackBodyLayout.addLayout(self.stepStackFields)

        self.stackMemory = QLabel(self.stepStackBody)
        self.stackMemory.setObjectName(u"stackMemory")
        self.stackMemory.setStyleSheet(u"QLabel#stackMemory {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    padding-top: 2px;\n"
"}")
        self.stackMemory.setWordWrap(True)

        self.stepStackBodyLayout.addWidget(self.stackMemory)

        self.stackError = QLabel(self.stepStackBody)
        self.stackError.setObjectName(u"stackError")
        self.stackError.setStyleSheet(u"QLabel#stackError {\n"
"    font-size: 11px;\n"
"    color: #b91c1c;\n"
"}")
        self.stackError.setWordWrap(True)

        self.stepStackBodyLayout.addWidget(self.stackError)

        self.stackRun = QPushButton(self.stepStackBody)
        self.stackRun.setObjectName(u"stackRun")
        self.stackRun.setEnabled(False)
        self.stackRun.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stackRun.setStyleSheet(u"QPushButton#stackRun {\n"
"    font-weight: bold;\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    padding: 7px 12px;\n"
"    border-radius: 6px;\n"
"    font-size: 13px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"QPushButton#stackRun:hover {\n"
"    background-color: #075985;\n"
"}\n"
"QPushButton#stackRun:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#stackRun:focus:enabled { border-color: #ffffff; }")

        self.stepStackBodyLayout.addWidget(self.stackRun)


        self.stepStackLayout.addWidget(self.stepStackBody)


        self.contentLayout.addWidget(self.stepStack)

        self.stepReview = QFrame(self.content)
        self.stepReview.setObjectName(u"stepReview")
        sizePolicy2.setHeightForWidth(self.stepReview.sizePolicy().hasHeightForWidth())
        self.stepReview.setSizePolicy(sizePolicy2)
        self.stepReview.setStyleSheet(u"QFrame#stepReview {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#stepReview:hover {\n"
"    border-color: #cbd5e1;\n"
"}")
        self.stepReviewLayout = QVBoxLayout(self.stepReview)
        self.stepReviewLayout.setSpacing(0)
        self.stepReviewLayout.setObjectName(u"stepReviewLayout")
        self.stepReviewLayout.setContentsMargins(0, 0, 0, 0)
        self.stepReviewHeader = QWidget(self.stepReview)
        self.stepReviewHeader.setObjectName(u"stepReviewHeader")
        sizePolicy3.setHeightForWidth(self.stepReviewHeader.sizePolicy().hasHeightForWidth())
        self.stepReviewHeader.setSizePolicy(sizePolicy3)
        self.stepReviewHeader.setMaximumSize(QSize(16777215, 46))
        self.stepReviewHeader.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepReviewHeaderLayout = QHBoxLayout(self.stepReviewHeader)
        self.stepReviewHeaderLayout.setSpacing(8)
        self.stepReviewHeaderLayout.setObjectName(u"stepReviewHeaderLayout")
        self.stepReviewHeaderLayout.setContentsMargins(8, 4, 8, 4)
        self.stepReviewNumber = QLabel(self.stepReviewHeader)
        self.stepReviewNumber.setObjectName(u"stepReviewNumber")
        self.stepReviewNumber.setMinimumSize(QSize(30, 30))
        self.stepReviewNumber.setMaximumSize(QSize(30, 30))
        self.stepReviewNumber.setStyleSheet(u"QLabel#stepReviewNumber {\n"
"                          background-color: #64748b;\n"
"                          color: #ffffff;\n"
"                          border: none;\n"
"                          border-radius: 15px;\n"
"                          font-weight: bold;\n"
"                          font-size: 13px;\n"
"                      }\n"
"                      QLabel#stepReviewNumber[stepStatus=\"ready\"] { background-color: #0369a1; }\n"
"                      QLabel#stepReviewNumber[stepStatus=\"done\"] { background-color: #1e293b; }\n"
"                      QLabel#stepReviewNumber[stepStatus=\"running\"] { background-color: #b45309; }")
        self.stepReviewNumber.setAlignment(Qt.AlignCenter)
        self.stepReviewNumber.setProperty(u"stepStatus", u"locked")

        self.stepReviewHeaderLayout.addWidget(self.stepReviewNumber)

        self.stepReviewTextColumn = QVBoxLayout()
        self.stepReviewTextColumn.setSpacing(2)
        self.stepReviewTextColumn.setObjectName(u"stepReviewTextColumn")
        self.stepReviewTextColumn.setContentsMargins(0, 0, 0, 0)
        self.stepReviewToggle = QPushButton(self.stepReviewHeader)
        self.stepReviewToggle.setObjectName(u"stepReviewToggle")
        sizePolicy5.setHeightForWidth(self.stepReviewToggle.sizePolicy().hasHeightForWidth())
        self.stepReviewToggle.setSizePolicy(sizePolicy5)
        self.stepReviewToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepReviewToggle.setStyleSheet(u"QPushButton#stepReviewToggle {\n"
"    border: 2px solid transparent;\n"
"    background: transparent;\n"
"    text-align: left;\n"
"    padding: 0px;\n"
"    font-size: 13px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stepReviewToggle:focus:enabled { border-color: #0f172a; }")
        self.stepReviewToggle.setCheckable(True)
        self.stepReviewToggle.setChecked(True)

        self.stepReviewTextColumn.addWidget(self.stepReviewToggle)

        self.stepReviewSubtitle = QLabel(self.stepReviewHeader)
        self.stepReviewSubtitle.setObjectName(u"stepReviewSubtitle")
        self.stepReviewSubtitle.setStyleSheet(u"QLabel#stepReviewSubtitle {\n"
"    color: #64748b;\n"
"    font-size: 11px;\n"
"}")

        self.stepReviewTextColumn.addWidget(self.stepReviewSubtitle)


        self.stepReviewHeaderLayout.addLayout(self.stepReviewTextColumn)

        self.stepReviewStatusBadge = QLabel(self.stepReviewHeader)
        self.stepReviewStatusBadge.setObjectName(u"stepReviewStatusBadge")
        self.stepReviewStatusBadge.setStyleSheet(u"QLabel#stepReviewStatusBadge {\n"
"                          background-color: #e0f2fe;\n"
"                          color: #0369a1;\n"
"                          border-radius: 9px;\n"
"                          font-weight: 600;\n"
"                          font-size: 10px;\n"
"                          padding: 2px 8px;\n"
"                      }\n"
"                      QLabel#stepReviewStatusBadge[stepStatus=\"done\"] { background-color: #dcfce7; color: #15803d; }\n"
"                      QLabel#stepReviewStatusBadge[stepStatus=\"running\"] { background-color: #fef3c7; color: #b45309; }")
        self.stepReviewStatusBadge.setAlignment(Qt.AlignCenter)
        self.stepReviewStatusBadge.setProperty(u"stepStatus", u"locked")

        self.stepReviewHeaderLayout.addWidget(self.stepReviewStatusBadge)

        self.stepReviewChevron = QLabel(self.stepReviewHeader)
        self.stepReviewChevron.setObjectName(u"stepReviewChevron")
        self.stepReviewChevron.setMinimumSize(QSize(14, 0))
        self.stepReviewChevron.setMaximumSize(QSize(14, 16777215))
        self.stepReviewChevron.setStyleSheet(u"QLabel#stepReviewChevron {\n"
"    font-size: 9px;\n"
"    font-weight: bold;\n"
"    color: #64748b;\n"
"}")
        self.stepReviewChevron.setAlignment(Qt.AlignCenter)

        self.stepReviewHeaderLayout.addWidget(self.stepReviewChevron)


        self.stepReviewLayout.addWidget(self.stepReviewHeader)

        self.stepReviewBody = QWidget(self.stepReview)
        self.stepReviewBody.setObjectName(u"stepReviewBody")
        self.stepReviewBody.setStyleSheet(u"QWidget#stepReviewBody {\n"
"    border-top: 1px solid #f1f5f9;\n"
"    background: transparent;\n"
"}")
        self.stepReviewBodyLayout = QVBoxLayout(self.stepReviewBody)
        self.stepReviewBodyLayout.setSpacing(8)
        self.stepReviewBodyLayout.setObjectName(u"stepReviewBodyLayout")
        self.stepReviewBodyLayout.setContentsMargins(10, 8, 10, 10)
        self.label = QLabel(self.stepReviewBody)
        self.label.setObjectName(u"label")
        self.label.setStyleSheet(u"QLabel {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    line-height: 1.3;\n"
"}")
        self.label.setWordWrap(True)

        self.stepReviewBodyLayout.addWidget(self.label)

        self.reviewCountsLayout = QHBoxLayout()
        self.reviewCountsLayout.setSpacing(6)
        self.reviewCountsLayout.setObjectName(u"reviewCountsLayout")
        self.reviewStatAuto = QFrame(self.stepReviewBody)
        self.reviewStatAuto.setObjectName(u"reviewStatAuto")
        self.reviewStatAuto.setStyleSheet(u"QFrame#reviewStatAuto {\n"
"    background-color: #f0fdf4;\n"
"    border: 1px solid #bbf7d0;\n"
"    border-radius: 6px;\n"
"}")
        self.reviewStatAutoLayout = QVBoxLayout(self.reviewStatAuto)
        self.reviewStatAutoLayout.setSpacing(2)
        self.reviewStatAutoLayout.setObjectName(u"reviewStatAutoLayout")
        self.reviewStatAutoLayout.setContentsMargins(6, 6, 6, 6)
        self.reviewStatAutoTitle = QLabel(self.reviewStatAuto)
        self.reviewStatAutoTitle.setObjectName(u"reviewStatAutoTitle")
        self.reviewStatAutoTitle.setStyleSheet(u"QLabel#reviewStatAutoTitle {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #15803d;\n"
"}")

        self.reviewStatAutoLayout.addWidget(self.reviewStatAutoTitle)

        self.reviewStatAutoNum = QLabel(self.reviewStatAuto)
        self.reviewStatAutoNum.setObjectName(u"reviewStatAutoNum")
        self.reviewStatAutoNum.setStyleSheet(u"QLabel#reviewStatAutoNum {\n"
"    font-size: 17px;\n"
"    font-weight: bold;\n"
"    color: #166534;\n"
"}")

        self.reviewStatAutoLayout.addWidget(self.reviewStatAutoNum)


        self.reviewCountsLayout.addWidget(self.reviewStatAuto)

        self.reviewStatManual = QFrame(self.stepReviewBody)
        self.reviewStatManual.setObjectName(u"reviewStatManual")
        self.reviewStatManual.setStyleSheet(u"QFrame#reviewStatManual {\n"
"    background-color: #f0f9ff;\n"
"    border: 1px solid #bae6fd;\n"
"    border-radius: 6px;\n"
"}")
        self.reviewStatManualLayout = QVBoxLayout(self.reviewStatManual)
        self.reviewStatManualLayout.setSpacing(2)
        self.reviewStatManualLayout.setObjectName(u"reviewStatManualLayout")
        self.reviewStatManualLayout.setContentsMargins(6, 6, 6, 6)
        self.reviewStatManualTitle = QLabel(self.reviewStatManual)
        self.reviewStatManualTitle.setObjectName(u"reviewStatManualTitle")
        self.reviewStatManualTitle.setStyleSheet(u"QLabel#reviewStatManualTitle {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #0369a1;\n"
"}")

        self.reviewStatManualLayout.addWidget(self.reviewStatManualTitle)

        self.reviewStatManualNum = QLabel(self.reviewStatManual)
        self.reviewStatManualNum.setObjectName(u"reviewStatManualNum")
        self.reviewStatManualNum.setStyleSheet(u"QLabel#reviewStatManualNum {\n"
"    font-size: 17px;\n"
"    font-weight: bold;\n"
"    color: #0369a1;\n"
"}")

        self.reviewStatManualLayout.addWidget(self.reviewStatManualNum)


        self.reviewCountsLayout.addWidget(self.reviewStatManual)

        self.reviewStatDeleted = QFrame(self.stepReviewBody)
        self.reviewStatDeleted.setObjectName(u"reviewStatDeleted")
        self.reviewStatDeleted.setStyleSheet(u"QFrame#reviewStatDeleted {\n"
"    background-color: #fffbeb;\n"
"    border: 1px solid #fde68a;\n"
"    border-radius: 6px;\n"
"}")
        self.reviewStatDeletedLayout = QVBoxLayout(self.reviewStatDeleted)
        self.reviewStatDeletedLayout.setSpacing(2)
        self.reviewStatDeletedLayout.setObjectName(u"reviewStatDeletedLayout")
        self.reviewStatDeletedLayout.setContentsMargins(6, 6, 6, 6)
        self.reviewStatDeletedTitle = QLabel(self.reviewStatDeleted)
        self.reviewStatDeletedTitle.setObjectName(u"reviewStatDeletedTitle")
        self.reviewStatDeletedTitle.setStyleSheet(u"QLabel#reviewStatDeletedTitle {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #b45309;\n"
"}")

        self.reviewStatDeletedLayout.addWidget(self.reviewStatDeletedTitle)

        self.reviewStatDeletedNum = QLabel(self.reviewStatDeleted)
        self.reviewStatDeletedNum.setObjectName(u"reviewStatDeletedNum")
        self.reviewStatDeletedNum.setStyleSheet(u"QLabel#reviewStatDeletedNum {\n"
"    font-size: 17px;\n"
"    font-weight: bold;\n"
"    color: #92400e;\n"
"}")

        self.reviewStatDeletedLayout.addWidget(self.reviewStatDeletedNum)


        self.reviewCountsLayout.addWidget(self.reviewStatDeleted)


        self.stepReviewBodyLayout.addLayout(self.reviewCountsLayout)

        self.exportShowDeletedMasksLayout = QHBoxLayout()
        self.exportShowDeletedMasksLayout.setObjectName(u"exportShowDeletedMasksLayout")
        self.exportShowDeletedMasksLabel = QLabel(self.stepReviewBody)
        self.exportShowDeletedMasksLabel.setObjectName(u"exportShowDeletedMasksLabel")

        self.exportShowDeletedMasksLayout.addWidget(self.exportShowDeletedMasksLabel)

        self.exportShowDeletedMasks = QCheckBox(self.stepReviewBody)
        self.exportShowDeletedMasks.setObjectName(u"exportShowDeletedMasks")
        self.exportShowDeletedMasks.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.exportShowDeletedMasks.setStyleSheet(u"QCheckBox#exportShowDeletedMasks { spacing: 0px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"                        QCheckBox#exportShowDeletedMasks::indicator { width: 36px; height: 20px;  border: 1px solid #64748b; border-radius: 10px; }\n"
"                        QCheckBox#exportShowDeletedMasks::indicator:unchecked { image: url(:/startrails/ui/switch_off.png); }\n"
"                        QCheckBox#exportShowDeletedMasks::indicator:checked { image: url(:/startrails/ui/switch_on.png); }\n"
"QCheckBox#exportShowDeletedMasks:focus:enabled { border-color: #0f172a; }")

        self.exportShowDeletedMasksLayout.addWidget(self.exportShowDeletedMasks, 0, Qt.AlignRight)


        self.stepReviewBodyLayout.addLayout(self.exportShowDeletedMasksLayout)

        self.reviewSepFindBrightest = QFrame(self.stepReviewBody)
        self.reviewSepFindBrightest.setObjectName(u"reviewSepFindBrightest")
        self.reviewSepFindBrightest.setStyleSheet(u"QFrame[frameShape=\"4\"] {\n"
"    border-top: 1px solid #CCC;\n"
"}")
        self.reviewSepFindBrightest.setFrameShape(QFrame.HLine)

        self.stepReviewBodyLayout.addWidget(self.reviewSepFindBrightest)

        self.reviewFindBrightestHeading = QLabel(self.stepReviewBody)
        self.reviewFindBrightestHeading.setObjectName(u"reviewFindBrightestHeading")
        self.reviewFindBrightestHeading.setStyleSheet(u"QLabel#reviewFindBrightestHeading {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #475569;\n"
"    text-transform: uppercase;\n"
"    letter-spacing: 0.5px;\n"
"    margin-top: 2px;\n"
"}")

        self.stepReviewBodyLayout.addWidget(self.reviewFindBrightestHeading)

        self.reviewFindBrightestHint = QLabel(self.stepReviewBody)
        self.reviewFindBrightestHint.setObjectName(u"reviewFindBrightestHint")
        self.reviewFindBrightestHint.setStyleSheet(u"QLabel#reviewFindBrightestHint {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    line-height: 1.3;\n"
"}")
        self.reviewFindBrightestHint.setWordWrap(True)

        self.stepReviewBodyLayout.addWidget(self.reviewFindBrightestHint)

        self.findBrightest = QPushButton(self.stepReviewBody)
        self.findBrightest.setObjectName(u"findBrightest")
        self.findBrightest.setEnabled(False)
        self.findBrightest.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.findBrightest.setStyleSheet(u"QPushButton#findBrightest {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#findBrightest:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#findBrightest:checked {\n"
"    background-color: #e0f2fe;\n"
"    color: #0369a1;\n"
"    border-color: #0369a1;\n"
"    font-weight: 600;\n"
"}\n"
"QPushButton#findBrightest:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#findBrightest:focus:enabled { border-color: #0f172a; }")
        self.findBrightest.setCheckable(True)

        self.stepReviewBodyLayout.addWidget(self.findBrightest)

        self.reviewSep1 = QFrame(self.stepReviewBody)
        self.reviewSep1.setObjectName(u"reviewSep1")
        self.reviewSep1.setStyleSheet(u"QFrame[frameShape=\"4\"] {\n"
"    border-top: 1px solid #CCC;\n"
"}")
        self.reviewSep1.setFrameShape(QFrame.HLine)

        self.stepReviewBodyLayout.addWidget(self.reviewSep1)

        self.reviewContributeHeading = QLabel(self.stepReviewBody)
        self.reviewContributeHeading.setObjectName(u"reviewContributeHeading")
        self.reviewContributeHeading.setStyleSheet(u"QLabel#reviewContributeHeading {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #475569;\n"
"    text-transform: uppercase;\n"
"    letter-spacing: 0.5px;\n"
"    margin-top: 2px;\n"
"}")

        self.stepReviewBodyLayout.addWidget(self.reviewContributeHeading)

        self.reviewContributeHint = QLabel(self.stepReviewBody)
        self.reviewContributeHint.setObjectName(u"reviewContributeHint")
        self.reviewContributeHint.setStyleSheet(u"QLabel#reviewContributeHint {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    line-height: 1.3;\n"
"}")
        self.reviewContributeHint.setWordWrap(True)

        self.stepReviewBodyLayout.addWidget(self.reviewContributeHint)

        self.exportTraining = QPushButton(self.stepReviewBody)
        self.exportTraining.setObjectName(u"exportTraining")
        self.exportTraining.setEnabled(False)
        self.exportTraining.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.exportTraining.setStyleSheet(u"QPushButton#exportTraining {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 2px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#exportTraining:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#exportTraining:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#exportTraining:focus:enabled { border-color: #0f172a; }")

        self.stepReviewBodyLayout.addWidget(self.exportTraining)


        self.stepReviewLayout.addWidget(self.stepReviewBody)


        self.contentLayout.addWidget(self.stepReview)

        self.stepFill = QFrame(self.content)
        self.stepFill.setObjectName(u"stepFill")
        sizePolicy2.setHeightForWidth(self.stepFill.sizePolicy().hasHeightForWidth())
        self.stepFill.setSizePolicy(sizePolicy2)
        self.stepFill.setStyleSheet(u"QFrame#stepFill {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#stepFill:hover {\n"
"    border-color: #cbd5e1;\n"
"}")
        self.stepFillLayout = QVBoxLayout(self.stepFill)
        self.stepFillLayout.setSpacing(0)
        self.stepFillLayout.setObjectName(u"stepFillLayout")
        self.stepFillLayout.setContentsMargins(0, 0, 0, 0)
        self.stepFillHeader = QWidget(self.stepFill)
        self.stepFillHeader.setObjectName(u"stepFillHeader")
        sizePolicy3.setHeightForWidth(self.stepFillHeader.sizePolicy().hasHeightForWidth())
        self.stepFillHeader.setSizePolicy(sizePolicy3)
        self.stepFillHeader.setMaximumSize(QSize(16777215, 46))
        self.stepFillHeader.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepFillHeaderLayout = QHBoxLayout(self.stepFillHeader)
        self.stepFillHeaderLayout.setSpacing(8)
        self.stepFillHeaderLayout.setObjectName(u"stepFillHeaderLayout")
        self.stepFillHeaderLayout.setContentsMargins(8, 4, 8, 4)
        self.stepFillNumber = QLabel(self.stepFillHeader)
        self.stepFillNumber.setObjectName(u"stepFillNumber")
        self.stepFillNumber.setMinimumSize(QSize(30, 30))
        self.stepFillNumber.setMaximumSize(QSize(30, 30))
        self.stepFillNumber.setStyleSheet(u"QLabel#stepFillNumber {\n"
"                          background-color: #64748b;\n"
"                          color: #ffffff;\n"
"                          border: none;\n"
"                          border-radius: 15px;\n"
"                          font-weight: bold;\n"
"                          font-size: 13px;\n"
"                      }\n"
"                      QLabel#stepFillNumber[stepStatus=\"ready\"] { background-color: #0369a1; }\n"
"                      QLabel#stepFillNumber[stepStatus=\"done\"] { background-color: #1e293b; }\n"
"                      QLabel#stepFillNumber[stepStatus=\"running\"] { background-color: #b45309; }")
        self.stepFillNumber.setAlignment(Qt.AlignCenter)
        self.stepFillNumber.setProperty(u"stepStatus", u"locked")

        self.stepFillHeaderLayout.addWidget(self.stepFillNumber)

        self.stepFillTextColumn = QVBoxLayout()
        self.stepFillTextColumn.setSpacing(2)
        self.stepFillTextColumn.setObjectName(u"stepFillTextColumn")
        self.stepFillTextColumn.setContentsMargins(0, 0, 0, 0)
        self.stepFillToggle = QPushButton(self.stepFillHeader)
        self.stepFillToggle.setObjectName(u"stepFillToggle")
        sizePolicy5.setHeightForWidth(self.stepFillToggle.sizePolicy().hasHeightForWidth())
        self.stepFillToggle.setSizePolicy(sizePolicy5)
        self.stepFillToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.stepFillToggle.setStyleSheet(u"QPushButton#stepFillToggle {\n"
"    border: 2px solid transparent;\n"
"    background: transparent;\n"
"    text-align: left;\n"
"    padding: 0px;\n"
"    font-size: 13px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}\n"
"QPushButton#stepFillToggle:focus:enabled { border-color: #0f172a; }")
        self.stepFillToggle.setCheckable(True)
        self.stepFillToggle.setChecked(True)

        self.stepFillTextColumn.addWidget(self.stepFillToggle)

        self.stepFillSubtitle = QLabel(self.stepFillHeader)
        self.stepFillSubtitle.setObjectName(u"stepFillSubtitle")
        self.stepFillSubtitle.setStyleSheet(u"QLabel#stepFillSubtitle {\n"
"    font-size: 10px;\n"
"    color: #64748b;\n"
"}")
        self.stepFillSubtitle.setWordWrap(True)

        self.stepFillTextColumn.addWidget(self.stepFillSubtitle)


        self.stepFillHeaderLayout.addLayout(self.stepFillTextColumn)

        self.stepFillStatusBadge = QLabel(self.stepFillHeader)
        self.stepFillStatusBadge.setObjectName(u"stepFillStatusBadge")
        self.stepFillStatusBadge.setStyleSheet(u"QLabel#stepFillStatusBadge {\n"
"                          background-color: #e0f2fe;\n"
"                          color: #0369a1;\n"
"                          border-radius: 9px;\n"
"                          font-weight: 600;\n"
"                          font-size: 10px;\n"
"                          padding: 2px 8px;\n"
"                      }\n"
"                      QLabel#stepFillStatusBadge[stepStatus=\"done\"] { background-color: #dcfce7; color: #15803d; }\n"
"                      QLabel#stepFillStatusBadge[stepStatus=\"running\"] { background-color: #fef3c7; color: #b45309; }")
        self.stepFillStatusBadge.setAlignment(Qt.AlignCenter)
        self.stepFillStatusBadge.setProperty(u"stepStatus", u"locked")

        self.stepFillHeaderLayout.addWidget(self.stepFillStatusBadge)

        self.stepFillChevron = QLabel(self.stepFillHeader)
        self.stepFillChevron.setObjectName(u"stepFillChevron")
        self.stepFillChevron.setMinimumSize(QSize(14, 0))
        self.stepFillChevron.setMaximumSize(QSize(14, 16777215))
        self.stepFillChevron.setStyleSheet(u"QLabel#stepFillChevron {\n"
"    font-size: 9px;\n"
"    font-weight: bold;\n"
"    color: #64748b;\n"
"}")
        self.stepFillChevron.setAlignment(Qt.AlignCenter)

        self.stepFillHeaderLayout.addWidget(self.stepFillChevron)


        self.stepFillLayout.addWidget(self.stepFillHeader)

        self.stepFillBody = QWidget(self.stepFill)
        self.stepFillBody.setObjectName(u"stepFillBody")
        self.stepFillBody.setVisible(True)
        self.stepFillBody.setStyleSheet(u"QWidget#stepFillBody {\n"
"    border-top: 1px solid #f1f5f9;\n"
"    background: transparent;\n"
"}")
        self.stepFillBodyLayout = QVBoxLayout(self.stepFillBody)
        self.stepFillBodyLayout.setSpacing(8)
        self.stepFillBodyLayout.setObjectName(u"stepFillBodyLayout")
        self.stepFillBodyLayout.setContentsMargins(10, 8, 10, 10)
        self.fillTarget = QLabel(self.stepFillBody)
        self.fillTarget.setObjectName(u"fillTarget")
        self.fillTarget.setStyleSheet(u"QLabel#fillTarget {\n"
"    font-size: 12px;\n"
"    color: #475569;\n"
"}")
        self.fillTarget.setWordWrap(True)

        self.stepFillBodyLayout.addWidget(self.fillTarget)

        self.fillRun = QPushButton(self.stepFillBody)
        self.fillRun.setObjectName(u"fillRun")
        self.fillRun.setEnabled(False)
        self.fillRun.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.fillRun.setStyleSheet(u"QPushButton#fillRun {\n"
"    font-weight: bold;\n"
"    background-color: #0369a1;\n"
"    color: #ffffff;\n"
"    padding: 7px 12px;\n"
"    border-radius: 6px;\n"
"    font-size: 13px;\n"
"    border: 2px solid transparent;\n"
"}\n"
"QPushButton#fillRun:hover {\n"
"    background-color: #075985;\n"
"}\n"
"QPushButton#fillRun:disabled {\n"
"    background-color: #e2e8f0;\n"
"    color: #94a3b8;\n"
"}\n"
"QPushButton#fillRun:focus:enabled { border-color: #ffffff; }")

        self.stepFillBodyLayout.addWidget(self.fillRun)


        self.stepFillLayout.addWidget(self.stepFillBody)


        self.contentLayout.addWidget(self.stepFill)

        self.additionalTools = QFrame(self.content)
        self.additionalTools.setObjectName(u"additionalTools")
        sizePolicy2.setHeightForWidth(self.additionalTools.sizePolicy().hasHeightForWidth())
        self.additionalTools.setSizePolicy(sizePolicy2)
        self.additionalTools.setStyleSheet(u"QFrame#additionalTools {\n"
"                    background-color: #ffffff;\n"
"                    border: 1px solid #e2e8f0;\n"
"                    border-radius: 8px;\n"
"}\n"
"QFrame#additionalTools:hover {\n"
"                    border-color: #cbd5e1;\n"
"}")
        self.additionalToolsLayout = QVBoxLayout(self.additionalTools)
        self.additionalToolsLayout.setSpacing(0)
        self.additionalToolsLayout.setObjectName(u"additionalToolsLayout")
        self.additionalToolsLayout.setContentsMargins(0, 0, 0, 0)
        self.additionalToolsHeader = QWidget(self.additionalTools)
        self.additionalToolsHeader.setObjectName(u"additionalToolsHeader")
        sizePolicy3.setHeightForWidth(self.additionalToolsHeader.sizePolicy().hasHeightForWidth())
        self.additionalToolsHeader.setSizePolicy(sizePolicy3)
        self.additionalToolsHeader.setMaximumSize(QSize(16777215, 46))
        self.additionalToolsHeader.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.additionalToolsHeaderLayout = QHBoxLayout(self.additionalToolsHeader)
        self.additionalToolsHeaderLayout.setSpacing(8)
        self.additionalToolsHeaderLayout.setObjectName(u"additionalToolsHeaderLayout")
        self.additionalToolsHeaderLayout.setContentsMargins(8, 4, 8, 4)
        self.additionalToolsNumber = QLabel(self.additionalToolsHeader)
        self.additionalToolsNumber.setObjectName(u"additionalToolsNumber")
        self.additionalToolsNumber.setMinimumSize(QSize(30, 30))
        self.additionalToolsNumber.setMaximumSize(QSize(30, 30))
        self.additionalToolsNumber.setStyleSheet(u"QLabel#additionalToolsNumber {\n"
"                          background-color: #64748b;\n"
"                          color: #ffffff;\n"
"                          border: none;\n"
"                          border-radius: 15px;\n"
"                          font-weight: bold;\n"
"                          font-size: 13px;\n"
"                      }\n"
"                      QLabel#additionalToolsNumber[stepStatus=\"ready\"] { background-color: #0369a1; }\n"
"                      QLabel#additionalToolsNumber[stepStatus=\"done\"] { background-color: #1e293b; }\n"
"                      QLabel#additionalToolsNumber[stepStatus=\"running\"] { background-color: #b45309; }")
        self.additionalToolsNumber.setAlignment(Qt.AlignCenter)
        self.additionalToolsNumber.setProperty(u"stepStatus", u"neutral")

        self.additionalToolsHeaderLayout.addWidget(self.additionalToolsNumber)

        self.additionalToolsTextColumn = QVBoxLayout()
        self.additionalToolsTextColumn.setSpacing(2)
        self.additionalToolsTextColumn.setObjectName(u"additionalToolsTextColumn")
        self.additionalToolsTextColumn.setContentsMargins(0, 0, 0, 0)
        self.additionalToolsToggle = QPushButton(self.additionalToolsHeader)
        self.additionalToolsToggle.setObjectName(u"additionalToolsToggle")
        sizePolicy5.setHeightForWidth(self.additionalToolsToggle.sizePolicy().hasHeightForWidth())
        self.additionalToolsToggle.setSizePolicy(sizePolicy5)
        self.additionalToolsToggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.additionalToolsToggle.setStyleSheet(u"QPushButton#additionalToolsToggle {\n"
"                    border: 2px solid transparent;\n"
"                    background: transparent;\n"
"                    text-align: left;\n"
"                    padding: 0px;\n"
"                    font-size: 13px;\n"
"                    font-weight: bold;\n"
"                    color: #0f172a;\n"
"}\n"
"QPushButton#additionalToolsToggle:focus:enabled { border-color: #0f172a; }")
        self.additionalToolsToggle.setCheckable(True)
        self.additionalToolsToggle.setChecked(True)

        self.additionalToolsTextColumn.addWidget(self.additionalToolsToggle)

        self.additionalToolsSubtitle = QLabel(self.additionalToolsHeader)
        self.additionalToolsSubtitle.setObjectName(u"additionalToolsSubtitle")
        self.additionalToolsSubtitle.setStyleSheet(u"QLabel#additionalToolsSubtitle {\n"
"                    font-size: 10px;\n"
"                    color: #64748b;\n"
"}")
        self.additionalToolsSubtitle.setWordWrap(True)

        self.additionalToolsTextColumn.addWidget(self.additionalToolsSubtitle)


        self.additionalToolsHeaderLayout.addLayout(self.additionalToolsTextColumn)

        self.additionalToolsStatusBadge = QLabel(self.additionalToolsHeader)
        self.additionalToolsStatusBadge.setObjectName(u"additionalToolsStatusBadge")
        self.additionalToolsStatusBadge.setVisible(False)
        self.additionalToolsStatusBadge.setStyleSheet(u"QLabel#additionalToolsStatusBadge {\n"
"                          background-color: #e0f2fe;\n"
"                          color: #0369a1;\n"
"                          border-radius: 9px;\n"
"                          font-weight: 600;\n"
"                          font-size: 10px;\n"
"                          padding: 2px 8px;\n"
"                      }\n"
"                      QLabel#additionalToolsStatusBadge[stepStatus=\"done\"] { background-color: #dcfce7; color: #15803d; }\n"
"                      QLabel#additionalToolsStatusBadge[stepStatus=\"running\"] { background-color: #fef3c7; color: #b45309; }")
        self.additionalToolsStatusBadge.setAlignment(Qt.AlignCenter)
        self.additionalToolsStatusBadge.setProperty(u"stepStatus", u"neutral")

        self.additionalToolsHeaderLayout.addWidget(self.additionalToolsStatusBadge)

        self.additionalToolsChevron = QLabel(self.additionalToolsHeader)
        self.additionalToolsChevron.setObjectName(u"additionalToolsChevron")
        self.additionalToolsChevron.setMinimumSize(QSize(14, 0))
        self.additionalToolsChevron.setMaximumSize(QSize(14, 16777215))
        self.additionalToolsChevron.setStyleSheet(u"QLabel#additionalToolsChevron {\n"
"                    font-size: 9px;\n"
"                    font-weight: bold;\n"
"                    color: #64748b;\n"
"}")
        self.additionalToolsChevron.setAlignment(Qt.AlignCenter)

        self.additionalToolsHeaderLayout.addWidget(self.additionalToolsChevron)


        self.additionalToolsLayout.addWidget(self.additionalToolsHeader)

        self.additionalToolsBody = QWidget(self.additionalTools)
        self.additionalToolsBody.setObjectName(u"additionalToolsBody")
        self.additionalToolsBody.setVisible(True)
        self.additionalToolsBody.setStyleSheet(u"QWidget#additionalToolsBody {\n"
"                    border-top: 1px solid #f1f5f9;\n"
"                    background: transparent;\n"
"}")
        self.additionalToolsBodyLayout = QVBoxLayout(self.additionalToolsBody)
        self.additionalToolsBodyLayout.setSpacing(8)
        self.additionalToolsBodyLayout.setObjectName(u"additionalToolsBodyLayout")
        self.additionalToolsBodyLayout.setContentsMargins(10, 8, 10, 10)
        self.toolsMasksHeading = QLabel(self.additionalToolsBody)
        self.toolsMasksHeading.setObjectName(u"toolsMasksHeading")
        self.toolsMasksHeading.setStyleSheet(u"QLabel#toolsMasksHeading {\n"
"                    font-size: 11px;\n"
"                    font-weight: 600;\n"
"                    color: #475569;\n"
"                    text-transform: uppercase;\n"
"                    letter-spacing: 0.5px;\n"
"                    margin-top: 2px;\n"
"}")

        self.additionalToolsBodyLayout.addWidget(self.toolsMasksHeading)

        self.toolsMasksHint = QLabel(self.additionalToolsBody)
        self.toolsMasksHint.setObjectName(u"toolsMasksHint")
        self.toolsMasksHint.setStyleSheet(u"QLabel#toolsMasksHint {\n"
"                    font-size: 11px;\n"
"                    color: #64748b;\n"
"                    line-height: 1.3;\n"
"}")
        self.toolsMasksHint.setWordWrap(True)

        self.additionalToolsBodyLayout.addWidget(self.toolsMasksHint)

        self.exportMasks = QPushButton(self.additionalToolsBody)
        self.exportMasks.setObjectName(u"exportMasks")
        self.exportMasks.setEnabled(False)
        self.exportMasks.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.exportMasks.setStyleSheet(u"QPushButton#exportMasks {\n"
"                    background-color: #ffffff;\n"
"                    color: #1e293b;\n"
"                    border: 2px solid #cbd5e1;\n"
"                    border-radius: 6px;\n"
"                    padding: 6px 12px;\n"
"                    font-weight: 500;\n"
"                    font-size: 12px;\n"
"}\n"
"QPushButton#exportMasks:hover {\n"
"                    background-color: #f1f5f9;\n"
"                    border-color: #94a3b8;\n"
"}\n"
"QPushButton#exportMasks:disabled {\n"
"                    background-color: #f8fafc;\n"
"                    color: #94a3b8;\n"
"                    border-color: #e2e8f0;\n"
"}\n"
"QPushButton#exportMasks:focus:enabled { border-color: #0f172a; }")

        self.additionalToolsBodyLayout.addWidget(self.exportMasks)


        self.additionalToolsLayout.addWidget(self.additionalToolsBody)


        self.contentLayout.addWidget(self.additionalTools)

        self.bottomSpace = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.contentLayout.addItem(self.bottomSpace)

        self.scroll.setWidget(self.content)

        self.sidebarLayout.addWidget(self.scroll)

        self.bodySplitter.addWidget(self.sidebar)
        self.canvasHost = QWidget(self.bodySplitter)
        self.canvasHost.setObjectName(u"canvasHost")
        self.canvasHost.setStyleSheet(u"QWidget#canvasHost {\n"
"    background-color: #0f172a;\n"
"}")
        self.canvasLayout = QVBoxLayout(self.canvasHost)
        self.canvasLayout.setObjectName(u"canvasLayout")
        self.canvasLayout.setContentsMargins(0, 0, 0, 0)
        self.canvas_main = QLabel(self.canvasHost)
        self.canvas_main.setObjectName(u"canvas_main")
        sizePolicy7 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        sizePolicy7.setHorizontalStretch(1)
        sizePolicy7.setVerticalStretch(1)
        sizePolicy7.setHeightForWidth(self.canvas_main.sizePolicy().hasHeightForWidth())
        self.canvas_main.setSizePolicy(sizePolicy7)
        self.canvas_main.setMinimumSize(QSize(200, 160))
        self.canvas_main.setStyleSheet(u"QLabel#canvas_main {\n"
"    background-color: #0f172a;\n"
"}")

        self.canvasLayout.addWidget(self.canvas_main)

        self.bodySplitter.addWidget(self.canvasHost)

        self.verticalLayout_5.addWidget(self.bodySplitter)


        self.horizontalLayout_5.addWidget(self.vframe)

        MainWindow.setCentralWidget(self.centralwidget)
#if QT_CONFIG(shortcut)
        self.detectConfidenceLabel.setBuddy(self.detectConfidence)
        self.detectThresholdLabel.setBuddy(self.detectMergeThreshold)
        self.detectUseGPULabel.setBuddy(self.detectUseGPU)
        self.stackAmountLabel.setBuddy(self.stackFadeAmount)
        self.stackUseGPULabel.setBuddy(self.stackUseGPU)
        self.stackBatchLabel.setBuddy(self.stackBatchSize)
        self.exportShowDeletedMasksLabel.setBuddy(self.exportShowDeletedMasks)
#endif // QT_CONFIG(shortcut)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"StarTrails AI", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"StarTrails AI", None))
        self.label_imageName.setText("")
        self.label_gpu.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.projectTitle.setText(QCoreApplication.translate("MainWindow", u"Project Images", None))
        self.newProject.setText(QCoreApplication.translate("MainWindow", u"New Project", None))
        self.openProject.setText(QCoreApplication.translate("MainWindow", u"Open Project", None))
        self.inputFilesChevron.setText(QCoreApplication.translate("MainWindow", u"\u25bc", None))
        self.inputFilesToggle.setText(QCoreApplication.translate("MainWindow", u"Input Files", None))
        self.inputFilesCount.setText(QCoreApplication.translate("MainWindow", u"0", None))
#if QT_CONFIG(tooltip)
        self.inputFilesAdd.setToolTip(QCoreApplication.translate("MainWindow", u"Add files\u2026", None))
#endif // QT_CONFIG(tooltip)
        self.inputFilesAdd.setText(QCoreApplication.translate("MainWindow", u"+", None))
        self.inputFilesEmpty.setText(QCoreApplication.translate("MainWindow", u"No files yet.", None))
        self.inputFilesLegendAuto.setText(QCoreApplication.translate("MainWindow", u"A: Auto", None))
        self.inputFilesLegendManual.setText(QCoreApplication.translate("MainWindow", u"M: Manual", None))
        self.inputFilesLegendDeleted.setText(QCoreApplication.translate("MainWindow", u"D: Deleted", None))
        self.outputFilesChevron.setText(QCoreApplication.translate("MainWindow", u"\u25b6", None))
        self.outputFilesToggle.setText(QCoreApplication.translate("MainWindow", u"Output Files", None))
        self.outputFilesCount.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.outputFilesAdd.setText(QCoreApplication.translate("MainWindow", u"+", None))
        self.outputFilesEmpty.setText(QCoreApplication.translate("MainWindow", u"Stacked and processed outputs will appear here.", None))
        self.operationsTitle.setText(QCoreApplication.translate("MainWindow", u"Operations", None))
        self.operationsProgressLabel.setText(QCoreApplication.translate("MainWindow", u"0 of 4 steps complete", None))
        self.stepDetectNumber.setText(QCoreApplication.translate("MainWindow", u"1", None))
        self.stepDetectToggle.setText(QCoreApplication.translate("MainWindow", u"Detect Streaks", None))
        self.stepDetectSubtitle.setText(QCoreApplication.translate("MainWindow", u"Ready to detect streaks", None))
        self.stepDetectStatusBadge.setText(QCoreApplication.translate("MainWindow", u"\u2713 Ready", None))
        self.stepDetectChevron.setText(QCoreApplication.translate("MainWindow", u"\u25bc", None))
        self.detectConfidenceLabel.setText(QCoreApplication.translate("MainWindow", u"Confidence", None))
#if QT_CONFIG(accessibility)
        self.detectConfidence.setAccessibleName(QCoreApplication.translate("MainWindow", u"Confidence threshold", None))
#endif // QT_CONFIG(accessibility)
        self.detectMergeLabel.setText(QCoreApplication.translate("MainWindow", u"Merging", None))
        self.detectMergeNMS.setText(QCoreApplication.translate("MainWindow", u"NMS", None))
        self.detectMergeNMM.setText(QCoreApplication.translate("MainWindow", u"Greedy NMM", None))
        self.detectThresholdLabel.setText(QCoreApplication.translate("MainWindow", u"Threshold", None))
#if QT_CONFIG(accessibility)
        self.detectMergeThreshold.setAccessibleName(QCoreApplication.translate("MainWindow", u"Merge threshold", None))
#endif // QT_CONFIG(accessibility)
        self.detectUseGPULabel.setText(QCoreApplication.translate("MainWindow", u"Use GPU", None))
#if QT_CONFIG(accessibility)
        self.detectUseGPU.setAccessibleName(QCoreApplication.translate("MainWindow", u"Use GPU for detection", None))
#endif // QT_CONFIG(accessibility)
        self.detectUseGPU.setText("")
        self.detectError.setText("")
        self.detectRun.setText(QCoreApplication.translate("MainWindow", u"Detect Streaks", None))
        self.stepStackNumber.setText(QCoreApplication.translate("MainWindow", u"2", None))
        self.stepStackToggle.setText(QCoreApplication.translate("MainWindow", u"Stack Images", None))
        self.stepStackSubtitle.setText(QCoreApplication.translate("MainWindow", u"Ready \u00b7 detection is optional", None))
        self.stepStackStatusBadge.setText(QCoreApplication.translate("MainWindow", u"\u2713 Ready", None))
        self.stepStackChevron.setText(QCoreApplication.translate("MainWindow", u"\u25bc", None))
        self.stackMethodLabel.setText(QCoreApplication.translate("MainWindow", u"Method", None))
        self.stackMethod.setText(QCoreApplication.translate("MainWindow", u"Lighten", None))
        self.stackStreaksLabel.setText(QCoreApplication.translate("MainWindow", u"Streaks", None))
        self.stackStreaksKeep.setText(QCoreApplication.translate("MainWindow", u"Keep", None))
        self.stackStreaksRemove.setText(QCoreApplication.translate("MainWindow", u"Remove", None))
        self.stackFadeLabel.setText(QCoreApplication.translate("MainWindow", u"Fade frames", None))
        self.stackFadeOff.setText(QCoreApplication.translate("MainWindow", u"Off", None))
        self.stackFadeStart.setText(QCoreApplication.translate("MainWindow", u"Start", None))
        self.stackFadeEnd.setText(QCoreApplication.translate("MainWindow", u"End", None))
        self.stackFadeBoth.setText(QCoreApplication.translate("MainWindow", u"Both", None))
        self.stackAmountLabel.setText(QCoreApplication.translate("MainWindow", u"Amount", None))
#if QT_CONFIG(accessibility)
        self.stackFadeAmount.setAccessibleName(QCoreApplication.translate("MainWindow", u"Fade amount", None))
#endif // QT_CONFIG(accessibility)
        self.stackFadeAmount.setSuffix(QCoreApplication.translate("MainWindow", u"%", None))
        self.stackUseGPULabel.setText(QCoreApplication.translate("MainWindow", u"Use GPU", None))
#if QT_CONFIG(accessibility)
        self.stackUseGPU.setAccessibleName(QCoreApplication.translate("MainWindow", u"Use GPU for stacking", None))
#endif // QT_CONFIG(accessibility)
        self.stackUseGPU.setText("")
        self.stackBatchLabel.setText(QCoreApplication.translate("MainWindow", u"Batch size", None))
#if QT_CONFIG(accessibility)
        self.stackBatchSize.setAccessibleName(QCoreApplication.translate("MainWindow", u"Batch size", None))
#endif // QT_CONFIG(accessibility)
        self.stackMemory.setText(QCoreApplication.translate("MainWindow", u"Add input files for a batch suggestion.", None))
        self.stackError.setText("")
        self.stackRun.setText(QCoreApplication.translate("MainWindow", u"Stack Images", None))
        self.stepReviewNumber.setText(QCoreApplication.translate("MainWindow", u"3", None))
        self.stepReviewToggle.setText(QCoreApplication.translate("MainWindow", u"Review and Correct", None))
        self.stepReviewSubtitle.setText(QCoreApplication.translate("MainWindow", u"0 corrections", None))
        self.stepReviewStatusBadge.setText(QCoreApplication.translate("MainWindow", u"Ready", None))
        self.stepReviewChevron.setText(QCoreApplication.translate("MainWindow", u"\u25bc", None))
        self.label.setText(QCoreApplication.translate("MainWindow", u"You can review and edit detected streaks. If you manually add, edit, or delete masks, consider contributing your corrections so that models may be improved.", None))
        self.reviewStatAutoTitle.setText(QCoreApplication.translate("MainWindow", u"A: Auto", None))
        self.reviewStatAutoNum.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.reviewStatManualTitle.setText(QCoreApplication.translate("MainWindow", u"M: Manual", None))
        self.reviewStatManualNum.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.reviewStatDeletedTitle.setText(QCoreApplication.translate("MainWindow", u"D: Deleted", None))
        self.reviewStatDeletedNum.setText(QCoreApplication.translate("MainWindow", u"0", None))
        self.exportShowDeletedMasksLabel.setStyleSheet(QCoreApplication.translate("MainWindow", u"color: #334155; font-size: 12px;", None))
        self.exportShowDeletedMasksLabel.setText(QCoreApplication.translate("MainWindow", u"Show Deleted Masks", None))
#if QT_CONFIG(accessibility)
        self.exportShowDeletedMasks.setAccessibleName(QCoreApplication.translate("MainWindow", u"Show Deleted Masks", None))
#endif // QT_CONFIG(accessibility)
        self.exportShowDeletedMasks.setText("")
        self.reviewFindBrightestHeading.setText(QCoreApplication.translate("MainWindow", u"Locate Streaks", None))
        self.reviewFindBrightestHint.setText(QCoreApplication.translate("MainWindow", u"Click on a streak in a stacked or gap-filled image to locate its source frame.", None))
#if QT_CONFIG(tooltip)
        self.findBrightest.setToolTip(QCoreApplication.translate("MainWindow", u"Select a stacked or gap-filled output image to enable finding the brightest frame at a point.", None))
#endif // QT_CONFIG(tooltip)
        self.findBrightest.setText(QCoreApplication.translate("MainWindow", u"Find Brightest", None))
        self.reviewContributeHeading.setText(QCoreApplication.translate("MainWindow", u"Optional: Contribute Corrections", None))
        self.reviewContributeHint.setText(QCoreApplication.translate("MainWindow", u"Export manual additions and deletions to help improve future streak detection models.", None))
#if QT_CONFIG(tooltip)
        self.exportTraining.setToolTip(QCoreApplication.translate("MainWindow", u"Requires manually added or deleted streak masks.", None))
#endif // QT_CONFIG(tooltip)
        self.exportTraining.setText(QCoreApplication.translate("MainWindow", u"Export Training", None))
        self.stepFillNumber.setText(QCoreApplication.translate("MainWindow", u"4", None))
        self.stepFillToggle.setText(QCoreApplication.translate("MainWindow", u"Fill Gaps", None))
        self.stepFillSubtitle.setText(QCoreApplication.translate("MainWindow", u"Select a stacked output image", None))
        self.stepFillStatusBadge.setText(QCoreApplication.translate("MainWindow", u"Locked", None))
        self.stepFillChevron.setText(QCoreApplication.translate("MainWindow", u"\u25bc", None))
        self.fillTarget.setText(QCoreApplication.translate("MainWindow", u"Select a stacked output image to fill its gaps.", None))
        self.fillRun.setText(QCoreApplication.translate("MainWindow", u"Fill Gaps", None))
        self.additionalToolsNumber.setText("")
        self.additionalToolsToggle.setText(QCoreApplication.translate("MainWindow", u"Additional Tools", None))
        self.additionalToolsSubtitle.setText(QCoreApplication.translate("MainWindow", u"Optional utilities", None))
        self.additionalToolsStatusBadge.setText(QCoreApplication.translate("MainWindow", u"Locked", None))
        self.additionalToolsChevron.setText(QCoreApplication.translate("MainWindow", u"\u25bc", None))
        self.toolsMasksHeading.setText(QCoreApplication.translate("MainWindow", u"Export Masks", None))
        self.toolsMasksHint.setText(QCoreApplication.translate("MainWindow", u"Save detected streak masks as image files.", None))
#if QT_CONFIG(tooltip)
        self.exportMasks.setToolTip(QCoreApplication.translate("MainWindow", u"Requires automatic or manual streak masks.", None))
#endif // QT_CONFIG(tooltip)
        self.exportMasks.setText(QCoreApplication.translate("MainWindow", u"Export Masks", None))
        self.canvas_main.setText(QCoreApplication.translate("MainWindow", u"Canvas", None))
    # retranslateUi
