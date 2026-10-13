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

## Code Naming Conventions

For consistency across the codebase, all new Python code must adhere to standard PEP 8 naming conventions:

- **Files & Modules**: `snake_case.py` (e.g., `sky_detector.py`, `freeze_ground.py`, `workflow_base.py`).
- **Classes**: `PascalCase` (e.g., `DarkCalibrator`, `FreezeGroundStacker`, `DenoisePipeline`).
- **Functions & Methods**: `snake_case` (e.g., `compute_master_dark()`, `get_array_module()`, `free_gpu_memory()`).
- **Variables & Arguments**: `snake_case` (e.g., `chunk_rows`, `use_gpu`, `input_path`).
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_CHUNK_ROWS`, `MAX_RETRIES`).

*(Note: Legacy code and Qt-required method overrides such as `mousePressEvent` or Qt-generated classes `Ui_*` are exempted, but all newly authored components must follow these conventions).*

### Linting Checks

Run the following lightweight checks to verify naming consistency:

```
# Check function (N802) and class (N801) naming conventions
uvx ruff check
```
