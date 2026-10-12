"""Regenerate checked-in PySide forms and their Qt resources."""
from pathlib import Path
import shutil
import subprocess
import sys


def find_compiler(name):
    executable = Path(sys.executable).with_name(name + (".exe" if sys.platform == "win32" else ""))
    compiler = str(executable) if executable.exists() else shutil.which(name)
    if not compiler:
        raise SystemExit("Run with the project environment containing PySide6.")
    return compiler


def main():
    root = Path(__file__).resolve().parents[1]
    directory = root / "src/startrails/ui"
    compiler = find_compiler("pyside6-uic")
    resource_compiler = find_compiler("pyside6-rcc")
    for source in sorted(directory.glob("*.qrc")):
        result = subprocess.run([resource_compiler, source.name], cwd=directory, check=True, capture_output=True)
        code = result.stdout.decode("utf-8").replace("\r\n", "\n")
        target = directory / (source.stem + "_rc.py")
        formatted = code.rstrip() + "\n"
        if not target.exists() or target.read_text(encoding="utf-8") != formatted:
            target.write_text(formatted, encoding="utf-8", newline="\n")
        print(source.name)
    import re
    for source in sorted(directory.glob("*.ui")):
        name = source.stem if source.stem.startswith("ui_") else "ui_" + source.stem
        result = subprocess.run([compiler, "--from-imports", source.name], cwd=directory, check=True, capture_output=True)
        code = result.stdout.decode("utf-8").replace("\r\n", "\n")
        for match in re.finditer(r"class\s+(Ui_([A-Za-z0-9_]+))\s*\(", code):
            full_class, base_name = match.group(1), match.group(2)
            pascal_class = f"Ui_{base_name[0].upper()}{base_name[1:]}"
            camel_class = f"Ui_{base_name[0].lower()}{base_name[1:]}"
            aliases = []
            if pascal_class != full_class and f"\n{pascal_class} =" not in code:
                aliases.append(f"{pascal_class} = {full_class}")
            if camel_class != full_class and f"\n{camel_class} =" not in code:
                aliases.append(f"{camel_class} = {full_class}")
            if aliases:
                code = code.rstrip() + "\n\n" + "\n".join(aliases) + "\n"
        target = directory / (name + ".py")
        formatted = code.rstrip() + "\n"
        if not target.exists() or target.read_text(encoding="utf-8") != formatted:
            target.write_text(formatted, encoding="utf-8", newline="\n")
        print(source.name)


if __name__ == "__main__":
    main()
