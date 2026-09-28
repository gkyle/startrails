# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'progress_overlay.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QLabel,
    QProgressBar, QPushButton, QSizePolicy, QSpacerItem,
    QVBoxLayout, QWidget)

class Ui_ProgressOverlay(object):
    def setupUi(self, progressOverlay):
        if not progressOverlay.objectName():
            progressOverlay.setObjectName(u"progressOverlay")
        progressOverlay.resize(460, 120)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(progressOverlay.sizePolicy().hasHeightForWidth())
        progressOverlay.setSizePolicy(sizePolicy)
        progressOverlay.setMinimumSize(QSize(460, 120))
        progressOverlay.setMaximumSize(QSize(460, 120))
        progressOverlay.setStyleSheet(u"QFrame#progressOverlay {\n"
"    background-color: rgba(15, 23, 42, 0.94);\n"
"    border: 1px solid rgba(255, 255, 255, 0.12);\n"
"    border-radius: 12px;\n"
"}\n"
"QLabel {\n"
"    font-family: 'Segoe UI';\n"
"    background: transparent;\n"
"}\n"
"QLabel#label_progressTitle {\n"
"    color: #f8fafc;\n"
"    font-size: 14px;\n"
"    font-weight: 600;\n"
"}\n"
"QLabel#label_progressBar {\n"
"    color: #94a3b8;\n"
"    font-size: 11px;\n"
"}\n"
"QLabel#label_progressPercent {\n"
"    color: #f1f5f9;\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    min-width: 32px;\n"
"}\n"
"QLabel#label_progressElapsed, QLabel#label_progressETA {\n"
"    color: #94a3b8;\n"
"    font-size: 11px;\n"
"}\n"
"QProgressBar#progressBar {\n"
"    background-color: #334155;\n"
"    border: none;\n"
"    border-radius: 3px;\n"
"    max-height: 6px;\n"
"    min-height: 6px;\n"
"}\n"
"QProgressBar#progressBar::chunk {\n"
"    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #38bdf8);\n"
"    border-ra"
                        "dius: 3px;\n"
"}\n"
"QPushButton#pushButton_cancelOp {\n"
"    background-color: rgba(255, 255, 255, 0.05);\n"
"    border: 1px solid rgba(148, 163, 184, 0.25);\n"
"    border-radius: 6px;\n"
"    color: #f43f5e;\n"
"    font-weight: bold;\n"
"    font-size: 13px;\n"
"    min-width: 26px;\n"
"    max-width: 26px;\n"
"    min-height: 26px;\n"
"    max-height: 26px;\n"
"}\n"
"QPushButton#pushButton_cancelOp:hover {\n"
"    background-color: rgba(244, 63, 94, 0.15);\n"
"    border-color: #f43f5e;\n"
"    color: #ff4d6d;\n"
"}")
        progressOverlay.setFrameShape(QFrame.StyledPanel)
        self.mainLayout = QVBoxLayout(progressOverlay)
        self.mainLayout.setSpacing(10)
        self.mainLayout.setObjectName(u"mainLayout")
        self.mainLayout.setContentsMargins(18, 14, 18, 14)
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setSpacing(12)
        self.headerLayout.setObjectName(u"headerLayout")
        self.spinnerContainer = QWidget(progressOverlay)
        self.spinnerContainer.setObjectName(u"spinnerContainer")
        sizePolicy.setHeightForWidth(self.spinnerContainer.sizePolicy().hasHeightForWidth())
        self.spinnerContainer.setSizePolicy(sizePolicy)
        self.spinnerContainer.setMinimumSize(QSize(30, 30))
        self.spinnerContainer.setMaximumSize(QSize(30, 30))

        self.headerLayout.addWidget(self.spinnerContainer)

        self.titleLayout = QVBoxLayout()
        self.titleLayout.setSpacing(2)
        self.titleLayout.setObjectName(u"titleLayout")
        self.label_progressTitle = QLabel(progressOverlay)
        self.label_progressTitle.setObjectName(u"label_progressTitle")

        self.titleLayout.addWidget(self.label_progressTitle)

        self.label_progressBar = QLabel(progressOverlay)
        self.label_progressBar.setObjectName(u"label_progressBar")

        self.titleLayout.addWidget(self.label_progressBar)


        self.headerLayout.addLayout(self.titleLayout)

        self.pushButton_cancelOp = QPushButton(progressOverlay)
        self.pushButton_cancelOp.setObjectName(u"pushButton_cancelOp")
        self.pushButton_cancelOp.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.headerLayout.addWidget(self.pushButton_cancelOp)


        self.mainLayout.addLayout(self.headerLayout)

        self.barLayout = QHBoxLayout()
        self.barLayout.setSpacing(10)
        self.barLayout.setObjectName(u"barLayout")
        self.progressBar = QProgressBar(progressOverlay)
        self.progressBar.setObjectName(u"progressBar")
        self.progressBar.setValue(0)
        self.progressBar.setTextVisible(False)

        self.barLayout.addWidget(self.progressBar)

        self.label_progressPercent = QLabel(progressOverlay)
        self.label_progressPercent.setObjectName(u"label_progressPercent")
        self.label_progressPercent.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.barLayout.addWidget(self.label_progressPercent)


        self.mainLayout.addLayout(self.barLayout)

        self.footerLayout = QHBoxLayout()
        self.footerLayout.setSpacing(6)
        self.footerLayout.setObjectName(u"footerLayout")
        self.label_progressElapsed = QLabel(progressOverlay)
        self.label_progressElapsed.setObjectName(u"label_progressElapsed")

        self.footerLayout.addWidget(self.label_progressElapsed)

        self.footerSpacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        self.footerLayout.addItem(self.footerSpacer)

        self.label_progressETA = QLabel(progressOverlay)
        self.label_progressETA.setObjectName(u"label_progressETA")
        self.label_progressETA.setAlignment(Qt.AlignRight|Qt.AlignTrailing|Qt.AlignVCenter)

        self.footerLayout.addWidget(self.label_progressETA)


        self.mainLayout.addLayout(self.footerLayout)


        self.retranslateUi(progressOverlay)

        QMetaObject.connectSlotsByName(progressOverlay)
    # setupUi

    def retranslateUi(self, progressOverlay):
        self.label_progressTitle.setText(QCoreApplication.translate("ProgressOverlay", u"Stack Images", None))
        self.label_progressBar.setText(QCoreApplication.translate("ProgressOverlay", u"Processing frame 0 of 0", None))
        self.pushButton_cancelOp.setText(QCoreApplication.translate("ProgressOverlay", u"\u2715", None))
        self.label_progressPercent.setText(QCoreApplication.translate("ProgressOverlay", u"0%", None))
        self.label_progressElapsed.setText(QCoreApplication.translate("ProgressOverlay", u"Elapsed 00:00:00", None))
        self.label_progressETA.setText(QCoreApplication.translate("ProgressOverlay", u"ETA --:--:--", None))
        pass
    # retranslateUi
