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
    def setupUi(self, StepCard):
        if not StepCard.objectName():
            StepCard.setObjectName(u"StepCard")
        StepCard.resize(208, 75)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(StepCard.sizePolicy().hasHeightForWidth())
        StepCard.setSizePolicy(sizePolicy)
        StepCard.setStyleSheet(u"QFrame#stepCard {\n"
"    background-color: #ffffff;\n"
"    border: 1px solid #e2e8f0;\n"
"    border-radius: 8px;\n"
"}\n"
"QFrame#stepCard:hover {\n"
"    border-color: #cbd5e1;\n"
"}\n"
"QPushButton#toggle {\n"
"    border: 2px solid transparent;\n"
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
"QLabel#chevron {\n"
"    min-width: 14px;\n"
"    max-width: 14px;\n"
"    image: url(:/startrails/ui/chevron_down.svg);\n"
"}\n"
"QLabel#chevron[expanded=\"false\"] {\n"
"    image: url(:/startrails/ui/chevron_right.svg);\n"
"}\n"
"QWidget#body {\n"
"    border-top: 1px solid #f1f5f9;\n"
"    background: transparent;\n"
"}\n"
"QPushButton#toggle:focus:enabled { border-color: #0f172a; }")
        self.cardLayout = QVBoxLayout(StepCard)
        self.cardLayout.setSpacing(0)
        self.cardLayout.setObjectName(u"cardLayout")
        self.cardLayout.setContentsMargins(0, 0, 0, 0)
        self.headerWidget = QWidget(StepCard)
        self.headerWidget.setObjectName(u"headerWidget")
        sizePolicy1 = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy1.setHorizontalStretch(0)
        sizePolicy1.setVerticalStretch(0)
        sizePolicy1.setHeightForWidth(self.headerWidget.sizePolicy().hasHeightForWidth())
        self.headerWidget.setSizePolicy(sizePolicy1)
        self.headerWidget.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.headerLayout = QHBoxLayout(self.headerWidget)
        self.headerLayout.setSpacing(8)
        self.headerLayout.setObjectName(u"headerLayout")
        self.headerLayout.setContentsMargins(8, 8, 8, 8)
        self.number = QLabel(self.headerWidget)
        self.number.setObjectName(u"number")
        self.number.setMinimumSize(QSize(30, 30))
        self.number.setMaximumSize(QSize(30, 30))
        self.number.setStyleSheet(u"QLabel#number {\n"
"           background-color: #64748b;\n"
"           color: #ffffff;\n"
"           border: none;\n"
"           border-radius: 15px;\n"
"           font-weight: bold;\n"
"           font-size: 13px;\n"
"       }\n"
"       QLabel#number[stepStatus=\"ready\"] { background-color: #0369a1; }\n"
"       QLabel#number[stepStatus=\"done\"] { background-color: #1e293b; }\n"
"       QLabel#number[stepStatus=\"running\"] { background-color: #b45309; }")
        self.number.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number.setProperty(u"stepStatus", u"ready")

        self.headerLayout.addWidget(self.number)

        self.textColumn = QVBoxLayout()
        self.textColumn.setSpacing(2)
        self.textColumn.setObjectName(u"textColumn")
        self.textColumn.setContentsMargins(0, 0, 0, 0)
        self.toggle = QPushButton(self.headerWidget)
        self.toggle.setObjectName(u"toggle")
        sizePolicy2 = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy2.setHorizontalStretch(1)
        sizePolicy2.setVerticalStretch(0)
        sizePolicy2.setHeightForWidth(self.toggle.sizePolicy().hasHeightForWidth())
        self.toggle.setSizePolicy(sizePolicy2)
        self.toggle.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle.setCheckable(True)
        self.toggle.setChecked(True)

        self.textColumn.addWidget(self.toggle)

        self.subtitle = QLabel(self.headerWidget)
        self.subtitle.setObjectName(u"subtitle")
        self.subtitle.setWordWrap(True)

        self.textColumn.addWidget(self.subtitle)


        self.headerLayout.addLayout(self.textColumn)

        self.statusBadge = QLabel(self.headerWidget)
        self.statusBadge.setObjectName(u"statusBadge")
        self.statusBadge.setStyleSheet(u"QLabel#statusBadge {\n"
"           background-color: #e0f2fe;\n"
"           color: #0369a1;\n"
"           border-radius: 9px;\n"
"           font-weight: 600;\n"
"           font-size: 10px;\n"
"           padding: 2px 8px;\n"
"       }\n"
"       QLabel#statusBadge[stepStatus=\"done\"] { background-color: #dcfce7; color: #15803d; }\n"
"       QLabel#statusBadge[stepStatus=\"running\"] { background-color: #fef3c7; color: #b45309; }")
        self.statusBadge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.statusBadge.setProperty(u"stepStatus", u"ready")

        self.headerLayout.addWidget(self.statusBadge)

        self.chevron = QLabel(self.headerWidget)
        self.chevron.setObjectName(u"chevron")
        self.chevron.setMinimumSize(QSize(14, 0))
        self.chevron.setMaximumSize(QSize(14, 16777215))
        self.chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.headerLayout.addWidget(self.chevron)


        self.cardLayout.addWidget(self.headerWidget)

        self.body = QWidget(StepCard)
        self.body.setObjectName(u"body")
        self.contentLayout = QVBoxLayout(self.body)
        self.contentLayout.setSpacing(6)
        self.contentLayout.setObjectName(u"contentLayout")
        self.contentLayout.setContentsMargins(10, 8, 10, 10)

        self.cardLayout.addWidget(self.body)


        self.retranslateUi(StepCard)

        QMetaObject.connectSlotsByName(StepCard)
    # setupUi

    def retranslateUi(self, StepCard):
        self.number.setText(QCoreApplication.translate("StepCard", u"1", None))
        self.toggle.setText(QCoreApplication.translate("StepCard", u"Step Title", None))
        self.subtitle.setText(QCoreApplication.translate("StepCard", u"Ready", None))
        self.statusBadge.setText(QCoreApplication.translate("StepCard", u"\u2713 Ready", None))
        self.chevron.setText("")
        pass
    # retranslateUi

Ui_stepCard = Ui_StepCard
