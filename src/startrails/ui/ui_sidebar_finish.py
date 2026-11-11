# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'sidebar_finish.ui'
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
from PySide6.QtWidgets import (QApplication, QFrame, QHBoxLayout, QPushButton,
    QScrollArea, QSizePolicy, QSpacerItem, QVBoxLayout,
    QWidget)

from startrails.ui.file_manager import FileSection
from startrails.ui.sky_mask_settings import SkyMaskSettings
from startrails.ui.steps import StepCard
from startrails.ui.steps_recombine import FinishRecombineSettings
from startrails.ui.steps_separate import SeparateStarsSettings
from startrails.ui.steps_starless import FinishStarlessSettings
from . import resources_rc

class Ui_SidebarFinish(object):
    def setupUi(self, SidebarFinish):
        if not SidebarFinish.objectName():
            SidebarFinish.setObjectName(u"SidebarFinish")
        SidebarFinish.resize(213, 400)
        SidebarFinish.setMinimumSize(QSize(0, 0))
        SidebarFinish.setMaximumSize(QSize(16777215, 16777215))
        self.root_layout = QVBoxLayout(SidebarFinish)
        self.root_layout.setSpacing(0)
        self.root_layout.setObjectName(u"root_layout")
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea(SidebarFinish)
        self.scroll.setObjectName(u"scroll")
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.setWidgetResizable(True)
        self.content = QWidget()
        self.content.setObjectName(u"content")
        self.content.setGeometry(QRect(0, 0, 213, 400))
        self.contentLayout = QVBoxLayout(self.content)
        self.contentLayout.setSpacing(8)
        self.contentLayout.setObjectName(u"contentLayout")
        self.contentLayout.setContentsMargins(8, 8, 8, 8)
        self.projectActions = QHBoxLayout()
        self.projectActions.setSpacing(6)
        self.projectActions.setObjectName(u"projectActions")
        self.newProject = QPushButton(self.content)
        self.newProject.setObjectName(u"newProject")
        self.newProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.projectActions.addWidget(self.newProject)

        self.openProject = QPushButton(self.content)
        self.openProject.setObjectName(u"openProject")
        self.openProject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.projectActions.addWidget(self.openProject)


        self.contentLayout.addLayout(self.projectActions)

        self.inputFiles = FileSection(self.content)
        self.inputFiles.setObjectName(u"inputFiles")
        self.inputFiles.setProperty(u"inputs", True)
        self.inputFiles.setProperty(u"show_legend", False)
        self.inputFiles.setProperty(u"is_expanded", True)

        self.contentLayout.addWidget(self.inputFiles)

        self.outputFiles = FileSection(self.content)
        self.outputFiles.setObjectName(u"outputFiles")
        self.outputFiles.setProperty(u"inputs", False)
        self.outputFiles.setProperty(u"show_legend", False)
        self.outputFiles.setProperty(u"is_expanded", True)

        self.contentLayout.addWidget(self.outputFiles)

        self.skyCard = StepCard(self.content)
        self.skyCard.setObjectName(u"skyCard")
        self.skyCard.setProperty(u"step_number", 1)
        self.skyCard.setProperty(u"is_expanded", False)
        self.skyCard.setProperty(u"before_after_enabled", True)
        self.skySettings = SkyMaskSettings(self.skyCard)
        self.skySettings.setObjectName(u"skySettings")
        self.skySettings.setGeometry(QRect(0, 0, 100, 30))
        self.skyCard.add_body(self.skySettings)

        self.contentLayout.addWidget(self.skyCard)

        self.separateCard = StepCard(self.content)
        self.separateCard.setObjectName(u"separateCard")
        self.separateCard.setProperty(u"step_number", 2)
        self.separateCard.setProperty(u"is_expanded", False)
        self.separateCard.setProperty(u"before_after_enabled", True)
        self.separateSettings = SeparateStarsSettings(self.separateCard)
        self.separateSettings.setObjectName(u"separateSettings")
        self.separateSettings.setGeometry(QRect(0, 0, 100, 30))
        self.separateCard.add_body(self.separateSettings)

        self.contentLayout.addWidget(self.separateCard)

        self.starlessCard = StepCard(self.content)
        self.starlessCard.setObjectName(u"starlessCard")
        self.starlessCard.setProperty(u"step_number", 3)
        self.starlessCard.setProperty(u"is_expanded", False)
        self.starlessCard.setProperty(u"before_after_enabled", True)
        self.starlessSettings = FinishStarlessSettings(self.starlessCard)
        self.starlessSettings.setObjectName(u"starlessSettings")
        self.starlessSettings.setGeometry(QRect(0, 0, 100, 30))
        self.starlessCard.add_body(self.starlessSettings)

        self.contentLayout.addWidget(self.starlessCard)

        self.recombineCard = StepCard(self.content)
        self.recombineCard.setObjectName(u"recombineCard")
        self.recombineCard.setProperty(u"step_number", 4)
        self.recombineCard.setProperty(u"is_expanded", False)
        self.recombineCard.setProperty(u"before_after_enabled", True)
        self.recombineSettings = FinishRecombineSettings(self.recombineCard)
        self.recombineSettings.setObjectName(u"recombineSettings")
        self.recombineSettings.setGeometry(QRect(0, 0, 100, 30))
        self.recombineCard.add_body(self.recombineSettings)

        self.contentLayout.addWidget(self.recombineCard)

        self.content_spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        self.contentLayout.addItem(self.content_spacer)

        self.scroll.setWidget(self.content)

        self.root_layout.addWidget(self.scroll)


        self.retranslateUi(SidebarFinish)

        QMetaObject.connectSlotsByName(SidebarFinish)
    # setupUi

    def retranslateUi(self, SidebarFinish):
#if QT_CONFIG(tooltip)
        self.newProject.setToolTip(QCoreApplication.translate("SidebarFinish", u"Create a new project", None))
#endif // QT_CONFIG(tooltip)
        self.newProject.setText(QCoreApplication.translate("SidebarFinish", u"New Project", None))
#if QT_CONFIG(tooltip)
        self.openProject.setToolTip(QCoreApplication.translate("SidebarFinish", u"Open an existing project", None))
#endif // QT_CONFIG(tooltip)
        self.openProject.setText(QCoreApplication.translate("SidebarFinish", u"Open Project", None))
        self.inputFiles.setProperty(u"title", QCoreApplication.translate("SidebarFinish", u"Input Files", None))
        self.outputFiles.setProperty(u"title", QCoreApplication.translate("SidebarFinish", u"Output Files", None))
        self.skyCard.setProperty(u"title", QCoreApplication.translate("SidebarFinish", u"Define Sky Region", None))
        self.skyCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarFinish", u"Detect Sky and refine sky protection mask", None))
        self.separateCard.setProperty(u"title", QCoreApplication.translate("SidebarFinish", u"Separate Stars", None))
        self.separateCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarFinish", u"Separate into starless and stars layers", None))
        self.starlessCard.setProperty(u"title", QCoreApplication.translate("SidebarFinish", u"Finish Starless", None))
        self.starlessCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarFinish", u"AI denoise with Structure and Detail controls", None))
        self.recombineCard.setProperty(u"title", QCoreApplication.translate("SidebarFinish", u"Recombine and Save", None))
        self.recombineCard.setProperty(u"subtitle", QCoreApplication.translate("SidebarFinish", u"Blend layers and export image", None))
        pass
    # retranslateUi

Ui_sidebarFinish = Ui_SidebarFinish
