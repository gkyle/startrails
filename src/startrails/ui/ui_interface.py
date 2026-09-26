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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLayout, QMainWindow,
    QProgressBar, QPushButton, QSizePolicy, QSplitter,
    QVBoxLayout, QWidget)

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(1600, 1200)
        MainWindow.setMinimumSize(QSize(300, 0))
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
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
        self.toolbar.setMaximumSize(QSize(16777215, 40))
        self.toolbar.setFrameShape(QFrame.NoFrame)
        self.toolbar.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.toolbar)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setHorizontalSpacing(0)
        self.gridLayout.setContentsMargins(0, 0, 6, 0)
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
        font.setPointSize(18)
        font.setBold(True)
        self.label_4.setFont(font)

        self.horizontalLayout_9.addWidget(self.label_4)


        self.gridLayout.addWidget(self.frame, 0, 0, 1, 1)

        self.frame_2 = QFrame(self.toolbar)
        self.frame_2.setObjectName(u"frame_2")
        sizePolicy.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy)
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_11 = QHBoxLayout(self.frame_2)
        self.horizontalLayout_11.setObjectName(u"horizontalLayout_11")
        self.horizontalLayout_11.setContentsMargins(-1, -1, 0, -1)
        self.label_progressBar = QLabel(self.frame_2)
        self.label_progressBar.setObjectName(u"label_progressBar")

        self.horizontalLayout_11.addWidget(self.label_progressBar)

        self.progressBar = QProgressBar(self.frame_2)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setMinimumSize(QSize(300, 0))
        self.progressBar.setMaximumSize(QSize(300, 16777215))
        self.progressBar.setValue(0)
        self.progressBar.setAlignment(Qt.AlignCenter)

        self.horizontalLayout_11.addWidget(self.progressBar)

        self.pushButton_cancelOp = QPushButton(self.frame_2)
        self.pushButton_cancelOp.setObjectName(u"pushButton_cancelOp")
        self.pushButton_cancelOp.setMinimumSize(QSize(30, 0))
        self.pushButton_cancelOp.setMaximumSize(QSize(30, 16777215))

        self.horizontalLayout_11.addWidget(self.pushButton_cancelOp)


        self.gridLayout.addWidget(self.frame_2, 0, 2, 1, 1, Qt.AlignRight)

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
        font1 = QFont()
        font1.setPointSize(13)
        self.label_imageName.setFont(font1)

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
        self.horizontalLayout_7.setContentsMargins(9, 5, 0, 5)
        self.frame_gpu = QFrame(self.frame_4)
        self.frame_gpu.setObjectName(u"frame_gpu")
        self.frame_gpu.setStyleSheet(u"")
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
        self.label_gpu = QLabel(self.frame_gpu_label)
        self.label_gpu.setObjectName(u"label_gpu")

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
        font2 = QFont()
        font2.setPointSize(8)
        self.progressBar_gpu_util.setFont(font2)
        self.progressBar_gpu_util.setStyleSheet(u"QProgressBar {\n"
"            border: 2px solid grey;\n"
"            border-radius: 5px;\n"
"        }\n"
"\n"
"        QProgressBar::chunk {\n"
"            background-color: green;\n"
"            width: 20px;\n"
"        }")
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
        self.progressBar_gpu_mem.setFont(font2)
        self.progressBar_gpu_mem.setStyleSheet(u"QProgressBar {\n"
"            border: 2px solid grey;\n"
"            border-radius: 5px;\n"
"        }\n"
"\n"
"        QProgressBar::chunk {\n"
"            background-color: green;\n"
"            width: 20px;\n"
"        }")
        self.progressBar_gpu_mem.setValue(0)
        self.progressBar_gpu_mem.setAlignment(Qt.AlignCenter)
        self.progressBar_gpu_mem.setTextVisible(True)
        self.progressBar_gpu_mem.setInvertedAppearance(False)

        self.horizontalLayout_18.addWidget(self.progressBar_gpu_mem)


        self.verticalLayout_15.addWidget(self.frame_gpu_mem)


        self.horizontalLayout_7.addWidget(self.frame_gpu)


        self.gridLayout.addWidget(self.frame_4, 0, 3, 1, 1)


        self.verticalLayout_5.addWidget(self.toolbar)

        self.bodySplitter = QSplitter(self.vframe)
        self.bodySplitter.setObjectName(u"bodySplitter")
        self.bodySplitter.setOrientation(Qt.Horizontal)
        self.bodySplitter.setChildrenCollapsible(False)
        self.sidebarHost = QWidget(self.bodySplitter)
        self.sidebarHost.setObjectName(u"sidebarHost")
        self.sidebarLayout = QVBoxLayout(self.sidebarHost)
        self.sidebarLayout.setObjectName(u"sidebarLayout")
        self.sidebarLayout.setContentsMargins(0, 0, 0, 0)
        self.bodySplitter.addWidget(self.sidebarHost)
        self.canvasHost = QWidget(self.bodySplitter)
        self.canvasHost.setObjectName(u"canvasHost")
        self.canvasLayout = QVBoxLayout(self.canvasHost)
        self.canvasLayout.setObjectName(u"canvasLayout")
        self.canvasLayout.setContentsMargins(0, 0, 0, 0)
        self.checkBox_showDeletedMasks = QCheckBox(self.canvasHost)
        self.checkBox_showDeletedMasks.setObjectName(u"checkBox_showDeletedMasks")

        self.canvasLayout.addWidget(self.checkBox_showDeletedMasks)

        self.canvas_main = QLabel(self.canvasHost)
        self.canvas_main.setObjectName(u"canvas_main")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        sizePolicy1.setHorizontalStretch(1)
        sizePolicy1.setVerticalStretch(1)
        sizePolicy1.setHeightForWidth(self.canvas_main.sizePolicy().hasHeightForWidth())
        self.canvas_main.setSizePolicy(sizePolicy1)
        self.canvas_main.setMinimumSize(QSize(200, 160))

        self.canvasLayout.addWidget(self.canvas_main)

        self.bodySplitter.addWidget(self.canvasHost)

        self.verticalLayout_5.addWidget(self.bodySplitter)


        self.horizontalLayout_5.addWidget(self.vframe)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"StarTrails AI", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"StarTrails AI", None))
        self.label_progressBar.setText("")
        self.pushButton_cancelOp.setText(QCoreApplication.translate("MainWindow", u"X", None))
        self.label_imageName.setText("")
        self.label_gpu.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.checkBox_showDeletedMasks.setText(QCoreApplication.translate("MainWindow", u"Show Deleted Masks", None))
        self.canvas_main.setText(QCoreApplication.translate("MainWindow", u"Canvas", None))
    # retranslateUi
