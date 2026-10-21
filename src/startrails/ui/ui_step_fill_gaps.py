# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_fill_gaps.ui'
##
## Created by: Qt User Interface Compiler version 6.12.0
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
from PySide6.QtWidgets import (QApplication, QLabel, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget)

class Ui_fillSettings(object):
    def setupUi(self, fillSettings):
        if not fillSettings.objectName():
            fillSettings.setObjectName(u"fillSettings")
        fillSettings.resize(117, 91)
        self.layout = QVBoxLayout(fillSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.target = QLabel(fillSettings)
        self.target.setObjectName(u"target")
        self.target.setStyleSheet(u"font-size: 12px;\n"
"color: #475569;")
        self.target.setWordWrap(True)

        self.layout.addWidget(self.target)

        self.run = QPushButton(fillSettings)
        self.run.setObjectName(u"run")
        self.run.setEnabled(False)
        self.run.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.run.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.layout.addWidget(self.run)


        self.retranslateUi(fillSettings)

        QMetaObject.connectSlotsByName(fillSettings)
    # setupUi

    def retranslateUi(self, fillSettings):
        self.target.setText(QCoreApplication.translate("fillSettings", u"Select a stacked output image to fill its gaps.", None))
        self.run.setText(QCoreApplication.translate("fillSettings", u"Fill Gaps", None))
        pass
    # retranslateUi

Ui_FillSettings = Ui_fillSettings
