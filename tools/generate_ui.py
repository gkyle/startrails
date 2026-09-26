"""Regenerate checked-in PySide forms with this environment's pyside6-uic."""
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "src/startrails/ui"
    executable = Path(sys.executable).with_name("pyside6-uic.exe" if sys.platform == "win32" else "pyside6-uic")
    compiler = str(executable) if executable.exists() else shutil.which("pyside6-uic")
    if not compiler:
        raise SystemExit("Run with the project environment containing PySide6.")
    for source in sorted(directory.glob("*.ui")):
        name = source.stem if source.stem.startswith("ui_") else "ui_" + source.stem
        result = subprocess.run([compiler, source.name], cwd=directory, check=True, capture_output=True)
        # uic's resource import must be package-relative when imported by the app.
        code = result.stdout.decode("utf-8").replace("import icons_darktheme_rc", "from . import icons_darktheme_rc")
        (directory / (name + ".py")).write_text(code.rstrip() + "\n", encoding="utf-8", newline="\n")
        print(source.name)


if __name__ == "__main__":
    main()
