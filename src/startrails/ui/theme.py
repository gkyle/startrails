"""System appearance support for the Designer styles and custom painters.

Designer forms remain the light-mode source. Only color declarations are adapted;
layout, selectors and state rules are shared by both appearances.
"""
import re
from weakref import WeakKeyDictionary, WeakSet

from PySide6.QtCore import QObject, QTimer, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget


_DARK_FOREGROUND = {
    "#0f172a": "#f1f5f9", "#1e293b": "#e2e8f0",
    "#334155": "#cbd5e1", "#475569": "#cbd5e1",
    "#64748b": "#94a3b8", "#94a3b8": "#64748b",
    "#0284c7": "#38bdf8", "#0369a1": "#7dd3fc",
    "#1d4ed8": "#93c5fd", "#15803d": "#86efac",
    "#166534": "#bbf7d0", "#b45309": "#fbbf24",
    "#92400e": "#fde68a", "#b91c1c": "#fca5a5",
    "#ef4444": "#f87171", "#6b21a8": "#d8b4fe",
}
_DARK_BACKGROUND = {
    "#ffffff": "#1e293b", "#f8fafc": "#0f172a",
    "#f1f5f9": "#263449", "#e2e8f0": "#334155",
    "#cbd5e1": "#475569", "#94a3b8": "#64748b",
    "#eff6ff": "#1e3a5f", "#e0f2fe": "#12354a",
    "#f0f9ff": "#162e42", "#dcfce7": "#163b2b",
    "#f0fdf4": "#162f28", "#fef3c7": "#44351d",
    "#fffbeb": "#342b1f", "#fee2e2": "#48252d",
    "#f3e8ff": "#35254a",
}
_DARK_BORDER = {
    "#64748b": "#94a3b8", "#0369a1": "#38bdf8",
    "#0f172a": "#f1f5f9",
    "#cccccc": "#475569",
    "#f1f5f9": "#334155", "#e2e8f0": "#334155",
    "#cbd5e1": "#475569", "#94a3b8": "#64748b",
    "#bbf7d0": "#276749", "#bae6fd": "#25516c",
    "#fde68a": "#705326", "#fecaca": "#7f3542",
    "#bfdbfe": "#315b85", "#e9d5ff": "#63417e",
}
_COLORS = {"foreground": _DARK_FOREGROUND, "background": _DARK_BACKGROUND,
           "border": _DARK_BORDER}
_DECLARATION = re.compile(r"(^|[;{])(\s*)([\w-]+)(\s*:\s*)([^;{}]+)", re.MULTILINE)
_HEX = re.compile(r"#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")


def is_dark(palette: QPalette) -> bool:
    background = palette.color(QPalette.Window)
    # Transparent tree views inherit the surface but have a black/zero-alpha
    # Window brush. Their inherited foreground still identifies the theme.
    if background.alpha() == 0:
        return palette.color(QPalette.WindowText).lightness() > 128
    return background.lightness() < 128


def themed_color(light: str, palette: QPalette, role: str = "foreground") -> QColor:
    return QColor(_COLORS[role].get(light, light) if is_dark(palette) else light)


def dark_stylesheet(source: str) -> str:
    for direction in ("up", "down"):
        source = source.replace(f"/arrow_{direction}.svg", f"/arrow_{direction}_dark.svg")
    for direction in ("down", "right"):
        source = source.replace(f"/chevron_{direction}.svg", f"/chevron_{direction}_dark.svg")

    def declaration(match):
        start, space, name, separator, value = match.groups()
        if name in ("color", "selection-color"):
            colors = _DARK_FOREGROUND
        elif name in ("background", "background-color", "selection-background-color"):
            colors = _DARK_BACKGROUND
        elif name.startswith("border"):
            colors = _DARK_BORDER
        else:
            return match.group(0)
        def replace_color(match):
            color = match[0].lower()
            if len(color) == 4:
                color = "#" + "".join(channel * 2 for channel in color[1:])
            return colors.get(color, match[0])

        value = _HEX.sub(replace_color, value)
        return start + space + name + separator + value

    return _DECLARATION.sub(declaration, source)


def theme_palette(dark: bool) -> QPalette:
    palette = QPalette(QApplication.instance().style().standardPalette())
    roles = {
        QPalette.Window: ("#f8fafc", "#0f172a"),
        QPalette.WindowText: ("#0f172a", "#f1f5f9"),
        QPalette.Base: ("#ffffff", "#1e293b"),
        QPalette.AlternateBase: ("#f8fafc", "#263449"),
        QPalette.Text: ("#0f172a", "#f1f5f9"),
        QPalette.Button: ("#f1f5f9", "#263449"),
        QPalette.ButtonText: ("#1e293b", "#e2e8f0"),
        QPalette.Highlight: ("#0369a1", "#0369a1"),
        QPalette.HighlightedText: ("#ffffff", "#ffffff"),
        QPalette.ToolTipBase: ("#ffffff", "#1e293b"),
        QPalette.ToolTipText: ("#0f172a", "#f1f5f9"),
        QPalette.PlaceholderText: ("#64748b", "#94a3b8"),
        QPalette.Link: ("#0369a1", "#38bdf8"),
        QPalette.LinkVisited: ("#6b21a8", "#d8b4fe"),
        QPalette.Light: ("#ffffff", "#475569"),
        QPalette.Midlight: ("#f1f5f9", "#334155"),
        QPalette.Mid: ("#cbd5e1", "#475569"),
        QPalette.Dark: ("#94a3b8", "#0f172a"),
        QPalette.Shadow: ("#64748b", "#020617"),
        QPalette.Accent: ("#0284c7", "#38bdf8"),
    }
    for role, values in roles.items():
        palette.setColor(role, QColor(values[dark]))
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        palette.setColor(QPalette.Disabled, role, QColor("#64748b" if dark else "#94a3b8"))
    return palette


class SystemTheme(QObject):
    def __init__(self, app: QApplication):
        super().__init__(app)
        self.app = app
        self._roots = WeakSet()
        self._styles = WeakKeyDictionary()
        self.dark = False
        app.styleHints().colorSchemeChanged.connect(self._system_changed)
        self.apply_scheme(app.styleHints().colorScheme())

    def _system_changed(self, scheme):
        # Qt updates its platform palette after emitting colorSchemeChanged.
        QTimer.singleShot(0, self, lambda: self.apply_scheme(scheme))

    def apply_scheme(self, scheme: Qt.ColorScheme):
        self.dark = (is_dark(self.app.palette()) if scheme == Qt.ColorScheme.Unknown
                     else scheme == Qt.ColorScheme.Dark)
        self.app.setPalette(theme_palette(self.dark))
        for root in self._roots:
            self._apply_widget(root)

    def register(self, root: QWidget):
        """Apply after setupUi, including forms created after a theme change."""
        if root not in self._roots:
            self._roots.add(root)
            root.destroyed.connect(lambda: self._roots.discard(root))
        self._apply_widget(root)

    def _apply_widget(self, widget: QWidget):
        if widget.property("themeFixed"):
            return
        source = self._styles.setdefault(widget, widget.styleSheet())
        sheet = dark_stylesheet(source) if self.dark else source
        if widget.styleSheet() != sheet:
            widget.setStyleSheet(sheet)
        QWidget.update(widget)
        for child in widget.children():
            if isinstance(child, QWidget):
                self._apply_widget(child)


def system_theme() -> SystemTheme:
    app = QApplication.instance()
    if not hasattr(app, "_startrails_theme"):
        app._startrails_theme = SystemTheme(app)
    return app._startrails_theme
