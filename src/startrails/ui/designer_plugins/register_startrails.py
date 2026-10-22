"""Qt Designer plugins for Startrails custom widgets."""
import os
import sys
from pathlib import Path

# Ensure project src is in sys.path when loaded by Qt Designer
for candidate in [
    os.environ.get("PYSIDE_DESIGNER_PLUGINS"),
    os.getcwd(),
    str(Path(__file__).resolve().parent) if "__file__" in globals() and __file__ != "pyscript" else None,
]:
    if candidate:
        p = Path(candidate).resolve()
        while p != p.parent:
            if (p / "src" / "startrails").is_dir():
                src_path = str(p / "src")
                if src_path not in sys.path:
                    sys.path.insert(0, src_path)
                break
            p = p.parent

from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection, QDesignerCustomWidgetInterface
from PySide6.QtGui import QIcon


class StartrailsStylePlugin(QDesignerCustomWidgetInterface):
    """Qt Designer plugin that automatically applies styles.qss to form windows."""

    def __init__(self):
        super().__init__()
        self._initialized = False

    def initialize(self, core):
        if self._initialized:
            return
        self._initialized = True
        try:
            mgr = core.formWindowManager()
            if mgr is not None:
                def _apply_styles(form_window):
                    try:
                        style_file = Path(__file__).resolve().parents[1] / "styles.qss"
                        if style_file.exists():
                            qss = style_file.read_text(encoding="utf-8")
                            container = form_window.formContainer()
                            if container is not None:
                                container.setStyleSheet(qss)
                    except Exception as err:
                        print("Error applying Startrails styles to Designer form:", err)

                mgr.formWindowAdded.connect(_apply_styles)
                for i in range(mgr.formWindowCount()):
                    _apply_styles(mgr.formWindow(i))
        except Exception as err:
            print("Error initializing StartrailsStylePlugin:", err)

    def isInitialized(self):
        return self._initialized

    def createWidget(self, parent):
        return None

    def name(self):
        return "StartrailsStylePlugin"

    def group(self):
        return ""

    def icon(self):
        return QIcon()

    def toolTip(self):
        return ""

    def whatsThis(self):
        return ""

    def isContainer(self):
        return False

    def domXml(self):
        return ""

    def includeFile(self):
        return ""


# Register style preview hook with Qt Designer
QPyDesignerCustomWidgetCollection.instance().addCustomWidget(StartrailsStylePlugin())

from startrails.ui.sidebar import Sidebar
from startrails.ui.sidebar_denoise import SidebarDenoise
from startrails.ui.steps import (
    DetectSettings,
    StackSettings,
    ReviewSettings,
    FillSettings,
    AdditionalToolsSettings,
    StepCard,
)
from startrails.ui.file_manager import FileSection
from startrails.ui.steps_denoise import (
    DenoiseSkySettings,
    DenoiseAlignSettings,
    DenoiseStackSettings,
    DenoiseTuneSettings,
    DenoiseExportSettings,
)

# 1. Sidebar (composite container)
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    Sidebar,
    module="startrails.ui.sidebar",
    group="Startrails",
    tool_tip="StarTrails AI Sidebar",
    container=True,
    xml="""<ui language='c++'>
    <widget class='Sidebar' name='sidebar'>
        <property name='minimumSize'>
            <size>
                <width>320</width>
                <height>0</height>
            </size>
        </property>
        <property name='maximumSize'>
            <size>
                <width>320</width>
                <height>16777215</height>
            </size>
        </property>
    </widget>
</ui>""",
)

# 1b. SidebarDenoise (composite container)
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    SidebarDenoise,
    module="startrails.ui.sidebar_denoise",
    group="Startrails",
    tool_tip="Denoise AI Sidebar",
    container=True,
    xml="""<ui language='c++'>
    <widget class='SidebarDenoise' name='sidebar'>
        <property name='minimumSize'>
            <size>
                <width>320</width>
                <height>0</height>
            </size>
        </property>
        <property name='maximumSize'>
            <size>
                <width>350</width>
                <height>16777215</height>
            </size>
        </property>
    </widget>
</ui>""",
)

