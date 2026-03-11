from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..config import DEFAULT_TERMINAL_TYPE, TERMINAL_TYPE_OPTIONS
from ..models import Command, NodeStatus, TaskFlowManager
from ..theme import CURRENT_THEME_NAME, THEMES, build_dialog_stylesheet, build_scrollbar_stylesheet, get_theme_palette
from ..utils import normalize_terminal_type, select_directory


class NodeEditorPanel(QWidget):
    """节点编辑面板"""

    node_change_started = Signal(str)
    node_changed = Signal(str)
    save_requested = Signal()
    execute_requested = Signal()

    def __init__(self, task_manager: TaskFlowManager):
        super().__init__()
        self.task_manager = task_manager
        self.current_node_id: Optional[str] = None
        self._is_loading = False
        self.theme_name = CURRENT_THEME_NAME
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.basic_group = QGroupBox("📋 基本信息")
        self.basic_group.setStyleSheet(self._get_group_style())
        basic_layout = QFormLayout(self.basic_group)

        self.node_id_edit = QLineEdit()
        self.node_id_edit.setStyleSheet(self._get_input_style())
        self.node_id_edit.setReadOnly(True)
        basic_layout.addRow("节点 ID:", self.node_id_edit)

        self.node_name_edit = QLineEdit()
        self.node_name_edit.setStyleSheet(self._get_input_style())
        self.node_name_edit.textChanged.connect(self._on_name_changed)
        basic_layout.addRow("节点名称:", self.node_name_edit)

        self.icon_combo = QComboBox()
        self.icon_combo.setStyleSheet(self._get_input_style())
        self.icon_combo.addItems(["📦", "", "🧮", "📋", "🤖", "", "⚙️", "🔧", "", "🚀", "✅", "❌"])
        self.icon_combo.currentTextChanged.connect(self._on_icon_changed)
        basic_layout.addRow("图标:", self.icon_combo)

        self.desc_edit = QTextEdit()
        self.desc_edit.setStyleSheet(self._get_input_style())
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.textChanged.connect(self._on_desc_changed)
        basic_layout.addRow("描述:", self.desc_edit)
        layout.addWidget(self.basic_group)

        self.config_group = QGroupBox("⚙️ 配置")
        self.config_group.setStyleSheet(self._get_group_style())
        config_layout = QFormLayout(self.config_group)

        self.workdir_edit = QLineEdit()
        self.workdir_edit.setStyleSheet(self._get_input_style())
        self.workdir_edit.textChanged.connect(self._on_workdir_changed)
        self.workdir_browse_btn = QPushButton("浏览...")
        self.workdir_browse_btn.setStyleSheet(self._get_btn_style("#0d6efd"))
        self.workdir_browse_btn.clicked.connect(self._browse_workdir)
        workdir_layout = QHBoxLayout()
        workdir_layout.setContentsMargins(0, 0, 0, 0)
        workdir_layout.addWidget(self.workdir_edit)
        workdir_layout.addWidget(self.workdir_browse_btn)
        config_layout.addRow("工作目录:", workdir_layout)

        self.terminal_combo = QComboBox()
        self.terminal_combo.setStyleSheet(self._get_input_style())
        for terminal_value, terminal_label in TERMINAL_TYPE_OPTIONS:
            self.terminal_combo.addItem(terminal_label, terminal_value)
        self.terminal_combo.currentIndexChanged.connect(self._on_terminal_changed)
        config_layout.addRow("终端类型:", self.terminal_combo)

        self.continue_check = QCheckBox()
        self.continue_check.setStyleSheet("color: white;")
        self.continue_check.stateChanged.connect(self._on_continue_changed)
        config_layout.addRow("允许错误继续:", self.continue_check)

        self.skip_check = QCheckBox()
        self.skip_check.setStyleSheet("color: white;")
        self.skip_check.stateChanged.connect(self._on_skip_changed)
        config_layout.addRow("执行时跳过:", self.skip_check)

        self.status_label = QLabel("-")
        self.status_label.setStyleSheet("color: #888;")
        config_layout.addRow("状态:", self.status_label)
        layout.addWidget(self.config_group)

        self.cmd_group = QGroupBox("📝 命令列表")
        self.cmd_group.setStyleSheet(self._get_group_style())
        cmd_layout = QVBoxLayout(self.cmd_group)

        self.command_list = QListWidget()
        self.command_list.setStyleSheet(self._get_command_list_style())
        self.command_list.setMaximumHeight(200)
        self.command_list.setDragEnabled(True)
        self.command_list.setAcceptDrops(True)
        self.command_list.setDropIndicatorShown(True)
        self.command_list.setDragDropMode(QAbstractItemView.InternalMove)
        self.command_list.setDefaultDropAction(Qt.MoveAction)
        self.command_list.setDragDropOverwriteMode(False)
        self.command_list.itemSelectionChanged.connect(self._on_command_selection_changed)
        self.command_list.itemDoubleClicked.connect(self._on_command_double_clicked)
        self.command_list.model().rowsMoved.connect(self._on_command_rows_moved)
        cmd_layout.addWidget(self.command_list)

        cmd_btn_layout = QHBoxLayout()
        self.add_cmd_btn = QPushButton("➕ 添加命令")
        self.add_cmd_btn.setStyleSheet(self._get_btn_style("#198754"))
        self.add_cmd_btn.clicked.connect(self._add_command)
        cmd_btn_layout.addWidget(self.add_cmd_btn)

        self.remove_cmd_btn = QPushButton("➖ 删除选中命令")
        self.remove_cmd_btn.setStyleSheet(self._get_btn_style("#dc3545"))
        self.remove_cmd_btn.clicked.connect(self._remove_command)
        cmd_btn_layout.addWidget(self.remove_cmd_btn)

        self.edit_cmd_btn = QPushButton("✏️ 编辑命令")
        self.edit_cmd_btn.setStyleSheet(self._get_btn_style("#ffc107"))
        self.edit_cmd_btn.clicked.connect(self._edit_command)
        cmd_btn_layout.addWidget(self.edit_cmd_btn)
        cmd_layout.addLayout(cmd_btn_layout)
        layout.addWidget(self.cmd_group)

        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton("💾 保存修改")
        self.save_btn.setStyleSheet(self._get_btn_style("#0d6efd"))
        self.save_btn.clicked.connect(self._save_changes)
        btn_layout.addWidget(self.save_btn)

        self.execute_btn = QPushButton("▶️ 执行节点")
        self.execute_btn.setStyleSheet(self._get_btn_style("#198754"))
        self.execute_btn.clicked.connect(self._execute_node)
        btn_layout.addWidget(self.execute_btn)

        layout.addLayout(btn_layout)
        layout.addStretch()
        self.apply_theme(self.theme_name)

    def _get_group_style(self) -> str:
        palette = get_theme_palette(self.theme_name)
        return f"""
            QGroupBox {{
                color: {palette['text']};
                border: 1px solid {palette['border']};
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }}
        """

    def _get_input_style(self) -> str:
        palette = get_theme_palette(self.theme_name)
        return f"""
            QLineEdit, QTextEdit, QComboBox {{
                background-color: {palette['panel_bg']};
                color: {palette['text']};
                border: 1px solid {palette['border']};
                border-radius: 3px;
                padding: 5px;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 28px;
            }}
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {palette['panel_bg']};
                color: {palette['text']};
                border: 1px solid {palette['border_strong']};
                selection-background-color: {palette['accent']};
                selection-color: white;
                outline: 0;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 28px;
                padding: 6px 10px;
                background-color: {palette['panel_bg']};
                color: {palette['text']};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {palette['panel_hover_bg']};
                color: {palette['text']};
            }}
            QComboBox QAbstractItemView::item:selected {{
                background-color: {palette['accent']};
                color: white;
            }}
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {{
                border-color: {palette['accent']};
            }}
        """

    def _get_btn_style(self, color: str) -> str:
        palette = get_theme_palette(self.theme_name)
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

    def _get_command_list_style(self) -> str:
        palette = get_theme_palette(self.theme_name)
        return f"""
            QListWidget {{
                background-color: {palette['panel_bg']};
                color: {palette['text']};
                border: 2px solid {palette['border_strong']};
                border-radius: 6px;
                padding: 6px;
                outline: 0;
            }}
            QListWidget::item {{
                padding: 10px 12px;
                border: 1px solid {palette['border']};
                border-radius: 4px;
                margin: 0 0 6px 0;
                background-color: {palette['panel_alt_bg']};
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
        """ + build_scrollbar_stylesheet(self.theme_name, "QListWidget")

    def apply_theme(self, theme_name: str):
        self.theme_name = theme_name if theme_name in THEMES else "dark"
        palette = get_theme_palette(self.theme_name)
        self.basic_group.setStyleSheet(self._get_group_style())
        self.config_group.setStyleSheet(self._get_group_style())
        self.cmd_group.setStyleSheet(self._get_group_style())
        for widget in (self.node_id_edit, self.node_name_edit, self.icon_combo, self.desc_edit, self.workdir_edit, self.terminal_combo):
            widget.setStyleSheet(self._get_input_style())
        self.workdir_browse_btn.setStyleSheet(self._get_btn_style(palette["accent"]))
        self.continue_check.setStyleSheet(f"color: {palette['text']};")
        self.skip_check.setStyleSheet(f"color: {palette['text']};")
        self.command_list.setStyleSheet(self._get_command_list_style())
        self.add_cmd_btn.setStyleSheet(self._get_btn_style("#198754"))
        self.remove_cmd_btn.setStyleSheet(self._get_btn_style("#dc3545"))
        self.edit_cmd_btn.setStyleSheet(self._get_btn_style("#ffc107"))
        self.save_btn.setStyleSheet(self._get_btn_style(palette["accent"]))
        self.execute_btn.setStyleSheet(self._get_btn_style("#198754"))
        if self.current_node_id and self.current_node_id in self.task_manager.nodes:
            node = self.task_manager.nodes[self.current_node_id]
            self.status_label.setStyleSheet(f"color: {node.get_status_color().name()};")
        else:
            self.status_label.setStyleSheet(f"color: {palette['status_text']};")

    def load_node(self, node_id: str):
        if self.current_node_id and self.current_node_id != node_id:
            self._apply_form_to_current_node()
        node = self.task_manager.nodes.get(node_id)
        if not node:
            return

        self._is_loading = True
        try:
            self.current_node_id = node_id
            self.node_id_edit.setText(node.id)
            self.node_name_edit.setText(node.name)
            self.icon_combo.setCurrentText(node.icon)
            self.desc_edit.setText(node.description)
            self.workdir_edit.setText(node.working_dir or "")
            terminal_index = self.terminal_combo.findData(normalize_terminal_type(node.terminal_type))
            self.terminal_combo.setCurrentIndex(terminal_index if terminal_index >= 0 else 0)
            self.continue_check.setChecked(node.continue_on_error)
            self.skip_check.setChecked(node.skip_in_flow)
            self.status_label.setText(node.get_status_text())
            self.status_label.setStyleSheet(f"color: {node.get_status_color().name()};")

            self.command_list.clear()
            for i, cmd in enumerate(node.commands):
                item_text = f"{cmd.name}"
                if cmd.command:
                    item_text += f" - {cmd.command}"
                if cmd.status != NodeStatus.PENDING:
                    status_icon = {
                        NodeStatus.SUCCESS: "✅",
                        NodeStatus.FAILED: "❌",
                        NodeStatus.SKIPPED: "⏭️",
                    }.get(cmd.status, "●")
                    item_text = f"{status_icon} {item_text}"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, i)
                self.command_list.addItem(item)

            if not node.commands:
                self.command_list.addItem(QListWidgetItem("暂无命令"))
        finally:
            self._is_loading = False

    def clear_node(self):
        self._apply_form_to_current_node()
        self._is_loading = True
        try:
            self.current_node_id = None
            self.node_id_edit.clear()
            self.node_name_edit.clear()
            self.icon_combo.setCurrentIndex(0)
            self.desc_edit.clear()
            self.workdir_edit.clear()
            terminal_index = self.terminal_combo.findData(DEFAULT_TERMINAL_TYPE)
            self.terminal_combo.setCurrentIndex(terminal_index if terminal_index >= 0 else 0)
            self.continue_check.setChecked(False)
            self.skip_check.setChecked(False)
            self.status_label.setText("-")
            self.command_list.clear()
            self.command_list.addItem(QListWidgetItem("暂无命令"))
        finally:
            self._is_loading = False

    def _apply_form_to_current_node(self):
        if self._is_loading or not self.current_node_id:
            return
        node = self.task_manager.nodes.get(self.current_node_id)
        if node is None:
            return
        node.name = self.node_name_edit.text().strip() or node.name
        node.icon = self.icon_combo.currentText()
        node.description = self.desc_edit.toPlainText().strip()
        node.working_dir = self.workdir_edit.text().strip() or None
        node.terminal_type = normalize_terminal_type(self.terminal_combo.currentData())
        node.continue_on_error = self.continue_check.isChecked()
        node.skip_in_flow = self.skip_check.isChecked()

    def _notify_node_changed(self):
        if self.current_node_id and not self._is_loading:
            self.node_changed.emit(self.current_node_id)

    def _notify_node_change_started(self):
        if self.current_node_id and not self._is_loading:
            self.node_change_started.emit(self.current_node_id)

    def _on_name_changed(self, text: str):
        if self.current_node_id:
            self._notify_node_change_started()
            self.task_manager.nodes[self.current_node_id].name = text
            self._notify_node_changed()

    def _on_icon_changed(self, text: str):
        if self.current_node_id:
            self._notify_node_change_started()
            self.task_manager.nodes[self.current_node_id].icon = text
            self._notify_node_changed()

    def _on_desc_changed(self):
        if self.current_node_id:
            self._notify_node_change_started()
            self.task_manager.nodes[self.current_node_id].description = self.desc_edit.toPlainText()
            self._notify_node_changed()

    def _on_workdir_changed(self, text: str):
        if self.current_node_id:
            self._notify_node_change_started()
            self.task_manager.nodes[self.current_node_id].working_dir = text if text else None
            self._notify_node_changed()

    def _on_terminal_changed(self, _index):
        if self.current_node_id:
            self._notify_node_change_started()
            self.task_manager.nodes[self.current_node_id].terminal_type = normalize_terminal_type(self.terminal_combo.currentData())
            self._notify_node_changed()

    def _browse_workdir(self):
        directory = select_directory(self, "选择工作目录", self.workdir_edit.text().strip())
        if directory:
            self.workdir_edit.setText(directory)

    def _on_continue_changed(self, state):
        if self.current_node_id:
            self._notify_node_change_started()
            self.task_manager.nodes[self.current_node_id].continue_on_error = (state == Qt.Checked)
            self._notify_node_changed()

    def _on_skip_changed(self, state):
        if self.current_node_id:
            self._notify_node_change_started()
            self.task_manager.nodes[self.current_node_id].skip_in_flow = (state == Qt.Checked)
            self._notify_node_changed()

    def _on_command_selection_changed(self):
        pass

    def _on_command_rows_moved(self, _parent, _start, _end, _destination, _row):
        del _parent, _start, _end, _destination, _row
        self._sync_command_order_from_list()

    def _sync_command_order_from_list(self):
        if self._is_loading or not self.current_node_id:
            return
        node = self.task_manager.nodes.get(self.current_node_id)
        if node is None or not node.commands:
            return

        reordered_commands = []
        used_indexes = set()
        for row in range(self.command_list.count()):
            item = self.command_list.item(row)
            command_index = item.data(Qt.UserRole)
            if not isinstance(command_index, int):
                continue
            if 0 <= command_index < len(node.commands) and command_index not in used_indexes:
                reordered_commands.append(node.commands[command_index])
                used_indexes.add(command_index)

        if len(reordered_commands) != len(node.commands):
            return

        node.commands = reordered_commands
        for row in range(self.command_list.count()):
            self.command_list.item(row).setData(Qt.UserRole, row)
        self._notify_node_change_started()
        self._notify_node_changed()

    def _on_command_double_clicked(self, item: QListWidgetItem):
        del item
        self._edit_command()

    def _get_command_dialog_result(self, name: str = "", command: str = "") -> tuple:
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑命令")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet(build_dialog_stylesheet())

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("命令名称:"))
        name_edit = QLineEdit(name)
        layout.addWidget(name_edit)
        layout.addWidget(QLabel("命令内容:"))
        cmd_edit = QTextEdit(command)
        cmd_edit.setMaximumHeight(100)
        layout.addWidget(cmd_edit)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(dialog.reject)
        btn_layout.addWidget(cancel_btn)
        ok_btn = QPushButton("确定")
        ok_btn.clicked.connect(dialog.accept)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        if dialog.exec() == QDialog.Accepted:
            return name_edit.text(), cmd_edit.toPlainText().strip()
        return None, None

    def _add_command(self):
        if self.current_node_id:
            node = self.task_manager.nodes[self.current_node_id]
            self._notify_node_change_started()
            node.commands.append(Command(name="新命令", command="echo '新命令'"))
            self.load_node(self.current_node_id)
            self.node_changed.emit(self.current_node_id)

    def _remove_command(self):
        if self.current_node_id:
            node = self.task_manager.nodes[self.current_node_id]
            selected_items = self.command_list.selectedItems()
            if selected_items:
                index = selected_items[0].data(Qt.UserRole)
                if index is not None and 0 <= index < len(node.commands):
                    self._notify_node_change_started()
                    node.commands.pop(index)
                    self.load_node(self.current_node_id)
                    self.node_changed.emit(self.current_node_id)

    def _edit_command(self):
        if self.current_node_id:
            node = self.task_manager.nodes[self.current_node_id]
            selected_items = self.command_list.selectedItems()
            if selected_items:
                index = selected_items[0].data(Qt.UserRole)
                if index is not None and 0 <= index < len(node.commands):
                    cmd = node.commands[index]
                    new_name, new_command = self._get_command_dialog_result(cmd.name, cmd.command)
                    if new_name is not None:
                        self._notify_node_change_started()
                        cmd.name = new_name
                        cmd.command = new_command
                        self.load_node(self.current_node_id)
                        self.node_changed.emit(self.current_node_id)

    def _save_changes(self, persist: bool = True):
        if self.current_node_id:
            self._apply_form_to_current_node()
            self.node_changed.emit(self.current_node_id)
            if persist:
                self.save_requested.emit()

    def _execute_node(self):
        if self.current_node_id:
            self._save_changes(persist=False)
            self.execute_requested.emit()
