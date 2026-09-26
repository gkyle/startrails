"""Render the real UI with sample files, without modifying the user's project."""
import argparse
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "src"))
from test_window import FakeApp, QT_APP, ui_wrap
from startrails.lib.file import InputFile, OutputFile
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--expanded", action="store_true")
    parser.add_argument("--bottom", action="store_true")
    args = parser.parse_args()
    QT_APP.setStyle("Fusion")
    QT_APP.styleHints().setColorScheme(Qt.ColorScheme.Dark if args.theme == "dark" else Qt.ColorScheme.Light)
    if args.theme == "dark":
        # Offscreen Qt has no OS theme provider; simulate the system's palette.
        palette = QPalette()
        for role, color in ((QPalette.Window, "#252525"), (QPalette.WindowText, "#eeeeee"),
                            (QPalette.Base, "#202020"), (QPalette.AlternateBase, "#2d2d2d"),
                            (QPalette.Text, "#eeeeee"), (QPalette.Button, "#303030"),
                            (QPalette.ButtonText, "#eeeeee"), (QPalette.Mid, "#555555"),
                            (QPalette.Highlight, "#347eaa"), (QPalette.HighlightedText, "#ffffff")):
            palette.setColor(role, QColor(color))
        for role in (QPalette.Text, QPalette.WindowText, QPalette.ButtonText):
            palette.setColor(QPalette.Disabled, role, QColor("#999999"))
        QT_APP.setPalette(palette)
    app = FakeApp()
    sample = str(ROOT / "docs/images/example_stack_with_streaks.jpg")
    app.inputs = [InputFile(f"DSC_{index:04}.jpg", sample) for index in range(1000)]
    app.inputs[1].streaksMasks = [[]] * 2
    app.inputs[2].streaksManualMasks = [[]]
    app.inputs[3].streaksManualDeletedMasks = [[]]
    app.inputs[4].excludeFromStack = True
    app.outputs = [OutputFile("stacked-night-sky.tif", sample, "Stacked")]
    window = ui_wrap.MainWindow(app)
    window.resize(args.width, args.height)
    if args.expanded:
        for card in (window.ui.sidebar.stackCard, window.ui.sidebar.fillCard, window.ui.sidebar.exportCard):
            card.setExpanded(True)
    QT_APP.processEvents()
    if args.bottom:
        bar = window.ui.sidebar.ui.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
        QT_APP.processEvents()
    window.grab().save(str(args.output))
    print(args.output)
    print(f"Window {window.width()}x{window.height()}, sidebar {window.ui.sidebar.width()} px")
    window.close()


if __name__ == "__main__":
    main()
