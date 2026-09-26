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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--theme", choices=("light", "dark"), default="light")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args()
    QT_APP.setStyle("Fusion")
    QT_APP.styleHints().setColorScheme(Qt.ColorScheme.Dark if args.theme == "dark" else Qt.ColorScheme.Light)
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
    QT_APP.processEvents()
    window.grab().save(str(args.output))
    print(args.output)
    print(f"Window {window.width()}x{window.height()}, sidebar {window.ui.sidebar.width()} px")
    window.close()


if __name__ == "__main__":
    main()
