# Contributor Guidelines

## UI Development (`src/startrails/ui/`)

When creating or modifying user interface components:

### 1. Declarative UI First (`.ui` files)
- **Always define UI declaratively** in `.ui` XML files. Do not build widget hierarchies, layouts, or static styling procedurally in Python.
- Configure widget properties directly in Designer: `objectName`, `toolTip`, `accessibleName`, `cursor`, `iconSize`, and size policies.
- Python wrapper classes should only handle signal/slot connections, model/data binding, and dynamic menus.

### 2. Stylesheets (QSS)
- Place component styles directly into the stylesheet property of the `.ui` forms.

### 3. Theme Support (Light & Dark)
- **Light mode is the source of truth** in `.ui` files.
- `SystemTheme` in [`src/startrails/ui/theme.py`](src/startrails/ui/theme.py) automatically converts hex colors to dark-mode equivalents at runtime.
- **Icons in stylesheets**: Set button icons declaratively via `qproperty-icon: url(:/startrails/ui/<name>.svg);` or `image: url(...)`. Register the dark variant in `dark_stylesheet()` in `theme.py` (e.g. `source.replace('/sort.svg', '/sort_dark.svg')`). Do not write imperative Python theme-switching hooks when stylesheets can handle it.
- **Custom `QPainter` code** (e.g. item delegates or canvas labels): Use `themed_color(color, palette)` and `is_dark(palette)` from `theme.py`. Avoid hardcoded RGB values in paint methods.

### 4. Icons & Resources
- Place SVG vector icons in `src/startrails/ui/icons/` (provide both `<name>.svg` and `<name>_dark.svg`).
- Register all icons in `src/startrails/ui/resources.qrc`.
- In `.ui` files, ensure `<resources><include location="resources.qrc"/></resources>` is declared.

### 5. Code Generation
- After editing any `.ui` or `.qrc` files, regenerate bindings using:
  ```sh
  uv run --no-sync python tools/generate_ui.py
  ```
- **Never edit generated files directly** (`ui_*.py` and `resources_rc.py`), as they are overwritten by `generate_ui.py`.