# 2. DetectSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    DetectSettings,
    module="startrails.ui.steps",
    group="Startrails",
    tool_tip="Detect Streaks Settings",
    xml="""<ui language='c++'>
    <widget class='DetectSettings' name='detectSettings'>
    </widget>
</ui>""",
)

# 3. StackSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    StackSettings,
    module="startrails.ui.steps",
    group="Startrails",
    tool_tip="Stack Images Settings",
    xml="""<ui language='c++'>
    <widget class='StackSettings' name='stackSettings'>
    </widget>
</ui>""",
)

# 4. ReviewSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    ReviewSettings,
    module="startrails.ui.steps",
    group="Startrails",
    tool_tip="Review and Correct Settings",
    xml="""<ui language='c++'>
    <widget class='ReviewSettings' name='reviewSettings'>
    </widget>
</ui>""",
)

# 5. FillSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    FillSettings,
    module="startrails.ui.steps",
    group="Startrails",
    tool_tip="Fill Gaps Settings",
    xml="""<ui language='c++'>
    <widget class='FillSettings' name='fillSettings'>
    </widget>
</ui>""",
)

# 6. AdditionalToolsSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    AdditionalToolsSettings,
    module="startrails.ui.steps",
    group="Startrails",
    tool_tip="Additional Tools Settings",
    xml="""<ui language='c++'>
    <widget class='AdditionalToolsSettings' name='additionalToolsSettings'>
    </widget>
</ui>""",
)

# 7. FileSection
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    FileSection,
    module="startrails.ui.file_manager",
    group="Startrails",
    tool_tip="File Section",
    xml="""<ui language='c++'>
    <widget class='FileSection' name='fileSection'>
    </widget>
</ui>""",
)

# 8. StepCard
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    StepCard,
    module="startrails.ui.steps",
    group="Startrails",
    tool_tip="Collapsible Step Card",
    container=True,
    xml="""<ui language='c++'>
    <widget class='StepCard' name='stepCard'>
    </widget>
</ui>""",
)

# 9. DenoiseSkySettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    DenoiseSkySettings,
    module="startrails.ui.steps_denoise",
    group="Startrails",
    tool_tip="Denoise Define Sky Region Settings",
    xml="""<ui language='c++'>
    <widget class='DenoiseSkySettings' name='denoiseSkySettings'>
    </widget>
</ui>""",
)

# 10. DenoiseAlignSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    DenoiseAlignSettings,
    module="startrails.ui.steps_denoise",
    group="Startrails",
    tool_tip="Denoise Align Stars Settings",
    xml="""<ui language='c++'>
    <widget class='DenoiseAlignSettings' name='denoiseAlignSettings'>
    </widget>
</ui>""",
)

# 11. DenoiseStackSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    DenoiseStackSettings,
    module="startrails.ui.steps_denoise",
    group="Startrails",
    tool_tip="Denoise Stack Foreground+Background Settings",
    xml="""<ui language='c++'>
    <widget class='DenoiseStackSettings' name='denoiseStackSettings'>
    </widget>
</ui>""",
)

# 12. DenoiseTuneSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    DenoiseTuneSettings,
    module="startrails.ui.steps_denoise",
    group="Startrails",
    tool_tip="Denoise Interactive Horizon Tuning Settings",
    xml="""<ui language='c++'>
    <widget class='DenoiseTuneSettings' name='denoiseTuneSettings'>
    </widget>
</ui>""",
)

# 13. DenoiseExportSettings
QPyDesignerCustomWidgetCollection.registerCustomWidget(
    DenoiseExportSettings,
    module="startrails.ui.steps_denoise",
    group="Startrails",
    tool_tip="Denoise Contribute and Export Settings",
    xml="""<ui language='c++'>
    <widget class='DenoiseExportSettings' name='denoiseExportSettings'>
    </widget>
</ui>""",
)

