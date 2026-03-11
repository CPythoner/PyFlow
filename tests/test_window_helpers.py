import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QMainWindow

from pyflow_app.ui.main_window_builders import build_canvas_area, build_flow_sidebar, build_menu_bar, build_right_panel, build_toolbar
from pyflow_app.window_helpers import DialogHelper, get_btn_style, get_flow_list_style


class DummyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.called = []
        self.undo_action = self.menuBar().addAction("undo")
        self.redo_action = self.menuBar().addAction("redo")

    def add_flow(self):
        self.called.append("add_flow")

    def rename_flow(self):
        self.called.append("rename_flow")

    def delete_flow(self):
        self.called.append("delete_flow")

    def on_flow_selection_changed(self, *args):
        self.called.append("selection")

    def show_flow_context_menu(self, *args):
        self.called.append("context")

    def load_config(self):
        self.called.append("load_config")

    def save_config(self):
        self.called.append("save_config")

    def load_sample_flow(self):
        self.called.append("load_sample_flow")

    def undo(self):
        self.called.append("undo")

    def redo(self):
        self.called.append("redo")

    def add_new_node(self):
        self.called.append("add_new_node")

    def copy_selected_node(self):
        self.called.append("copy_selected_node")

    def connect_nodes_dialog(self):
        self.called.append("connect_nodes_dialog")

    def delete_selected_node(self):
        self.called.append("delete_selected_node")

    def toggle_grid_visibility(self, checked):
        self.called.append(("toggle_grid", checked))

    def apply_theme(self, theme_name):
        self.called.append(("apply_theme", theme_name))

    class _FlowView:
        @staticmethod
        def is_grid_visible():
            return True

    flow_view = _FlowView()

    def on_node_clicked(self, *args):
        self.called.append("on_node_clicked")

    def _on_node_change_started(self, *args):
        self.called.append("node_change_started")

    def _on_node_changed(self, *args):
        self.called.append("node_changed")

    def update_connection_condition(self, *args):
        self.called.append("update_connection_condition")

    def delete_connection(self, *args):
        self.called.append("delete_connection")

    def create_connection_from_drag(self, *args):
        self.called.append("create_connection_from_drag")

    task_manager = None

    def execute_selected_node(self):
        self.called.append("execute_selected_node")

    def execute_all_nodes(self):
        self.called.append("execute_all_nodes")

    def reset_all(self):
        self.called.append("reset_all")

    def stop_execution(self):
        self.called.append("stop_execution")


class WindowHelpersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_style_helpers_include_expected_colors(self):
        self.assertIn("#198754", get_btn_style("dark", "#198754"))
        self.assertIn("QListWidget", get_flow_list_style("light"))

    def test_dialog_helper_prompt_flow_name_trims_value(self):
        helper = DialogHelper()
        with patch("pyflow_app.window_helpers.QInputDialog.getText", return_value=("  Demo  ", True)):
            self.assertEqual(helper.prompt_flow_name(None, "title", "label"), "Demo")

    def test_builders_create_sidebar_and_toolbar(self):
        window = DummyWindow()
        sidebar = build_flow_sidebar(window, lambda color: f"style:{color}")
        build_menu_bar(window)
        toolbar = build_toolbar(window)

        self.assertIs(window.flow_sidebar, sidebar)
        self.assertEqual(window.add_flow_btn.toolTip(), "新建 Flow")
        self.assertIs(window.toolbar, toolbar)
        self.assertGreaterEqual(len(toolbar.actions()), 5)

        window.add_flow_btn.click()
        self.assertIn("add_flow", window.called)

    def test_menu_builder_creates_actions(self):
        window = DummyWindow()
        menu_bar = build_menu_bar(window)

        self.assertIsNotNone(window.undo_action)
        self.assertIsNotNone(window.redo_action)
        self.assertIsNotNone(window.toggle_grid_action)
        self.assertIn("文件", [action.text() for action in menu_bar.actions()])

    def test_canvas_and_right_panel_builders(self):
        window = DummyWindow()
        canvas = build_canvas_area(window, lambda color: f"style:{color}")
        right = build_right_panel(window, lambda color: f"style:{color}")

        self.assertIsNotNone(canvas)
        self.assertIsNotNone(right)
        self.assertIsNotNone(window.flow_scene)
        self.assertIsNotNone(window.flow_view)
        self.assertIsNotNone(window.editor_panel)
        self.assertIsNotNone(window.tab_widget)
        self.assertEqual(window.output_tab_index, 2)


if __name__ == "__main__":
    unittest.main()
