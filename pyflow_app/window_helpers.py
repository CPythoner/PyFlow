from typing import Optional

from PySide6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from .theme import THEMES, build_app_stylesheet, build_dialog_stylesheet, get_theme_palette, set_current_theme_name


def get_btn_style(theme_name: str, color: str) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QPushButton {{
            background-color: {color};
            color: white;
            padding: 8px 16px;
            border-radius: 5px;
            font-weight: bold;
            border: 1px solid {palette['border']};
        }}
        QPushButton:hover {{
            background-color: {color}dd;
        }}
    """


def get_flow_list_style(theme_name: str) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QListWidget {{
            background-color: {palette['panel_bg']};
            color: {palette['text']};
            border: 1px solid {palette['border']};
            border-radius: 6px;
            padding: 6px;
            outline: 0;
        }}
        QListWidget::item {{
            background-color: {palette['panel_alt_bg']};
            border: 1px solid {palette['border']};
            border-radius: 5px;
            padding: 10px 12px;
            margin: 0 0 6px 0;
        }}
        QListWidget::item:selected {{
            background-color: {palette['accent']};
            color: white;
            border: 2px solid {palette['accent_border']};
        }}
        QListWidget::item:hover {{
            background-color: {palette['panel_hover_bg']};
            border: 1px solid {palette['border_strong']};
        }}
    """


def get_tab_style(theme_name: str) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QTabWidget::pane {{
            border: 1px solid {palette['border']};
            border-radius: 5px;
        }}
        QTabBar::tab {{
            background-color: {palette['panel_bg']};
            color: {palette['text']};
            padding: 10px 20px;
            border: 1px solid {palette['border']};
            border-radius: 5px 5px 0 0;
        }}
        QTabBar::tab:selected {{
            background-color: {palette['accent']};
            color: white;
        }}
    """


def get_log_style(theme_name: str) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QTextEdit {{
            background-color: {palette['log_bg']};
            color: {palette['text']};
            border: none;
            font-family: Consolas, monospace;
            font-size: 11px;
        }}
    """


def get_output_style(theme_name: str) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QTextEdit {{
            background-color: {palette['output_bg']};
            color: {palette['text']};
            border: none;
            font-family: Consolas, 'Microsoft YaHei UI', monospace;
            font-size: 11px;
        }}
    """


def get_menu_bar_style(theme_name: str) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QMenuBar {{
            background-color: {palette['menu_bar_bg']};
            color: {palette['menu_bar_text']};
            border-bottom: 1px solid {palette['menu_border']};
            padding: 6px 10px;
            font-size: 14px;
        }}
        QMenuBar::item {{
            background: transparent;
            padding: 6px 12px;
            margin-right: 2px;
            border-radius: 4px;
        }}
        QMenuBar::item:selected {{
            background-color: {palette['menu_bar_hover']};
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
    """


def get_toolbar_style(theme_name: str) -> str:
    palette = get_theme_palette(theme_name)
    return f"""
        QToolBar {{
            background-color: {palette['panel_bg']};
            border: none;
            padding: 5px;
        }}
        QToolButton {{
            color: {palette['text']};
            border: none;
            padding: 5px 10px;
            border-radius: 3px;
        }}
        QToolButton:hover {{
            background-color: {palette['panel_hover_bg']};
        }}
    """


class ThemeHelper:
    def apply(self, window, theme_name: str, announce: bool = True):
        resolved = theme_name if theme_name in THEMES else "dark"
        window.current_theme_name = resolved
        window.workspace.theme_name = resolved
        set_current_theme_name(resolved)
        palette = get_theme_palette(resolved)
        app = QApplication.instance()
        if isinstance(app, QApplication):
            app.setStyleSheet(build_app_stylesheet(resolved))

        window.setStyleSheet(f"QMainWindow {{ background-color: {palette['main_bg']}; }}")
        window.menuBar().setStyleSheet(get_menu_bar_style(resolved))
        if hasattr(window, "toolbar"):
            window.toolbar.setStyleSheet(get_toolbar_style(resolved))
        window.flow_sidebar.setStyleSheet(
            f"QFrame {{ background-color: {palette['sidebar_bg']}; border-right: 1px solid {palette['menu_border']}; }}"
        )
        window.flow_sidebar_title.setStyleSheet(f"color: {palette['text']};")
        window.flow_sidebar_desc.setStyleSheet(f"color: {palette['muted']};")
        window.flow_list.setStyleSheet(get_flow_list_style(resolved))
        window.flow_header.setStyleSheet(f"color: {palette['text']}; padding: 15px; background-color: {palette['panel_bg']};")
        window.add_flow_btn.setStyleSheet(get_btn_style(resolved, "#198754"))
        window.rename_flow_btn.setStyleSheet(get_btn_style(resolved, "#ffc107"))
        window.delete_flow_btn.setStyleSheet(get_btn_style(resolved, "#dc3545"))
        window.add_node_btn.setStyleSheet(get_btn_style(resolved, "#198754"))
        window.copy_node_btn.setStyleSheet(get_btn_style(resolved, "#20c997"))
        window.connect_node_btn.setStyleSheet(get_btn_style(resolved, "#fd7e14"))
        window.delete_node_btn.setStyleSheet(get_btn_style(resolved, "#dc3545"))
        window.tab_widget.setStyleSheet(get_tab_style(resolved))
        window.log_text.setStyleSheet(get_log_style(resolved))
        window.output_text.setStyleSheet(get_output_style(resolved))
        window.reset_btn.setStyleSheet(get_btn_style(resolved, "#6c757d"))
        window.execute_node_btn.setStyleSheet(get_btn_style(resolved, "#198754"))
        window.execute_all_btn.setStyleSheet(get_btn_style(resolved, palette["accent"]))
        window.stop_btn.setStyleSheet(get_btn_style(resolved, "#dc3545"))
        window.statusBar.setStyleSheet(f"color: {palette['status_text']};")
        window.flow_scene.set_theme(resolved)
        window.flow_view.set_theme(resolved)
        window.editor_panel.apply_theme(resolved)
        if hasattr(window, "dark_theme_action"):
            window.dark_theme_action.setChecked(resolved == "dark")
        if hasattr(window, "light_theme_action"):
            window.light_theme_action.setChecked(resolved == "light")
        if announce:
            window.statusBar.showMessage("已切换到黑色主题" if resolved == "dark" else "已切换到白色主题")


class DialogHelper:
    def message_box(self, parent, theme_name: str, icon, title: str, text: str, buttons=QMessageBox.Ok, default_button=QMessageBox.NoButton):
        box = QMessageBox(parent)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.NoButton:
            box.setDefaultButton(default_button)
        box.setStyleSheet(build_dialog_stylesheet(theme_name))
        return box.exec()

    def select_open_file(self, parent, theme_name: str, title: str, name_filter: str, directory: str = "") -> str:
        dialog = QFileDialog(parent, title, directory, name_filter)
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setStyleSheet(build_dialog_stylesheet(theme_name))
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                return files[0]
        return ""

    def select_save_file(self, parent, theme_name: str, title: str, name_filter: str, directory: str = "") -> str:
        dialog = QFileDialog(parent, title, directory, name_filter)
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setStyleSheet(build_dialog_stylesheet(theme_name))
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                return files[0]
        return ""

    def prompt_flow_name(self, parent, title: str, label: str, text: str = "") -> Optional[str]:
        value, ok = QInputDialog.getText(parent, title, label, text=text)
        value = value.strip()
        return value if ok and value else None
