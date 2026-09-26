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
    QSizePolicy, QToolButton, QVBoxLayout, QWidget)

class Ui_StepCard(object):
    def setupUi(self, stepCard):
        if not stepCard.objectName():
            stepCard.setObjectName(u"stepCard")
        stepCard.setStyleSheet(u"QFrame#stepCard { border: 1px solid palette(mid); border-radius: 8px; }\n"
"QLabel#number { background: palette(highlight); color: palette(highlighted-text); border-radius: 14px; font-weight: bold; }\n"
"QToolButton#toggle { border: none; text-align: left; padding: 6px; font-weight: bold; }\n"
"QToolButton#toggle:hover { background: palette(alternate-base); }\n"
"QToolButton#toggle:focus { border: 1px solid palette(highlight); }")
        self.cardLayout = QVBoxLayout(stepCard)
        self.cardLayout.setSpacing(6)
        self.cardLayout.setObjectName(u"cardLayout")
        self.headerLayout = QHBoxLayout()
        self.headerLayout.setObjectName(u"headerLayout")
        self.number = QLabel(stepCard)
        self.number.setObjectName(u"number")
        self.number.setMinimumSize(QSize(28, 28))
        self.number.setMaximumSize(QSize(28, 28))
        self.number.setAlignment(Qt.AlignCenter)

        self.headerLayout.addWidget(self.number)

        self.toggle = QToolButton(stepCard)
        self.toggle.setObjectName(u"toggle")
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.toggle.sizePolicy().hasHeightForWidth())
        self.toggle.setSizePolicy(sizePolicy)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.RightArrow)

        self.headerLayout.addWidget(self.toggle)


        self.cardLayout.addLayout(self.headerLayout)

        self.subtitle = QLabel(stepCard)
        self.subtitle.setObjectName(u"subtitle")
        self.subtitle.setWordWrap(True)

        self.cardLayout.addWidget(self.subtitle)

        self.body = QWidget(stepCard)
        self.body.setObjectName(u"body")
        self.contentLayout = QVBoxLayout(self.body)
        self.contentLayout.setObjectName(u"contentLayout")
        self.contentLayout.setContentsMargins(0, 4, 0, 0)

        self.cardLayout.addWidget(self.body)


        self.retranslateUi(stepCard)

        QMetaObject.connectSlotsByName(stepCard)
    # setupUi

    def retranslateUi(self, stepCard):
        self.number.setText(QCoreApplication.translate("StepCard", u"1", None))
        self.toggle.setText(QCoreApplication.translate("StepCard", u"Step", None))
        self.subtitle.setText(QCoreApplication.translate("StepCard", u"Ready", None))
        pass
    # retranslateUi
