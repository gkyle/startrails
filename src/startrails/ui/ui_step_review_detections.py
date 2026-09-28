# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_review_detections.ui'
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
from PySide6.QtWidgets import (QApplication, QCheckBox, QFrame, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget)

class Ui_ReviewSettings(object):
    def setupUi(self, reviewSettings):
        if not reviewSettings.objectName():
            reviewSettings.setObjectName(u"reviewSettings")
        reviewSettings.setStyleSheet(u"QLabel#optionalHeading, QLabel#contributeHeading {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #475569;\n"
"    text-transform: uppercase;\n"
"    letter-spacing: 0.5px;\n"
"    margin-top: 2px;\n"
"}\n"
"QLabel#optionalMasksHint, QLabel#contributeHint {\n"
"    font-size: 11px;\n"
"    color: #64748b;\n"
"    line-height: 1.3;\n"
"}\n"
"QFrame#statAuto {\n"
"    background-color: #f0fdf4;\n"
"    border: 1px solid #bbf7d0;\n"
"    border-radius: 6px;\n"
"}\n"
"QFrame#statManual {\n"
"    background-color: #f0f9ff;\n"
"    border: 1px solid #bae6fd;\n"
"    border-radius: 6px;\n"
"}\n"
"QFrame#statDeleted {\n"
"    background-color: #fffbeb;\n"
"    border: 1px solid #fde68a;\n"
"    border-radius: 6px;\n"
"}\n"
"QLabel#statAutoTitle {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #15803d;\n"
"}\n"
"QLabel#statManualTitle {\n"
"    font-size: 11px;\n"
"    font-weight: 600;\n"
"    color: #0284c7;\n"
"}\n"
"QLabel#statDeletedTitle {\n"
"    font-size: 11px;\n"
"    fon"
                        "t-weight: 600;\n"
"    color: #b45309;\n"
"}\n"
"QLabel#statAutoNum {\n"
"    font-size: 17px;\n"
"    font-weight: bold;\n"
"    color: #166534;\n"
"}\n"
"QLabel#statManualNum {\n"
"    font-size: 17px;\n"
"    font-weight: bold;\n"
"    color: #0369a1;\n"
"}\n"
"QLabel#statDeletedNum {\n"
"    font-size: 17px;\n"
"    font-weight: bold;\n"
"    color: #92400e;\n"
"}\n"
"QCheckBox#showDeletedMasks {\n"
"    font-size: 12px;\n"
"    color: #1e293b;\n"
"    spacing: 8px;\n"
"    font-weight: 500;\n"
"}\n"
"QPushButton#masks, QPushButton#training {\n"
"    background-color: #ffffff;\n"
"    color: #1e293b;\n"
"    border: 1px solid #cbd5e1;\n"
"    border-radius: 6px;\n"
"    padding: 6px 12px;\n"
"    font-weight: 500;\n"
"    font-size: 12px;\n"
"}\n"
"QPushButton#masks:hover, QPushButton#training:hover {\n"
"    background-color: #f1f5f9;\n"
"    border-color: #94a3b8;\n"
"}\n"
"QPushButton#masks:disabled, QPushButton#training:disabled {\n"
"    background-color: #f8fafc;\n"
"    color: #94a3b8;\n"
"    borde"
                        "r-color: #e2e8f0;\n"
"}\n"
"QFrame#sep1, QFrame#sep2 {\n"
"    background-color: #f1f5f9;\n"
"    max-height: 1px;\n"
"}")
        self.layout = QVBoxLayout(reviewSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.countsLayout = QHBoxLayout()
        self.countsLayout.setSpacing(6)
        self.countsLayout.setObjectName(u"countsLayout")
        self.statAuto = QFrame(reviewSettings)
        self.statAuto.setObjectName(u"statAuto")
        self.statAutoLayout = QVBoxLayout(self.statAuto)
        self.statAutoLayout.setSpacing(2)
        self.statAutoLayout.setObjectName(u"statAutoLayout")
        self.statAutoLayout.setContentsMargins(6, 6, 6, 6)
        self.statAutoTitle = QLabel(self.statAuto)
        self.statAutoTitle.setObjectName(u"statAutoTitle")

        self.statAutoLayout.addWidget(self.statAutoTitle, 0, Qt.AlignCenter)

        self.statAutoNum = QLabel(self.statAuto)
        self.statAutoNum.setObjectName(u"statAutoNum")

        self.statAutoLayout.addWidget(self.statAutoNum, 0, Qt.AlignCenter)


        self.countsLayout.addWidget(self.statAuto)

        self.statManual = QFrame(reviewSettings)
        self.statManual.setObjectName(u"statManual")
        self.statManualLayout = QVBoxLayout(self.statManual)
        self.statManualLayout.setSpacing(2)
        self.statManualLayout.setObjectName(u"statManualLayout")
        self.statManualLayout.setContentsMargins(6, 6, 6, 6)
        self.statManualTitle = QLabel(self.statManual)
        self.statManualTitle.setObjectName(u"statManualTitle")

        self.statManualLayout.addWidget(self.statManualTitle, 0, Qt.AlignCenter)

        self.statManualNum = QLabel(self.statManual)
        self.statManualNum.setObjectName(u"statManualNum")

        self.statManualLayout.addWidget(self.statManualNum, 0, Qt.AlignCenter)


        self.countsLayout.addWidget(self.statManual)

        self.statDeleted = QFrame(reviewSettings)
        self.statDeleted.setObjectName(u"statDeleted")
        self.statDeletedLayout = QVBoxLayout(self.statDeleted)
        self.statDeletedLayout.setSpacing(2)
        self.statDeletedLayout.setObjectName(u"statDeletedLayout")
        self.statDeletedLayout.setContentsMargins(6, 6, 6, 6)
        self.statDeletedTitle = QLabel(self.statDeleted)
        self.statDeletedTitle.setObjectName(u"statDeletedTitle")

        self.statDeletedLayout.addWidget(self.statDeletedTitle, 0, Qt.AlignCenter)

        self.statDeletedNum = QLabel(self.statDeleted)
        self.statDeletedNum.setObjectName(u"statDeletedNum")

        self.statDeletedLayout.addWidget(self.statDeletedNum, 0, Qt.AlignCenter)


        self.countsLayout.addWidget(self.statDeleted)


        self.layout.addLayout(self.countsLayout)

        self.showDeletedMasks = QCheckBox(reviewSettings)
        self.showDeletedMasks.setObjectName(u"showDeletedMasks")
        self.showDeletedMasks.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.layout.addWidget(self.showDeletedMasks)

        self.sep1 = QFrame(reviewSettings)
        self.sep1.setObjectName(u"sep1")
        self.sep1.setFrameShape(QFrame.HLine)

        self.layout.addWidget(self.sep1)

        self.optionalHeading = QLabel(reviewSettings)
        self.optionalHeading.setObjectName(u"optionalHeading")

        self.layout.addWidget(self.optionalHeading)

        self.optionalMasksHint = QLabel(reviewSettings)
        self.optionalMasksHint.setObjectName(u"optionalMasksHint")
        self.optionalMasksHint.setWordWrap(True)

        self.layout.addWidget(self.optionalMasksHint)

        self.masks = QPushButton(reviewSettings)
        self.masks.setObjectName(u"masks")
        self.masks.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.masks.setEnabled(False)

        self.layout.addWidget(self.masks)

        self.sep2 = QFrame(reviewSettings)
        self.sep2.setObjectName(u"sep2")
        self.sep2.setFrameShape(QFrame.HLine)

        self.layout.addWidget(self.sep2)

        self.contributeHeading = QLabel(reviewSettings)
        self.contributeHeading.setObjectName(u"contributeHeading")

        self.layout.addWidget(self.contributeHeading)

        self.contributeHint = QLabel(reviewSettings)
        self.contributeHint.setObjectName(u"contributeHint")
        self.contributeHint.setWordWrap(True)

        self.layout.addWidget(self.contributeHint)

        self.training = QPushButton(reviewSettings)
        self.training.setObjectName(u"training")
        self.training.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.training.setEnabled(False)

        self.layout.addWidget(self.training)


        self.retranslateUi(reviewSettings)

        QMetaObject.connectSlotsByName(reviewSettings)
    # setupUi

    def retranslateUi(self, reviewSettings):
        self.statAutoTitle.setText(QCoreApplication.translate("ReviewSettings", u"\u25cf Auto", None))
        self.statAutoNum.setText(QCoreApplication.translate("ReviewSettings", u"0", None))
        self.statManualTitle.setText(QCoreApplication.translate("ReviewSettings", u"\u25cf Manual", None))
        self.statManualNum.setText(QCoreApplication.translate("ReviewSettings", u"0", None))
        self.statDeletedTitle.setText(QCoreApplication.translate("ReviewSettings", u"\u25cf Deleted", None))
        self.statDeletedNum.setText(QCoreApplication.translate("ReviewSettings", u"0", None))
        self.showDeletedMasks.setText(QCoreApplication.translate("ReviewSettings", u"Show Deleted Masks", None))
        self.optionalHeading.setText(QCoreApplication.translate("ReviewSettings", u"Optional", None))
        self.optionalMasksHint.setText(QCoreApplication.translate("ReviewSettings", u"Save detected streak masks as image files.", None))
        self.masks.setText(QCoreApplication.translate("ReviewSettings", u"Export Masks", None))
#if QT_CONFIG(tooltip)
        self.masks.setToolTip(QCoreApplication.translate("ReviewSettings", u"Requires automatic or manual streak masks.", None))
#endif // QT_CONFIG(tooltip)
        self.contributeHeading.setText(QCoreApplication.translate("ReviewSettings", u"Optional: Contribute Corrections", None))
        self.contributeHint.setText(QCoreApplication.translate("ReviewSettings", u"Export manual additions and deletions to help improve future streak detection models.", None))
        self.training.setText(QCoreApplication.translate("ReviewSettings", u"Export Training", None))
#if QT_CONFIG(tooltip)
        self.training.setToolTip(QCoreApplication.translate("ReviewSettings", u"Requires manually added or deleted streak masks.", None))
#endif // QT_CONFIG(tooltip)
        pass
    # retranslateUi
