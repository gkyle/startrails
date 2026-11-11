# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'step_denoise_export.ui'
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

class Ui_DenoiseExportSettings(object):
    def setupUi(self, DenoiseExportSettings):
        if not DenoiseExportSettings.objectName():
            DenoiseExportSettings.setObjectName(u"DenoiseExportSettings")
        self.layout = QVBoxLayout(DenoiseExportSettings)
        self.layout.setSpacing(8)
        self.layout.setObjectName(u"layout")
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.contributeHeading = QLabel(DenoiseExportSettings)
        self.contributeHeading.setObjectName(u"contributeHeading")

        self.layout.addWidget(self.contributeHeading)

        self.contributeHint = QLabel(DenoiseExportSettings)
        self.contributeHint.setObjectName(u"contributeHint")
        self.contributeHint.setWordWrap(True)

        self.layout.addWidget(self.contributeHint)

        self.contribute = QPushButton(DenoiseExportSettings)
        self.contribute.setObjectName(u"contribute")
        self.contribute.setEnabled(False)
        self.contribute.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.layout.addWidget(self.contribute)

        self.training = QPushButton(DenoiseExportSettings)
        self.training.setObjectName(u"training")
        self.training.setEnabled(False)
        self.training.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.layout.addWidget(self.training)


        self.retranslateUi(DenoiseExportSettings)

        QMetaObject.connectSlotsByName(DenoiseExportSettings)
    # setupUi

    def retranslateUi(self, DenoiseExportSettings):
        self.contributeHeading.setText(QCoreApplication.translate("DenoiseExportSettings", u"Optional: Contribute Corrections", None))
        self.contributeHint.setText(QCoreApplication.translate("DenoiseExportSettings", u"Export manual sky mask corrections to help improve future celestial sky detection models.", None))
#if QT_CONFIG(tooltip)
        self.contribute.setToolTip(QCoreApplication.translate("DenoiseExportSettings", u"Requires manual sky mask brush corrections.", None))
#endif // QT_CONFIG(tooltip)
        self.contribute.setText(QCoreApplication.translate("DenoiseExportSettings", u"Contribute Corrections", None))
#if QT_CONFIG(tooltip)
        self.training.setToolTip(QCoreApplication.translate("DenoiseExportSettings", u"Requires manual sky mask brush corrections.", None))
#endif // QT_CONFIG(tooltip)
        self.training.setText(QCoreApplication.translate("DenoiseExportSettings", u"Export to Disk", None))
        pass
    # retranslateUi

Ui_denoiseExportSettings = Ui_DenoiseExportSettings
