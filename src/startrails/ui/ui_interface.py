# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'interfaceYIXVEv.ui'
##
## Created by: Qt User Interface Compiler version 6.4.2
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
from PySide6.QtWidgets import (QAbstractScrollArea, QApplication, QFrame, QGridLayout,
    QHBoxLayout, QLabel, QLayout, QMainWindow,
    QProgressBar, QPushButton, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget)
import icons_rc

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(4095, 3938)
        MainWindow.setMinimumSize(QSize(300, 0))
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        sizePolicy = QSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.centralwidget.sizePolicy().hasHeightForWidth())
        self.centralwidget.setSizePolicy(sizePolicy)
        self.centralwidget.setStyleSheet(u"")
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
        sizePolicy1 = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.toolbar.sizePolicy().hasHeightForWidth())
        self.toolbar.setSizePolicy(sizePolicy1)
        self.toolbar.setMaximumSize(QSize(16777215, 40))
        self.toolbar.setFrameShape(QFrame.NoFrame)
        self.toolbar.setFrameShadow(QFrame.Raised)
        self.gridLayout = QGridLayout(self.toolbar)
        self.gridLayout.setObjectName(u"gridLayout")
        self.gridLayout.setHorizontalSpacing(0)
        self.gridLayout.setContentsMargins(0, 0, 6, 0)
        self.frame = QFrame(self.toolbar)
        self.frame.setObjectName(u"frame")
        sizePolicy1.setHeightForWidth(self.frame.sizePolicy().hasHeightForWidth())
        self.frame.setSizePolicy(sizePolicy1)
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
        sizePolicy1.setHeightForWidth(self.frame_2.sizePolicy().hasHeightForWidth())
        self.frame_2.setSizePolicy(sizePolicy1)
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

        self.horizontalLayout_11.addWidget(self.progressBar)


        self.gridLayout.addWidget(self.frame_2, 0, 2, 1, 1, Qt.AlignRight)

        self.frame_3 = QFrame(self.toolbar)
        self.frame_3.setObjectName(u"frame_3")
        sizePolicy1.setHeightForWidth(self.frame_3.sizePolicy().hasHeightForWidth())
        self.frame_3.setSizePolicy(sizePolicy1)
        self.frame_3.setFrameShape(QFrame.NoFrame)
        self.frame_3.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_10 = QHBoxLayout(self.frame_3)
        self.horizontalLayout_10.setObjectName(u"horizontalLayout_10")
        self.label_imageName = QLabel(self.frame_3)
        self.label_imageName.setObjectName(u"label_imageName")
        font1 = QFont()
        font1.setPointSize(14)
        self.label_imageName.setFont(font1)

        self.horizontalLayout_10.addWidget(self.label_imageName)


        self.gridLayout.addWidget(self.frame_3, 0, 1, 1, 1)

        self.frame_4 = QFrame(self.toolbar)
        self.frame_4.setObjectName(u"frame_4")
        self.frame_4.setMinimumSize(QSize(274, 0))
        self.frame_4.setMaximumSize(QSize(274, 16777215))
        self.frame_4.setFrameShape(QFrame.NoFrame)
        self.frame_4.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_7 = QHBoxLayout(self.frame_4)
        self.horizontalLayout_7.setSpacing(6)
        self.horizontalLayout_7.setObjectName(u"horizontalLayout_7")
        self.horizontalLayout_7.setContentsMargins(9, -1, 0, -1)
        self.label_cuda = QLabel(self.frame_4)
        self.label_cuda.setObjectName(u"label_cuda")

        self.horizontalLayout_7.addWidget(self.label_cuda)


        self.gridLayout.addWidget(self.frame_4, 0, 3, 1, 1)


        self.verticalLayout_5.addWidget(self.toolbar)

        self.frame_app = QFrame(self.vframe)
        self.frame_app.setObjectName(u"frame_app")
        self.frame_app.setFrameShape(QFrame.NoFrame)
        self.frame_app.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_6 = QHBoxLayout(self.frame_app)
        self.horizontalLayout_6.setSpacing(0)
        self.horizontalLayout_6.setObjectName(u"horizontalLayout_6")
        self.horizontalLayout_6.setContentsMargins(0, 0, 0, 0)
        self.frame_main = QFrame(self.frame_app)
        self.frame_main.setObjectName(u"frame_main")
        self.frame_main.setStyleSheet(u"background-color:gray;")
        self.frame_main.setFrameShape(QFrame.StyledPanel)
        self.frame_main.setFrameShadow(QFrame.Raised)
        self.verticalLayout = QVBoxLayout(self.frame_main)
        self.verticalLayout.setSpacing(0)
        self.verticalLayout.setObjectName(u"verticalLayout")
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.canvas_main = QLabel(self.frame_main)
        self.canvas_main.setObjectName(u"canvas_main")
        self.canvas_main.setMinimumSize(QSize(600, 600))
        font2 = QFont()
        font2.setPointSize(20)
        font2.setBold(True)
        self.canvas_main.setFont(font2)
        self.canvas_main.setAlignment(Qt.AlignCenter)

        self.verticalLayout.addWidget(self.canvas_main, 0, Qt.AlignHCenter|Qt.AlignVCenter)


        self.horizontalLayout_6.addWidget(self.frame_main)

        self.frame_right = QFrame(self.frame_app)
        self.frame_right.setObjectName(u"frame_right")
        self.frame_right.setMaximumSize(QSize(274, 16777215))
        self.frame_right.setFrameShape(QFrame.StyledPanel)
        self.frame_right.setFrameShadow(QFrame.Raised)
        self.verticalLayout_2 = QVBoxLayout(self.frame_right)
        self.verticalLayout_2.setSpacing(0)
        self.verticalLayout_2.setObjectName(u"verticalLayout_2")
        self.verticalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.slide_menu = QFrame(self.frame_right)
        self.slide_menu.setObjectName(u"slide_menu")
        self.slide_menu.setMinimumSize(QSize(274, 0))
        self.slide_menu.setMaximumSize(QSize(274, 16777215))
        self.slide_menu.setFrameShape(QFrame.NoFrame)
        self.slide_menu.setFrameShadow(QFrame.Raised)
        self.verticalLayout_3 = QVBoxLayout(self.slide_menu)
        self.verticalLayout_3.setSpacing(0)
        self.verticalLayout_3.setObjectName(u"verticalLayout_3")
        self.verticalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.frame_6 = QFrame(self.slide_menu)
        self.frame_6.setObjectName(u"frame_6")
        self.frame_6.setMaximumSize(QSize(16777215, 10))
        self.frame_6.setFrameShape(QFrame.NoFrame)
        self.frame_6.setFrameShadow(QFrame.Raised)
        self.verticalLayout_8 = QVBoxLayout(self.frame_6)
        self.verticalLayout_8.setObjectName(u"verticalLayout_8")

        self.verticalLayout_3.addWidget(self.frame_6)

        self.frame_operations = QFrame(self.slide_menu)
        self.frame_operations.setObjectName(u"frame_operations")
        font3 = QFont()
        font3.setBold(True)
        self.frame_operations.setFont(font3)
        self.frame_operations.setFrameShape(QFrame.NoFrame)
        self.frame_operations.setFrameShadow(QFrame.Raised)
        self.verticalLayout_4 = QVBoxLayout(self.frame_operations)
        self.verticalLayout_4.setSpacing(10)
        self.verticalLayout_4.setObjectName(u"verticalLayout_4")
        self.verticalLayout_4.setContentsMargins(8, 0, 8, 0)
        self.label_operations = QLabel(self.frame_operations)
        self.label_operations.setObjectName(u"label_operations")
        font4 = QFont()
        font4.setPointSize(14)
        font4.setBold(True)
        self.label_operations.setFont(font4)
        self.label_operations.setLineWidth(0)

        self.verticalLayout_4.addWidget(self.label_operations, 0, Qt.AlignTop)

        self.frame_5 = QFrame(self.frame_operations)
        self.frame_5.setObjectName(u"frame_5")
        self.frame_5.setFrameShape(QFrame.StyledPanel)
        self.frame_5.setFrameShadow(QFrame.Raised)
        self.gridLayout_2 = QGridLayout(self.frame_5)
        self.gridLayout_2.setSpacing(9)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.gridLayout_2.setContentsMargins(0, 0, 0, 0)
        self.pushButton_newProject = QPushButton(self.frame_5)
        self.pushButton_newProject.setObjectName(u"pushButton_newProject")
        self.pushButton_newProject.setMinimumSize(QSize(124, 110))
        self.pushButton_newProject.setMaximumSize(QSize(124, 110))
        font5 = QFont()
        font5.setPointSize(11)
        font5.setBold(False)
        self.pushButton_newProject.setFont(font5)
        self.pushButton_newProject.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/folder-plus.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")
        self.pushButton_newProject.setIconSize(QSize(120, 120))
        self.pushButton_newProject.setCheckable(False)
        self.pushButton_newProject.setChecked(False)

        self.gridLayout_2.addWidget(self.pushButton_newProject, 0, 0, 1, 1, Qt.AlignLeft|Qt.AlignBottom)

        self.pushButton_openProject = QPushButton(self.frame_5)
        self.pushButton_openProject.setObjectName(u"pushButton_openProject")
        self.pushButton_openProject.setMinimumSize(QSize(124, 110))
        self.pushButton_openProject.setMaximumSize(QSize(124, 110))
        font6 = QFont()
        font6.setBold(False)
        self.pushButton_openProject.setFont(font6)
        self.pushButton_openProject.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/folder.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")

        self.gridLayout_2.addWidget(self.pushButton_openProject, 0, 1, 1, 1)


        self.verticalLayout_4.addWidget(self.frame_5, 0, Qt.AlignLeft)

        self.line_3 = QFrame(self.frame_operations)
        self.line_3.setObjectName(u"line_3")
        self.line_3.setFrameShape(QFrame.HLine)
        self.line_3.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_4.addWidget(self.line_3)

        self.frame_7 = QFrame(self.frame_operations)
        self.frame_7.setObjectName(u"frame_7")
        self.frame_7.setFrameShape(QFrame.StyledPanel)
        self.frame_7.setFrameShadow(QFrame.Raised)
        self.gridLayout_4 = QGridLayout(self.frame_7)
        self.gridLayout_4.setSpacing(9)
        self.gridLayout_4.setObjectName(u"gridLayout_4")
        self.gridLayout_4.setContentsMargins(0, 0, 0, 0)
        self.pushButton_stackImages = QPushButton(self.frame_7)
        self.pushButton_stackImages.setObjectName(u"pushButton_stackImages")
        self.pushButton_stackImages.setEnabled(False)
        self.pushButton_stackImages.setMinimumSize(QSize(124, 110))
        self.pushButton_stackImages.setMaximumSize(QSize(124, 110))
        self.pushButton_stackImages.setFont(font5)
        self.pushButton_stackImages.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/layers.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")
        self.pushButton_stackImages.setIconSize(QSize(64, 64))

        self.gridLayout_4.addWidget(self.pushButton_stackImages, 0, 1, 1, 1)

        self.pushButton_selectFiles = QPushButton(self.frame_7)
        self.pushButton_selectFiles.setObjectName(u"pushButton_selectFiles")
        self.pushButton_selectFiles.setMinimumSize(QSize(124, 110))
        self.pushButton_selectFiles.setMaximumSize(QSize(124, 110))
        self.pushButton_selectFiles.setFont(font5)
        self.pushButton_selectFiles.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/star.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")

        self.gridLayout_4.addWidget(self.pushButton_selectFiles, 0, 0, 1, 1)


        self.verticalLayout_4.addWidget(self.frame_7, 0, Qt.AlignLeft)

        self.line = QFrame(self.frame_operations)
        self.line.setObjectName(u"line")
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_4.addWidget(self.line)

        self.frame_8 = QFrame(self.frame_operations)
        self.frame_8.setObjectName(u"frame_8")
        self.frame_8.setFrameShape(QFrame.StyledPanel)
        self.frame_8.setFrameShadow(QFrame.Raised)
        self.gridLayout_5 = QGridLayout(self.frame_8)
        self.gridLayout_5.setSpacing(9)
        self.gridLayout_5.setObjectName(u"gridLayout_5")
        self.gridLayout_5.setContentsMargins(0, 0, 0, 0)
        self.pushButton_removeStreaks = QPushButton(self.frame_8)
        self.pushButton_removeStreaks.setObjectName(u"pushButton_removeStreaks")
        self.pushButton_removeStreaks.setEnabled(False)
        self.pushButton_removeStreaks.setMinimumSize(QSize(124, 110))
        self.pushButton_removeStreaks.setMaximumSize(QSize(124, 110))
        self.pushButton_removeStreaks.setFont(font5)
        self.pushButton_removeStreaks.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/edit-3.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")

        self.gridLayout_5.addWidget(self.pushButton_removeStreaks, 0, 0, 1, 1)

        self.pushButton_exportMasks = QPushButton(self.frame_8)
        self.pushButton_exportMasks.setObjectName(u"pushButton_exportMasks")
        self.pushButton_exportMasks.setMinimumSize(QSize(124, 110))
        self.pushButton_exportMasks.setMaximumSize(QSize(124, 110))
        self.pushButton_exportMasks.setFont(font6)
        self.pushButton_exportMasks.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/external-link.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")

        self.gridLayout_5.addWidget(self.pushButton_exportMasks, 0, 1, 1, 1)

        self.pushButton_exportTraining = QPushButton(self.frame_8)
        self.pushButton_exportTraining.setObjectName(u"pushButton_exportTraining")
        self.pushButton_exportTraining.setMinimumSize(QSize(124, 110))
        self.pushButton_exportTraining.setMaximumSize(QSize(124, 110))
        self.pushButton_exportTraining.setFont(font6)
        self.pushButton_exportTraining.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/external-link.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")

        self.gridLayout_5.addWidget(self.pushButton_exportTraining, 1, 0, 1, 1)


        self.verticalLayout_4.addWidget(self.frame_8, 0, Qt.AlignLeft)

        self.line_2 = QFrame(self.frame_operations)
        self.line_2.setObjectName(u"line_2")
        self.line_2.setFrameShape(QFrame.HLine)
        self.line_2.setFrameShadow(QFrame.Sunken)

        self.verticalLayout_4.addWidget(self.line_2)

        self.frame_9 = QFrame(self.frame_operations)
        self.frame_9.setObjectName(u"frame_9")
        self.frame_9.setFrameShape(QFrame.StyledPanel)
        self.frame_9.setFrameShadow(QFrame.Raised)
        self.gridLayout_6 = QGridLayout(self.frame_9)
        self.gridLayout_6.setSpacing(9)
        self.gridLayout_6.setObjectName(u"gridLayout_6")
        self.gridLayout_6.setContentsMargins(0, 0, 0, 0)
        self.pushButton_fillGaps = QPushButton(self.frame_9)
        self.pushButton_fillGaps.setObjectName(u"pushButton_fillGaps")
        self.pushButton_fillGaps.setEnabled(False)
        self.pushButton_fillGaps.setMinimumSize(QSize(124, 110))
        self.pushButton_fillGaps.setMaximumSize(QSize(124, 110))
        self.pushButton_fillGaps.setFont(font5)
        self.pushButton_fillGaps.setStyleSheet(u"background-repeat: no-repeat;\n"
"background-position: center top;\n"
"background-image: url(:icons48/git-commit.svg);\n"
"text-align: bottom;\n"
"padding-top: 14px;\n"
"padding-bottom: 15px;\n"
"background-origin: content")

        self.gridLayout_6.addWidget(self.pushButton_fillGaps, 0, 0, 1, 1)


        self.verticalLayout_4.addWidget(self.frame_9, 0, Qt.AlignLeft)


        self.verticalLayout_3.addWidget(self.frame_operations, 0, Qt.AlignTop)


        self.verticalLayout_2.addWidget(self.slide_menu)


        self.horizontalLayout_6.addWidget(self.frame_right)


        self.verticalLayout_5.addWidget(self.frame_app)

        self.frame_bottom = QFrame(self.vframe)
        self.frame_bottom.setObjectName(u"frame_bottom")
        sizePolicy1.setHeightForWidth(self.frame_bottom.sizePolicy().hasHeightForWidth())
        self.frame_bottom.setSizePolicy(sizePolicy1)
        self.frame_bottom.setMinimumSize(QSize(0, 208))
        self.frame_bottom.setMaximumSize(QSize(16777215, 196))
        self.frame_bottom.setFrameShape(QFrame.NoFrame)
        self.frame_bottom.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_3 = QHBoxLayout(self.frame_bottom)
        self.horizontalLayout_3.setSpacing(5)
        self.horizontalLayout_3.setObjectName(u"horizontalLayout_3")
        self.horizontalLayout_3.setSizeConstraint(QLayout.SetNoConstraint)
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)
        self.frame_outputFilesContainer = QFrame(self.frame_bottom)
        self.frame_outputFilesContainer.setObjectName(u"frame_outputFilesContainer")
        sizePolicy1.setHeightForWidth(self.frame_outputFilesContainer.sizePolicy().hasHeightForWidth())
        self.frame_outputFilesContainer.setSizePolicy(sizePolicy1)
        self.frame_outputFilesContainer.setMinimumSize(QSize(160, 196))
        self.frame_outputFilesContainer.setFrameShape(QFrame.NoFrame)
        self.frame_outputFilesContainer.setFrameShadow(QFrame.Raised)
        self.verticalLayout_9 = QVBoxLayout(self.frame_outputFilesContainer)
        self.verticalLayout_9.setObjectName(u"verticalLayout_9")
        self.verticalLayout_9.setContentsMargins(6, 0, 6, 0)
        self.label_5 = QLabel(self.frame_outputFilesContainer)
        self.label_5.setObjectName(u"label_5")
        font7 = QFont()
        font7.setPointSize(12)
        font7.setBold(True)
        self.label_5.setFont(font7)

        self.verticalLayout_9.addWidget(self.label_5)

        self.scrollArea_2 = QScrollArea(self.frame_outputFilesContainer)
        self.scrollArea_2.setObjectName(u"scrollArea_2")
        sizePolicy2 = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        sizePolicy2.setHorizontalStretch(0)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.scrollArea_2.sizePolicy().hasHeightForWidth())
        self.scrollArea_2.setSizePolicy(sizePolicy2)
        self.scrollArea_2.setMinimumSize(QSize(158, 160))
        self.scrollArea_2.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea_2.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollArea_2.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.scrollArea_2.setWidgetResizable(True)
        self.frame_outputFiles_scroll = QWidget()
        self.frame_outputFiles_scroll.setObjectName(u"frame_outputFiles_scroll")
        self.frame_outputFiles_scroll.setGeometry(QRect(0, 0, 156, 144))
        sizePolicy1.setHeightForWidth(self.frame_outputFiles_scroll.sizePolicy().hasHeightForWidth())
        self.frame_outputFiles_scroll.setSizePolicy(sizePolicy1)
        self.horizontalLayout_8 = QHBoxLayout(self.frame_outputFiles_scroll)
        self.horizontalLayout_8.setSpacing(0)
        self.horizontalLayout_8.setObjectName(u"horizontalLayout_8")
        self.horizontalLayout_8.setContentsMargins(0, 0, 0, 0)
        self.frame_outputFiles = QFrame(self.frame_outputFiles_scroll)
        self.frame_outputFiles.setObjectName(u"frame_outputFiles")
        sizePolicy1.setHeightForWidth(self.frame_outputFiles.sizePolicy().hasHeightForWidth())
        self.frame_outputFiles.setSizePolicy(sizePolicy1)
        self.frame_outputFiles.setFrameShape(QFrame.NoFrame)
        self.frame_outputFiles.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_2 = QHBoxLayout(self.frame_outputFiles)
        self.horizontalLayout_2.setSpacing(5)
        self.horizontalLayout_2.setObjectName(u"horizontalLayout_2")
        self.horizontalLayout_2.setContentsMargins(0, 0, 0, 0)
        self.label_7 = QLabel(self.frame_outputFiles)
        self.label_7.setObjectName(u"label_7")

        self.horizontalLayout_2.addWidget(self.label_7)


        self.horizontalLayout_8.addWidget(self.frame_outputFiles)

        self.scrollArea_2.setWidget(self.frame_outputFiles_scroll)

        self.verticalLayout_9.addWidget(self.scrollArea_2)


        self.horizontalLayout_3.addWidget(self.frame_outputFilesContainer, 0, Qt.AlignLeft|Qt.AlignTop)

        self.frame_divider = QFrame(self.frame_bottom)
        self.frame_divider.setObjectName(u"frame_divider")
        self.frame_divider.setFrameShape(QFrame.VLine)
        self.frame_divider.setFrameShadow(QFrame.Raised)
        self.frame_divider.setLineWidth(1)

        self.horizontalLayout_3.addWidget(self.frame_divider)

        self.frame_inputFilesContainer = QFrame(self.frame_bottom)
        self.frame_inputFilesContainer.setObjectName(u"frame_inputFilesContainer")
        sizePolicy3 = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Preferred)
        sizePolicy3.setHorizontalStretch(100)
        sizePolicy3.setVerticalStretch(0)
        sizePolicy3.setHeightForWidth(self.frame_inputFilesContainer.sizePolicy().hasHeightForWidth())
        self.frame_inputFilesContainer.setSizePolicy(sizePolicy3)
        self.frame_inputFilesContainer.setMinimumSize(QSize(200, 196))
        self.frame_inputFilesContainer.setFrameShape(QFrame.NoFrame)
        self.frame_inputFilesContainer.setFrameShadow(QFrame.Raised)
        self.verticalLayout_6 = QVBoxLayout(self.frame_inputFilesContainer)
        self.verticalLayout_6.setSpacing(6)
        self.verticalLayout_6.setObjectName(u"verticalLayout_6")
        self.verticalLayout_6.setSizeConstraint(QLayout.SetDefaultConstraint)
        self.verticalLayout_6.setContentsMargins(6, 0, 6, 0)
        self.frame_10 = QFrame(self.frame_inputFilesContainer)
        self.frame_10.setObjectName(u"frame_10")
        self.frame_10.setFrameShape(QFrame.NoFrame)
        self.frame_10.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_12 = QHBoxLayout(self.frame_10)
        self.horizontalLayout_12.setObjectName(u"horizontalLayout_12")
        self.horizontalLayout_12.setContentsMargins(0, 0, 0, 0)
        self.label = QLabel(self.frame_10)
        self.label.setObjectName(u"label")
        self.label.setFont(font7)

        self.horizontalLayout_12.addWidget(self.label)


        self.verticalLayout_6.addWidget(self.frame_10)

        self.scrollArea = QScrollArea(self.frame_inputFilesContainer)
        self.scrollArea.setObjectName(u"scrollArea")
        sizePolicy4 = QSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        sizePolicy4.setHorizontalStretch(1)
        sizePolicy4.setVerticalStretch(0)
        sizePolicy4.setHeightForWidth(self.scrollArea.sizePolicy().hasHeightForWidth())
        self.scrollArea.setSizePolicy(sizePolicy4)
        self.scrollArea.setMinimumSize(QSize(300, 160))
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.scrollArea.setSizeAdjustPolicy(QAbstractScrollArea.AdjustToContents)
        self.scrollArea.setWidgetResizable(True)
        self.frame_inputFiles_scroll = QWidget()
        self.frame_inputFiles_scroll.setObjectName(u"frame_inputFiles_scroll")
        self.frame_inputFiles_scroll.setGeometry(QRect(0, 0, 3908, 144))
        sizePolicy1.setHeightForWidth(self.frame_inputFiles_scroll.sizePolicy().hasHeightForWidth())
        self.frame_inputFiles_scroll.setSizePolicy(sizePolicy1)
        self.horizontalLayout = QHBoxLayout(self.frame_inputFiles_scroll)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName(u"horizontalLayout")
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.frame_inputFiles = QFrame(self.frame_inputFiles_scroll)
        self.frame_inputFiles.setObjectName(u"frame_inputFiles")
        sizePolicy1.setHeightForWidth(self.frame_inputFiles.sizePolicy().hasHeightForWidth())
        self.frame_inputFiles.setSizePolicy(sizePolicy1)
        self.frame_inputFiles.setFrameShape(QFrame.NoFrame)
        self.frame_inputFiles.setFrameShadow(QFrame.Raised)
        self.horizontalLayout_4 = QHBoxLayout(self.frame_inputFiles)
        self.horizontalLayout_4.setSpacing(5)
        self.horizontalLayout_4.setObjectName(u"horizontalLayout_4")
        self.horizontalLayout_4.setContentsMargins(0, 0, 0, 0)
        self.label_2 = QLabel(self.frame_inputFiles)
        self.label_2.setObjectName(u"label_2")
        sizePolicy5 = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy5.setHorizontalStretch(0)
        sizePolicy5.setVerticalStretch(0)
        sizePolicy5.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy5)

        self.horizontalLayout_4.addWidget(self.label_2)


        self.horizontalLayout.addWidget(self.frame_inputFiles, 0, Qt.AlignLeft)

        self.scrollArea.setWidget(self.frame_inputFiles_scroll)

        self.verticalLayout_6.addWidget(self.scrollArea)


        self.horizontalLayout_3.addWidget(self.frame_inputFilesContainer, 0, Qt.AlignTop)

        self.horizontalLayout_3.setStretch(0, 1)

        self.verticalLayout_5.addWidget(self.frame_bottom)


        self.horizontalLayout_5.addWidget(self.vframe)

        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"StarStack AI", None))
        self.label_4.setText(QCoreApplication.translate("MainWindow", u"StarStack AI", None))
        self.label_progressBar.setText("")
        self.label_imageName.setText("")
        self.label_cuda.setText(QCoreApplication.translate("MainWindow", u"<GPU Stats>", None))
        self.canvas_main.setText(QCoreApplication.translate("MainWindow", u"TextLabel", None))
        self.label_operations.setText(QCoreApplication.translate("MainWindow", u"Operations", None))
        self.pushButton_newProject.setText(QCoreApplication.translate("MainWindow", u"New Project", None))
        self.pushButton_openProject.setText(QCoreApplication.translate("MainWindow", u"Open Project", None))
        self.pushButton_stackImages.setText(QCoreApplication.translate("MainWindow", u"Stack Images", None))
        self.pushButton_selectFiles.setText(QCoreApplication.translate("MainWindow", u"Add Star Frames", None))
        self.pushButton_removeStreaks.setText(QCoreApplication.translate("MainWindow", u"Detect Streaks", None))
        self.pushButton_exportMasks.setText(QCoreApplication.translate("MainWindow", u"Export Masks", None))
        self.pushButton_exportTraining.setText(QCoreApplication.translate("MainWindow", u"Export Training", None))
        self.pushButton_fillGaps.setText(QCoreApplication.translate("MainWindow", u"Fill Gaps", None))
        self.label_5.setText(QCoreApplication.translate("MainWindow", u"Output Files", None))
        self.label_7.setText("")
        self.label.setText(QCoreApplication.translate("MainWindow", u"Input Files", None))
        self.label_2.setText("")
    # retranslateUi

