#!/usr/bin/env python3
"""
基于 PyQtGraph 的任务流编排管理器
实现类似 PyFlow 的可视化任务流程管理
支持节点编辑功能
"""

import json
import re
import sys
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal, Slot
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPen,
)
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pyflow_app.config import (
    DEFAULT_TERMINAL_TYPE,
    FLOW_CONFIG_PATH,
)
from pyflow_app.controllers import ExecutionController, FlowEditController
from pyflow_app.models import NodeStatus, TaskFlowManager
from pyflow_app.theme import (
    APP_STYLESHEET,
    CURRENT_THEME_NAME,
    THEMES,
    build_dialog_stylesheet,
    build_scrollbar_stylesheet,
    get_theme_palette,
)
from pyflow_app.ui import AddNodeDialog, ConnectNodesDialog, FlowScene, FlowView, NodeEditorPanel
from pyflow_app.ui.main_window_builders import build_canvas_area, build_menu_bar, build_right_panel, build_toolbar
from pyflow_app.utils import (
    ensure_unique_flow_id,
    get_connection_condition_label,
    load_node_templates,
    normalize_connection_condition,
    select_directory,
)
from pyflow_app.workspace import FlowWorkspace
from pyflow_app.window_helpers import DialogHelper, ThemeHelper, get_btn_style


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.workspace = FlowWorkspace()
        self.task_manager = self.workspace.task_manager
        self.flows: Dict[str, TaskFlowManager] = self.workspace.flows
        self.flow_order: List[str] = self.workspace.flow_order
        self.current_flow_id: Optional[str] = self.workspace.current_flow_id
        self.node_templates = load_node_templates()
        self.selected_node_id: Optional[str] = None
        self.execution_controller = ExecutionController(self)
        self.execution_controller.node_started.connect(self.on_node_started)
        self.execution_controller.node_finished.connect(self.on_node_finished)
        self.execution_controller.command_executing.connect(self.on_command_executing)
        self.execution_controller.command_finished.connect(self.on_command_finished)
        self.execution_controller.log_message.connect(self.on_log_message)
        self.execution_controller.output_message.connect(self.on_output_message)
        self.execution_controller.all_finished.connect(self.on_all_finished)
        self.execution_controller.finished.connect(self.on_worker_finished)
        self.execution_controller.stopped.connect(self.on_worker_stopped)
        self.edit_controller = FlowEditController(lambda: self.task_manager, lambda: self.selected_node_id)
        self.theme_helper = ThemeHelper()
        self.dialog_helper = DialogHelper()
        self.current_theme_name = self.workspace.theme_name
        self._undo_stack: List[Dict[str, Any]] = self.workspace.undo_stack
        self._redo_stack: List[Dict[str, Any]] = self.workspace.redo_stack
        self._restoring_history = self.workspace.restoring_history
        self.init_ui()
        self.load_startup_flow()

    def _sync_workspace_state(self):
        self.task_manager = self.workspace.task_manager
        self.flows = self.workspace.flows
        self.flow_order = self.workspace.flow_order
        self.current_flow_id = self.workspace.current_flow_id
        self.current_theme_name = self.workspace.theme_name
        self._undo_stack = self.workspace.undo_stack
        self._redo_stack = self.workspace.redo_stack
        self._restoring_history = self.workspace.restoring_history

    def init_ui(self):
        self.setWindowTitle("🔄 PyFlow 任务流编排管理器")
        self.setMinimumSize(1400, 900)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # 定义按钮样式函数（在 editor_panel 创建之前使用）
        def get_btn_style(color: str) -> str:
            return globals()["get_btn_style"](self.current_theme_name, color)
        splitter.addWidget(build_canvas_area(self, get_btn_style))
        splitter.addWidget(build_right_panel(self, get_btn_style))
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        build_menu_bar(self)
        build_toolbar(self)

        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪 - 点击节点查看详情并编辑")
        self.apply_theme(self.current_theme_name, announce=False, persist=False)

    def apply_theme(self, theme_name: str, announce: bool = True, persist: bool = True):
        self.theme_helper.apply(self, theme_name, announce=announce)
        if announce:
            self.statusBar.showMessage("已切换到黑色主题" if self.current_theme_name == "dark" else "已切换到白色主题")
        if persist and not self._restoring_history:
            self.save_config(show_message=False)

    def _show_message_box(self, icon, title: str, text: str,
                          buttons=QMessageBox.Ok,
                          default_button=QMessageBox.NoButton):
        return self.dialog_helper.message_box(self, self.current_theme_name, icon, title, text, buttons, default_button)

    def _show_info(self, title: str, text: str):
        return self._show_message_box(QMessageBox.Information, title, text)

    def _show_warning(self, title: str, text: str):
        return self._show_message_box(QMessageBox.Warning, title, text)

    def _show_error(self, title: str, text: str):
        return self._show_message_box(QMessageBox.Critical, title, text)

    def _show_question(self, title: str, text: str,
                       buttons=QMessageBox.Yes | QMessageBox.No,
                       default_button=QMessageBox.No):
        return self._show_message_box(
            QMessageBox.Question, title, text, buttons, default_button
        )

    def _select_open_file(self, title: str, name_filter: str, directory: str = "") -> str:
        return self.dialog_helper.select_open_file(self, self.current_theme_name, title, name_filter, directory)

    def _select_save_file(self, title: str, name_filter: str, directory: str = "") -> str:
        return self.dialog_helper.select_save_file(self, self.current_theme_name, title, name_filter, directory)

    def _prompt_flow_name(self, title: str, label: str, text: str = "") -> Optional[str]:
        return self.dialog_helper.prompt_flow_name(self, title, label, text)

    def _refresh_flow_selector(self):
        self.flow_list.blockSignals(True)
        self.flow_list.clear()
        for flow_id in self.flow_order:
            manager = self.flows[flow_id]
            item = QListWidgetItem(f"🗂️ {manager.flow_name}")
            item.setData(Qt.UserRole, flow_id)
            item.setToolTip(flow_id)
            self.flow_list.addItem(item)

        if self.current_flow_id:
            for index in range(self.flow_list.count()):
                item = self.flow_list.item(index)
                if item.data(Qt.UserRole) == self.current_flow_id:
                    self.flow_list.setCurrentItem(item)
                    break
        self.flow_list.blockSignals(False)

    def _set_current_flow(self, flow_id: str):
        if self.workspace.select_flow(flow_id) is None:
            return
        self._sync_workspace_state()
        self.editor_panel.task_manager = self.task_manager
        self.selected_node_id = None
        self.editor_panel.clear_node()
        self.log_text.clear()
        self.output_text.clear()
        self.flow_scene.load_flow(self.task_manager)
        self._refresh_flow_selector()
        self._update_undo_redo_actions()
        self.statusBar.showMessage(f"当前 Flow：{self.task_manager.flow_name}")

    def _load_flows_from_config(self, config: Dict[str, Any]):
        self.workspace.load_from_config(config)
        self._sync_workspace_state()
        self._set_current_flow(self.current_flow_id)
        self.apply_theme(self.current_theme_name, announce=False, persist=False)

    def _export_flows_config(self) -> Dict[str, Any]:
        return self.workspace.export_config()

    def _capture_history_snapshot(self) -> Dict[str, Any]:
        return self.workspace.capture_history_snapshot()

    def _push_undo_snapshot(self):
        self.workspace.push_undo_snapshot()
        self._sync_workspace_state()
        if hasattr(self, "undo_action"):
            self._update_undo_redo_actions()

    def _restore_history_snapshot(self, snapshot: Dict[str, Any]):
        self.workspace.restore_history_snapshot(snapshot)
        self._sync_workspace_state()
        self._set_current_flow(self.current_flow_id)
        self.reset_all()
        self._update_undo_redo_actions()

    def _update_undo_redo_actions(self):
        if hasattr(self, "undo_action"):
            self.undo_action.setEnabled(self.workspace.can_undo() and not self.execution_controller.is_running())
        if hasattr(self, "redo_action"):
            self.redo_action.setEnabled(self.workspace.can_redo() and not self.execution_controller.is_running())

    def undo(self):
        if self.execution_controller.is_running() or not self.workspace.undo():
            return
        self._sync_workspace_state()
        self._set_current_flow(self.current_flow_id)
        self.reset_all()
        self._update_undo_redo_actions()
        self.statusBar.showMessage("已撤销上一项修改")

    def redo(self):
        if self.execution_controller.is_running() or not self.workspace.redo():
            return
        self._sync_workspace_state()
        self._set_current_flow(self.current_flow_id)
        self.reset_all()
        self._update_undo_redo_actions()
        self.statusBar.showMessage("已重做上一项修改")

    def _get_selected_flow_id(self) -> Optional[str]:
        current_item = self.flow_list.currentItem()
        if current_item is None:
            return None
        return current_item.data(Qt.UserRole)

    def on_flow_selection_changed(self, current: Optional[QListWidgetItem], previous: Optional[QListWidgetItem]):
        del previous
        if current is None:
            return
        flow_id = current.data(Qt.UserRole)
        if flow_id and flow_id != self.current_flow_id:
            self._set_current_flow(flow_id)

    def show_flow_context_menu(self, pos):
        item = self.flow_list.itemAt(pos)
        if item is not None:
            self.flow_list.setCurrentItem(item)

        menu = QMenu(self)
        add_action = menu.addAction("➕ 新建 Flow")
        rename_action = menu.addAction("✏️ 重命名 Flow")
        delete_action = menu.addAction("🗑️ 删除 Flow")

        if self._get_selected_flow_id() is None:
            rename_action.setEnabled(False)
            delete_action.setEnabled(False)

        chosen_action = menu.exec(self.flow_list.viewport().mapToGlobal(pos))
        if chosen_action == add_action:
            self.add_flow()
        elif chosen_action == rename_action:
            self.rename_flow()
        elif chosen_action == delete_action:
            self.delete_flow()

    def add_flow(self):
        flow_name = self._prompt_flow_name("新增 Flow", "Flow 名称:")
        if not flow_name:
            return

        self._push_undo_snapshot()
        flow_id = self.workspace.add_flow(flow_name)
        self._sync_workspace_state()
        self._set_current_flow(flow_id)
        self._autosave()

    def rename_flow(self):
        flow_id = self._get_selected_flow_id() or self.current_flow_id
        if not flow_id:
            return

        manager = self.flows[flow_id]
        flow_name = self._prompt_flow_name("重命名 Flow", "Flow 名称:", manager.flow_name)
        if not flow_name:
            return

        self._push_undo_snapshot()
        self.workspace.rename_flow(flow_id, flow_name)
        self._sync_workspace_state()
        self._refresh_flow_selector()
        self._autosave()
        self.statusBar.showMessage(f"已重命名 Flow：{flow_name}")

    def delete_flow(self):
        flow_id = self._get_selected_flow_id() or self.current_flow_id
        if not flow_id:
            return

        if len(self.flow_order) == 1:
            self._show_warning("警告", "至少保留一个 Flow")
            return

        manager = self.flows[flow_id]
        reply = self._show_question(
            "删除 Flow",
            f"确定要删除 Flow '{manager.flow_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._push_undo_snapshot()
        next_flow_id = self.workspace.delete_flow(flow_id)
        self._sync_workspace_state()
        self._set_current_flow(next_flow_id)
        self._autosave()

    def _on_node_change_started(self, _node_id: str):
        self._push_undo_snapshot()

    def _on_node_changed(self, node_id: str):
        self.flow_scene.update_node_status(node_id)
        self._autosave()

    def _set_execution_state(self, is_running: bool):
        self.execute_node_btn.setEnabled(not is_running)
        self.execute_all_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)
        self._update_undo_redo_actions()

    def _validate_before_execution(self, node_ids: Optional[List[str]] = None) -> bool:
        errors = self.task_manager.validate_flow(node_ids)
        if not errors:
            return True
        error_text = "\n".join(f"{index + 1}. {message}" for index, message in enumerate(errors))
        self._show_error("执行前校验失败", error_text)
        return False

    @Slot(bool)
    def toggle_grid_visibility(self, visible: bool):
        self.flow_view.set_grid_visible(visible)
        self.statusBar.showMessage("已开启网格显示" if visible else "已关闭网格显示")

    def execute_selected_node(self):
        if not self.selected_node_id:
            self._show_warning("警告", "请先选择一个节点")
            return
        self.execute_nodes([self.selected_node_id], respect_skip=False)

    def execute_all_nodes(self):
        if not self._validate_before_execution():
            return
        execution_order = self.task_manager.get_execution_order()
        self.execute_nodes(execution_order, respect_skip=True, route_by_connections=True)

    def execute_nodes(self, node_ids: List[str], respect_skip: bool = True, route_by_connections: bool = False):
        if not node_ids:
            self._show_warning("警告", "没有可执行的任务")
            return

        if self.execution_controller.is_running():
            self._show_warning("警告", "当前已有 Flow 正在执行")
            return

        self.output_text.clear()
        self.tab_widget.setCurrentIndex(self.output_tab_index)
        self._set_execution_state(True)
        self.execution_controller.start(
            self.task_manager,
            node_ids,
            respect_skip=respect_skip,
            route_by_connections=route_by_connections,
        )
        self.statusBar.showMessage("正在执行任务...")

    def stop_execution(self):
        if not self.execution_controller.is_running():
            return
        self.execution_controller.stop()
        self.statusBar.showMessage("正在停止执行...")
        self.stop_btn.setEnabled(False)

    @Slot(str)
    def on_node_started(self, node_id: str):
        self.flow_scene.set_node_running(node_id, True)
        self.flow_scene.update_node_status(node_id)
        if self.selected_node_id == node_id:
            self.editor_panel.load_node(node_id)

    @Slot(str, bool)
    def on_node_finished(self, node_id: str, success: bool):
        self.flow_scene.set_node_running(node_id, False)
        self.flow_scene.update_node_status(node_id)
        if self.selected_node_id == node_id:
            self.editor_panel.load_node(node_id)

    @Slot(str, str, str)
    def on_command_executing(self, node_id: str, cmd_name: str, cmd: str):
        pass

    @Slot(str, str, bool, float)
    def on_command_finished(self, node_id: str, cmd_name: str, success: bool, duration: float):
        if self.selected_node_id == node_id:
            self.editor_panel.load_node(node_id)

    @Slot(str)
    def on_log_message(self, message: str):
        self.log_text.append(message)
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(str, str)
    def on_output_message(self, node_id: str, message: str):
        node = self.task_manager.nodes.get(node_id)
        prefix = f"[{node.name}] " if node else f"[{node_id}] "
        text = message if message.startswith("\n>>>") or message.startswith("\n===") else "".join(
            f"{prefix}{line}\n" if line else "\n" for line in message.splitlines()
        )
        self.output_text.insertPlainText(text)
        scrollbar = self.output_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(bool)
    def on_all_finished(self, all_success: bool):
        pass

    @Slot()
    def on_worker_stopped(self):
        self.statusBar.showMessage("执行已停止")

    @Slot()
    def on_worker_finished(self):
        was_stopped = self.execution_controller.execution_was_stopped
        self._set_execution_state(False)
        self.execution_controller.execution_was_stopped = False
        self.statusBar.showMessage("执行已停止" if was_stopped else "执行完成")

    def reset_all(self):
        self.task_manager.reset_status()
        self.flow_scene.load_flow(self.task_manager)
        self.log_text.clear()
        self.output_text.clear()
        self.selected_node_id = None
        self.statusBar.showMessage("已重置所有状态")

    def _load_config_file(self, filepath: str):
        self.workspace.load_from_file(filepath)
        self.workspace.reset_history()
        self._sync_workspace_state()
        self._set_current_flow(self.current_flow_id)
        self.reset_all()
        self._update_undo_redo_actions()
        self.statusBar.showMessage(f"已从 {filepath} 加载配置")

    def load_startup_flow(self):
        config_path = str(FLOW_CONFIG_PATH)
        if FLOW_CONFIG_PATH.exists():
            try:
                self._load_config_file(config_path)
                return
            except Exception as e:
                self.load_sample_flow()
                self.statusBar.showMessage(
                    f"自动加载 {FLOW_CONFIG_PATH.name} 失败，已回退到示例流程: {e}"
                )
                return

        self.load_sample_flow()
        self.statusBar.showMessage(f"未找到 {FLOW_CONFIG_PATH.name}，已加载示例流程")

    def load_config(self):
        filepath = self._select_open_file(
            "加载配置", "JSON Files (*.json);;All Files (*)"
        )
        if filepath:
            try:
                self._load_config_file(filepath)
            except Exception as e:
                self._show_error("错误", f"加载配置失败：{e}")

    def _autosave(self):
        self.save_config(show_message=False)

    def save_config(self, show_message: bool = True):
        filepath = str(FLOW_CONFIG_PATH)
        try:
            self.workspace.save_to_file(filepath)
            if show_message:
                self.statusBar.showMessage(f"已保存到 {filepath}")
        except Exception as e:
            self._show_error("错误", f"保存配置失败：{e}")

    def load_sample_flow(self):
        self.workspace.load_sample_flow()
        self._sync_workspace_state()
        self._set_current_flow(self.current_flow_id)
        self.reset_all()
        self._update_undo_redo_actions()
        self.statusBar.showMessage("已加载示例流程 - 点击节点进行编辑")

    def on_node_clicked(self, node_id: str):
        """节点被点击"""
        self.selected_node_id = node_id
        self.editor_panel.load_node(node_id)
        # 切换到编辑标签页
        self.tab_widget.setCurrentIndex(0)
        self.statusBar.showMessage(f"已选择节点：{self.task_manager.nodes[node_id].name}")

    def _get_new_node_position(self) -> Dict[str, float]:
        if self.selected_node_id and self.selected_node_id in self.task_manager.nodes:
            selected_node = self.task_manager.nodes[self.selected_node_id]
            if selected_node.position:
                return {
                    "x": float(selected_node.position.get("x", 50.0)),
                    "y": float(selected_node.position.get("y", 50.0)) + 230.0,
                }

        if self.task_manager.node_order:
            last_node = self.task_manager.nodes[self.task_manager.node_order[-1]]
            if last_node.position:
                return {
                    "x": float(last_node.position.get("x", 50.0)),
                    "y": float(last_node.position.get("y", 50.0)) + 230.0,
                }

        return {"x": 50.0, "y": 50.0}

    def _connect_nodes(self, source_id: str, target_id: str, insert_into_chain: bool = False,
                       condition: str = "success"):
        self.edit_controller.connect_nodes(source_id, target_id, insert_into_chain, condition)

    def connect_nodes_dialog(self):
        if len(self.task_manager.node_order) < 2:
            self._show_warning("警告", "至少需要两个节点才能建立连接")
            return

        dialog = ConnectNodesDialog(self.task_manager, self.selected_node_id, self)
        if dialog.exec() != QDialog.Accepted:
            return

        connection_data = dialog.get_connection_data()
        source_id = connection_data["source_id"]
        target_id = connection_data["target_id"]
        condition = connection_data["condition"]

        if self.task_manager.find_connection(source_id, target_id, condition) is not None and not connection_data["insert_into_chain"]:
            self._show_warning("警告", "这两个节点已经连接，无需重复添加")
            return

        self._push_undo_snapshot()
        self.edit_controller.connect_nodes(source_id, target_id, connection_data["insert_into_chain"], condition)
        self.flow_scene.load_flow(self.task_manager)
        self.on_node_clicked(target_id)
        self._autosave()
        self.statusBar.showMessage(
            f"已连接节点：{self.task_manager.nodes[source_id].name} -[{get_connection_condition_label(condition)}]-> {self.task_manager.nodes[target_id].name}"
        )

    @Slot(str, str)
    def create_connection_from_drag(self, source_id: str, target_id: str):
        if source_id == target_id:
            return

        if self.task_manager.find_connection(source_id, target_id, "success") is not None:
            self.statusBar.showMessage(
                f"连接已存在：{self.task_manager.nodes[source_id].name} -> {self.task_manager.nodes[target_id].name}"
            )
            return

        self._push_undo_snapshot()
        self.edit_controller.connect_nodes(source_id, target_id, insert_into_chain=False, condition="success")
        self.flow_scene.load_flow(self.task_manager)
        self.on_node_clicked(target_id)
        self._autosave()
        self.statusBar.showMessage(
            f"已连接节点：{self.task_manager.nodes[source_id].name} -> {self.task_manager.nodes[target_id].name}"
        )

    @Slot(str, str, str)
    def delete_connection(self, source_id: str, target_id: str, condition: str):
        if self.task_manager.find_connection(source_id, target_id, condition) is None:
            return

        source_name = self.task_manager.nodes.get(source_id).name if source_id in self.task_manager.nodes else source_id
        target_name = self.task_manager.nodes.get(target_id).name if target_id in self.task_manager.nodes else target_id
        condition_label = get_connection_condition_label(condition)
        reply = self._show_question(
            "删除连接",
            f"确定要删除连接 '{source_name} -[{condition_label}]-> {target_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self._push_undo_snapshot()
        self.edit_controller.delete_connection(source_id, target_id, condition)
        self.flow_scene.load_flow(self.task_manager)
        self._autosave()
        self.statusBar.showMessage(f"已删除连接：{source_name} -[{condition_label}]-> {target_name}")

    @Slot(str, str, str, str)
    def update_connection_condition(self, source_id: str, target_id: str, old_condition: str, new_condition: str):
        old_condition = normalize_connection_condition(old_condition)
        new_condition = normalize_connection_condition(new_condition)
        if old_condition == new_condition:
            return

        connection = self.task_manager.find_connection(source_id, target_id, old_condition)
        if connection is None:
            return

        if self.task_manager.find_connection(source_id, target_id, new_condition) is not None:
            source_name = self.task_manager.nodes.get(source_id).name if source_id in self.task_manager.nodes else source_id
            target_name = self.task_manager.nodes.get(target_id).name if target_id in self.task_manager.nodes else target_id
            self._show_warning(
                "修改失败",
                f"连接 '{source_name} -> {target_name}' 已存在条件“{get_connection_condition_label(new_condition)}”。",
            )
            return

        self._push_undo_snapshot()
        self.edit_controller.update_connection_condition(source_id, target_id, old_condition, new_condition)
        self.flow_scene.load_flow(self.task_manager)
        self._autosave()
        source_name = self.task_manager.nodes.get(source_id).name if source_id in self.task_manager.nodes else source_id
        target_name = self.task_manager.nodes.get(target_id).name if target_id in self.task_manager.nodes else target_id
        self.statusBar.showMessage(
            f"已更新连接条件：{source_name} -[{get_connection_condition_label(new_condition)}]-> {target_name}"
        )

    def add_new_node(self):
        """添加新节点"""
        self.node_templates = load_node_templates()
        selected_name = ""
        if self.selected_node_id and self.selected_node_id in self.task_manager.nodes:
            selected_name = self.task_manager.nodes[self.selected_node_id].name

        dialog = AddNodeDialog(
            self.task_manager.nodes.keys(),
            self.node_templates,
            selected_name,
            self,
        )
        if dialog.exec() != QDialog.Accepted:
            return

        self._push_undo_snapshot()
        node_data = dialog.get_node_data()
        node = self.edit_controller.add_node(node_data, self._get_new_node_position())

        self.flow_scene.load_flow(self.task_manager)
        self.on_node_clicked(node.id)
        self._autosave()
        self.statusBar.showMessage(f"已添加节点：{node.name}")

    def copy_selected_node(self):
        """复制当前选中的节点。"""
        if not self.selected_node_id or self.selected_node_id not in self.task_manager.nodes:
            self._show_warning("警告", "请先选择一个要复制的节点")
            return

        self._push_undo_snapshot()
        source_node = self.task_manager.nodes[self.selected_node_id]
        copied_node = self.edit_controller.copy_selected_node(self._get_new_node_position)
        self.flow_scene.load_flow(self.task_manager)
        self.on_node_clicked(copied_node.id)
        self._autosave()
        self.statusBar.showMessage(f"已复制节点：{source_node.name} -> {copied_node.name}")

    def delete_selected_node(self):
        """删除选中的节点"""
        if not self.selected_node_id:
            self._show_warning("警告", "请先选择一个节点")
            return

        # 确认删除
        reply = self._show_question(
            "确认删除",
            f"确定要删除节点 '{self.task_manager.nodes[self.selected_node_id].name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            self._push_undo_snapshot()
            self.edit_controller.delete_selected_node()
            self.flow_scene.load_flow(self.task_manager)

            # 清空选择
            self.selected_node_id = None
            self._autosave()
            self.statusBar.showMessage("节点已删除")


def main():
    QApplication.setAttribute(Qt.AA_DontUseNativeDialogs, True)
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLESHEET)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
