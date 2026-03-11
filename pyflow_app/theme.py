from typing import Any, Dict, Optional

THEMES = {
    "dark": {
        "main_bg": "#1e1e2e",
        "text": "#f3f6fb",
        "muted": "#9aa6bf",
        "panel_bg": "#2b2b3b",
        "panel_alt_bg": "#303247",
        "panel_hover_bg": "#3a3f58",
        "sidebar_bg": "#202536",
        "border": "#4e566d",
        "border_strong": "#59627a",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_pressed": "#1d4ed8",
        "accent_border": "#60a5fa",
        "disabled_bg": "#4b5563",
        "menu_bar_bg": "#232837",
        "menu_bar_text": "#f3f6fb",
        "menu_bar_hover": "#353c52",
        "canvas_bg": "#1e1e2e",
        "grid_minor": "#353a50",
        "grid_major": "#4a526e",
        "node_bg": "#2b2b3b",
        "node_highlight": "#78bbff",
        "node_text": "#ffffff",
        "node_desc": "#969fb0",
        "node_count": "#6aa36a",
        "conn_badge_bg": (30, 30, 46, 220),
        "conn_badge_text": "#f0f4ff",
        "status_text": "#888888",
        "log_bg": "#2b2b3b",
        "output_bg": "#161b26",
        "menu_border": "#3a4154",
        "scroll_bg": "#1b2030",
    },
    "light": {
        "main_bg": "#f4f6fb",
        "text": "#1f2937",
        "muted": "#5b6475",
        "panel_bg": "#ffffff",
        "panel_alt_bg": "#f6f8fc",
        "panel_hover_bg": "#e9eef7",
        "sidebar_bg": "#eef2f9",
        "border": "#c8d2e3",
        "border_strong": "#b6c2d6",
        "accent": "#2563eb",
        "accent_hover": "#3b82f6",
        "accent_pressed": "#1d4ed8",
        "accent_border": "#60a5fa",
        "disabled_bg": "#cbd5e1",
        "menu_bar_bg": "#ffffff",
        "menu_bar_text": "#1f2937",
        "menu_bar_hover": "#e5ebf5",
        "canvas_bg": "#fbfcfe",
        "grid_minor": "#e1e6ef",
        "grid_major": "#c8d1df",
        "node_bg": "#ffffff",
        "node_highlight": "#4a90ff",
        "node_text": "#172033",
        "node_desc": "#667085",
        "node_count": "#2f7d4a",
        "conn_badge_bg": (255, 255, 255, 235),
        "conn_badge_text": "#1f2937",
        "status_text": "#667085",
        "log_bg": "#ffffff",
        "output_bg": "#f8fafc",
        "menu_border": "#c8d2e3",
        "scroll_bg": "#edf2f7",
    },
}
CURRENT_THEME_NAME = "dark"


def get_theme_palette(theme_name: Optional[str] = None) -> Dict[str, Any]:
    return THEMES.get(theme_name or CURRENT_THEME_NAME, THEMES["dark"])


def set_current_theme_name(theme_name: str):
    global CURRENT_THEME_NAME
    CURRENT_THEME_NAME = theme_name if theme_name in THEMES else "dark"


