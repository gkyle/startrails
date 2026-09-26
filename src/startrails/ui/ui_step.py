# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step.ui'
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
    QPushButton, QSizePolicy, QVBoxLayout, QWidget)

class Ui_StepCard(object):
    def setupUi(self, stepCard):
        if not stepCard.objectName():
            stepCard.setObjectName(u"stepCard")
        stepCard.setStyleSheet(u"QFrame#stepCard {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#stepCard:hover {\n"
"    border-color: #cbd5e1;\n"
"}\n"
"QLabel#number {\n"
"    background-color: #0284c7;\n"
"    color: #ffffff;\n"
"    border-radius: 15px;\n"
"    font-weight: bold;\n"
"    font-size: 13px;\n"
"}\n"
"QPushButton#toggle {\n"
"    border: none;\n"
"    background: transparent;\n"
"    text-align: left;\n"
"    padding: 0px;\n"
"    font-size: 13px;\n"
"    font-weight: bold;\n"
"    color: #0f172a;\n"
"}\n"
"QLabel#subtitle {\n"
"    font-size: 10px;\n"
"    color: #64748b;\n"
"}\n"
"QLabel#statusBadge {\n"
"    background-color: #e0f2fe;\n"
"    color: #0284c7;\n"
"    border-radius: 9px;\n"
"    font-weight: 600;\n"
"    font-size: 10px;\n"
"    padding: 2px 8px;\n"
"    font-family: \"Segoe UI\", \"Segoe UI Symbol\", sans-serif;\n"
"}\n"
"QLabel#chevron {\n"
"    font-size: 9px;\n"
"    font-weight: bold;\n"
"    color: #64748b;\n"
"    font-family: \"Seg"
                        "oe UI\", \"Segoe UI Symbol\", sans-serif;\n"
"}\n"
"QWidget#body {\n"
"    border-top: 1px solid #f1f5f9;\n"
"    background: transparent;\n"
"}")
        self.cardLayout = QVBoxLayout(stepCard)
        self.cardLayout.setSpacing(0)
        self.cardLayout.setObjectName(u"cardLayout")
        self.cardLayout.setContentsMargins(0, 0, 0, 0)
        self.headerWidget = QWidget(stepCard)
        self.headerWidget.setObjectName(u"headerWidget")
        self.headerWidget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setSpacing(8)
        self.headerLayout.setObjectName(u"headerLayout")
        self.headerLayout.setContentsMargins(8, 8, 8, 8)
        self.number = QLabel(self.headerWidget)
        self.number.setObjectName(u"number")
        self.number.setMinimumSize(QSize(30, 30))
        self.number.setMaximumSize(QSize(30, 30))
        self.number.setAlignment(Qt.AlignCenter)

        self.headerLayout.addWidget(self.number)

        self.textColumn = QVBoxLayout()
        self.textColumn.setSpacing(2)
        self.textColumn.setObjectName(u"textColumn")
        self.textColumn.setContentsMargins(0, 0, 0, 0)
        self.toggle = QPushButton(self.headerWidget)
        self.toggle.setObjectName(u"toggle")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.toggle.sizePolicy().hasHeightForWidth())
        self.toggle.setSizePolicy(sizePolicy)
        self.toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle.setCheckable(True)

        self.textColumn.addWidget(self.toggle)

        self.subtitle = QLabel(self.headerWidget)
        self.subtitle.setObjectName(u"subtitle")
        self.subtitle.setWordWrap(True)

        self.textColumn.addWidget(self.subtitle)


        self.headerLayout.addLayout(self.textColumn)

        self.statusBadge = QLabel(self.headerWidget)
        self.statusBadge.setObjectName(u"statusBadge")
        self.statusBadge.setAlignment(Qt.AlignCenter)

        self.headerLayout.addWidget(self.statusBadge)

        self.chevron = QLabel(self.headerWidget)
        self.chevron.setObjectName(u"chevron")
        self.chevron.setMinimumSize(QSize(14, 0))
        self.chevron.setMaximumSize(QSize(14, 16777215))
        self.chevron.setAlignment(Qt.AlignCenter)

        self.headerLayout.addWidget(self.chevron)


        self.cardLayout.addWidget(self.headerWidget)

        self.body = QWidget(stepCard)
        self.body.setObjectName(u"body")
        self.contentLayout = QVBoxLayout(self.body)
        self.contentLayout.setSpacing(6)
        self.contentLayout.setObjectName(u"contentLayout")
        self.contentLayout.setContentsMargins(10, 8, 10, 10)

        self.cardLayout.addWidget(self.body)


        self.retranslateUi(stepCard)

        QMetaObject.connectSlotsByName(stepCard)
    # setupUi

    def retranslateUi(self, stepCard):
        self.number.setText(QCoreApplication.translate("StepCard", u"1", None))
        self.toggle.setText(QCoreApplication.translate("StepCard", u"Step Title", None))
        self.subtitle.setText(QCoreApplication.translate("StepCard", u"Ready", None))
        self.statusBadge.setText(QCoreApplication.translate("StepCard", u"\u2713 Ready", None))
        self.chevron.setText(QCoreApplication.translate("StepCard", u"\u25b6", None))
        pass
    # retranslateUi
