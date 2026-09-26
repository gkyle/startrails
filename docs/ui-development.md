# Editing the UI

Static layouts live in `src/startrails/ui/*.ui` and can be edited with Qt Designer. Python controllers compose the generated forms and implement signals, models, validation, and expansion. Do not edit generated `ui_*.py` files by hand.

From the repository root, regenerate all forms using the project environment (PySide6 6.8.2):

```powershell
.venv/Scripts/python.exe tools/generate_ui.py
```

On Linux/macOS use `.venv/bin/python`. Commit each `.ui` change with its generated Python. The generator uses relative source names so output is independent of the checkout path.

Run UI checks without models or GPU initialization:

```powershell
$env:PYTHONPATH = 'src'
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

The step shell uses Qt palette roles rather than fixed light/dark colors. Keep controls keyboard accessible, use label buddies for settings, and avoid painting annotation status with color alone.