def build_dialog_stylesheet(theme_name: Optional[str] = None) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QDialog, QMessageBox, QFileDialog {{
            background-color: {palette['panel_bg']};
            color: {palette['text']};
        }}
        QDialog QLabel, QMessageBox QLabel, QFileDialog QLabel {{
            color: {palette['text']};
            background: transparent;
        }}
        QDialog QPushButton, QMessageBox QPushButton, QFileDialog QPushButton {{
            background-color: {palette['accent']};
            color: white;
            border: 1px solid {palette['accent_border']};
            border-radius: 6px;
            padding: 8px 16px;
            min-width: 96px;
            font-weight: bold;
        }}
        QDialog QPushButton:hover, QMessageBox QPushButton:hover, QFileDialog QPushButton:hover {{
            background-color: {palette['accent_hover']};
        }}
        QDialog QPushButton:pressed, QMessageBox QPushButton:pressed, QFileDialog QPushButton:pressed {{
            background-color: {palette['accent_pressed']};
        }}
        QDialog QPushButton:disabled, QMessageBox QPushButton:disabled, QFileDialog QPushButton:disabled {{
            background-color: {palette['disabled_bg']};
            border-color: {palette['border']};
            color: {palette['muted']};
        }}
        QDialog QLineEdit, QDialog QTextEdit, QDialog QListWidget, QDialog QComboBox,
        QMessageBox QLineEdit, QFileDialog QLineEdit, QFileDialog QTextEdit, QFileDialog QListView,
        QFileDialog QTreeView, QFileDialog QComboBox, QFileDialog QStackedWidget, QFileDialog QFrame {{
            background-color: {palette['output_bg']};
            color: {palette['text']};
            border: 1px solid {palette['menu_border']};
            border-radius: 4px;
            selection-background-color: {palette['accent']};
            selection-color: white;
        }}
        QDialog QLineEdit, QDialog QTextEdit, QMessageBox QLineEdit, QFileDialog QLineEdit, QFileDialog QTextEdit {{
            padding: 8px;
        }}
        QDialog QComboBox::drop-down, QFileDialog QComboBox::drop-down {{
            border: none;
        }}
        QDialog QAbstractItemView, QFileDialog QAbstractItemView {{
            background-color: {palette['output_bg']};
            color: {palette['text']};
            selection-background-color: {palette['accent']};
            selection-color: white;
        }}
        QDialog QCheckBox, QFileDialog QCheckBox {{
            color: {palette['text']};
        }}
        QDialog QScrollBar:vertical, QFileDialog QScrollBar:vertical,
        QDialog QScrollBar:horizontal, QFileDialog QScrollBar:horizontal {{
            background: {palette['scroll_bg']};
            border: none;
        }}
        QDialog QScrollBar::handle:vertical, QFileDialog QScrollBar::handle:vertical,
        QDialog QScrollBar::handle:horizontal, QFileDialog QScrollBar::handle:horizontal {{
            background: {palette['border_strong']};
            border-radius: 4px;
        }}
        QMenu {{
            background-color: {palette['panel_bg']};
            color: {palette['text']};
            border: 1px solid {palette['menu_border']};
            padding: 6px;
        }}
        QMenu::item {{
            padding: 8px 20px;
            border-radius: 4px;
        }}
        QMenu::item:selected {{
            background-color: {palette['accent']};
            color: white;
        }}
        QToolTip {{
            background-color: {palette['panel_bg']};
            color: {palette['text']};
            border: 1px solid {palette['menu_border']};
            padding: 6px;
        }}
    """


def build_app_stylesheet(theme_name: Optional[str] = None) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QWidget {{
            color: {palette['text']};
            font-family: 'Microsoft YaHei', sans-serif;
            background-color: {palette['main_bg']};
        }}
    """ + build_dialog_stylesheet(theme_name)


def build_scrollbar_stylesheet(theme_name: Optional[str] = None, target: str = "*") -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        {target} QScrollBar:vertical {{
            background: transparent;
            width: 12px;
            margin: 2px 2px 2px 0;
            border: none;
        }}
        {target} QScrollBar::handle:vertical {{
            background: {palette['border_strong']};
            min-height: 36px;
            border-radius: 6px;
            border: 2px solid transparent;
        }}
        {target} QScrollBar::handle:vertical:hover {{
            background: {palette['accent']};
        }}
        {target} QScrollBar::add-line:vertical, {target} QScrollBar::sub-line:vertical {{
            height: 0px;
            border: none;
            background: transparent;
        }}
        {target} QScrollBar::add-page:vertical, {target} QScrollBar::sub-page:vertical {{
            background: transparent;
        }}
        {target} QScrollBar:horizontal {{
            background: transparent;
            height: 12px;
            margin: 0 2px 2px 2px;
            border: none;
        }}
        {target} QScrollBar::handle:horizontal {{
            background: {palette['border_strong']};
            min-width: 36px;
            border-radius: 6px;
            border: 2px solid transparent;
        }}
        {target} QScrollBar::handle:horizontal:hover {{
            background: {palette['accent']};
        }}
        {target} QScrollBar::add-line:horizontal, {target} QScrollBar::sub-line:horizontal {{
            width: 0px;
            border: none;
            background: transparent;
        }}
        {target} QScrollBar::add-page:horizontal, {target} QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}
    """


DIALOG_STYLESHEET = build_dialog_stylesheet("dark")
APP_STYLESHEET = build_app_stylesheet("dark")
