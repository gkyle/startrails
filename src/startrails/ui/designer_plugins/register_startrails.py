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

from PySide6.QtDesigner import QPyDesignerCustomWidgetCollection

from startrails.ui.sidebar import Sidebar
from startrails.ui.steps import (
    DetectSettings,
    StackSettings,
    ReviewSettings,
    FillSettings,
    AdditionalToolsSettings,
    StepCard,
)
from startrails.ui.file_manager import FileSection

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
