import re
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..config import CONNECTION_CONDITION_OPTIONS, DEFAULT_TERMINAL_TYPE, NODE_ICON_OPTIONS, TERMINAL_TYPE_OPTIONS
from ..models import TaskFlowManager
from ..theme import build_dialog_stylesheet, get_theme_palette
from ..utils import ensure_unique_node_id, normalize_connection_condition, normalize_terminal_type, select_directory


class AddNodeDialog(QDialog):
    """新增节点对话框。"""

    def __init__(self, existing_ids, templates=None, selected_node_name: str = "", parent=None):
        super().__init__(parent)
        self.existing_ids = set(existing_ids)
        self.templates = templates or []
        self.template_map = {
            template.get("id"): template
            for template in self.templates
            if template.get("id")
        }
        self.selected_node_name = selected_node_name
        self._node_id_touched = False
        self.template_commands: List[Dict[str, str]] = []

        self.setWindowTitle("添加节点")
        self.setMinimumWidth(560)
        self.setStyleSheet(build_dialog_stylesheet())
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        hint = QLabel("创建一个可立即编辑和执行的新节点。")
        hint.setStyleSheet(f"color: {get_theme_palette().get('muted')};")
        layout.addWidget(hint)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)

        self.template_combo = QComboBox()
        self.template_combo.addItem("自定义", None)
        for template in self.templates:
            label = f"{template.get('icon', '📦')} {template.get('name', '模板')}"
            self.template_combo.addItem(label, template.get("id"))
        self.template_combo.currentIndexChanged.connect(self._apply_selected_template)
        form.addRow("模板:", self.template_combo)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例如：数据清洗")
        self.name_edit.textChanged.connect(self._sync_node_id)
        form.addRow("节点名称:", self.name_edit)

        self.node_id_edit = QLineEdit()
        self.node_id_edit.setPlaceholderText("例如：data_cleaning")
        self.node_id_edit.textEdited.connect(self._mark_node_id_touched)
        form.addRow("节点 ID:", self.node_id_edit)

        self.icon_combo = QComboBox()
        self.icon_combo.addItems(NODE_ICON_OPTIONS)
        form.addRow("图标:", self.icon_combo)

        self.desc_edit = QTextEdit()
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.setPlaceholderText("节点用途说明，可选")
        form.addRow("描述:", self.desc_edit)

        self.workdir_edit = QLineEdit()
        self.workdir_edit.setPlaceholderText("工作目录，可选")
        self.workdir_browse_btn = QPushButton("浏览...")
        self.workdir_browse_btn.clicked.connect(self._browse_workdir)
        workdir_layout = QHBoxLayout()
        workdir_layout.setContentsMargins(0, 0, 0, 0)
        workdir_layout.addWidget(self.workdir_edit)
        workdir_layout.addWidget(self.workdir_browse_btn)
        form.addRow("工作目录:", workdir_layout)

        self.terminal_combo = QComboBox()
        for terminal_value, terminal_label in TERMINAL_TYPE_OPTIONS:
            self.terminal_combo.addItem(terminal_label, terminal_value)
        default_terminal_index = self.terminal_combo.findData(DEFAULT_TERMINAL_TYPE)
        self.terminal_combo.setCurrentIndex(default_terminal_index if default_terminal_index >= 0 else 0)
        form.addRow("终端类型:", self.terminal_combo)

        self.continue_check = QCheckBox("失败后继续后续节点")
        form.addRow("执行策略:", self.continue_check)
        layout.addLayout(form)

        if self.selected_node_name:
            self.connect_after_check = QCheckBox(f"自动连接到当前选中节点“{self.selected_node_name}”之后")
            self.connect_after_check.setChecked(True)
            layout.addWidget(self.connect_after_check)
        else:
            self.connect_after_check = None

        command_group = QGroupBox("首条命令")
        command_layout = QFormLayout(command_group)
        self.command_name_edit = QLineEdit("新命令")
        command_layout.addRow("命令名称:", self.command_name_edit)

        self.command_edit = QTextEdit()
        self.command_edit.setMaximumHeight(100)
        self.command_edit.setPlaceholderText("可留空，稍后再编辑")
        command_layout.addRow("命令内容:", self.command_edit)
        layout.addWidget(command_group)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _mark_node_id_touched(self, _text: str):
        self._node_id_touched = True

    def _sync_node_id(self, text: str):
        if self._node_id_touched:
            return
        self.node_id_edit.setText(ensure_unique_node_id(text or "node", self.existing_ids))

    def _apply_selected_template(self, _index=None):
        template_id = self.template_combo.currentData()
        if not template_id:
            self.template_commands = []
            return

        template = self.template_map.get(template_id)
        if not template:
            self.template_commands = []
            return

        default_name = template.get("default_name") or template.get("name", "")
        if default_name:
            self.name_edit.setText(default_name)

        icon = template.get("icon", "")
        if icon:
            if self.icon_combo.findText(icon) == -1:
                self.icon_combo.addItem(icon)
            self.icon_combo.setCurrentText(icon)

        self.desc_edit.setPlainText(template.get("description", ""))
        self.workdir_edit.setText(template.get("working_dir", ""))
        terminal_index = self.terminal_combo.findData(normalize_terminal_type(template.get("terminal_type")))
        self.terminal_combo.setCurrentIndex(terminal_index if terminal_index >= 0 else 0)
        self.continue_check.setChecked(bool(template.get("continue_on_error", False)))

        commands = template.get("commands", [])
        self.template_commands = [
            {
                "name": cmd.get("name", "新命令"),
                "command": cmd.get("command", ""),
            }
            for cmd in commands
            if cmd.get("command")
        ]
        first_command = self.template_commands[0] if self.template_commands else {}
        self.command_name_edit.setText(first_command.get("name", "新命令"))
        self.command_edit.setPlainText(first_command.get("command", ""))

    def _browse_workdir(self):
        directory = select_directory(self, "选择工作目录", self.workdir_edit.text().strip())
        if directory:
            self.workdir_edit.setText(directory)

    def _validate_and_accept(self):
        name = self.name_edit.text().strip()
        node_id = self.node_id_edit.text().strip()

        if not name:
            QMessageBox.warning(self, "校验失败", "节点名称不能为空。")
            return

        if not node_id:
            node_id = ensure_unique_node_id(name, self.existing_ids)
            self.node_id_edit.setText(node_id)

        if not re.fullmatch(r"[A-Za-z0-9_-]+", node_id):
            QMessageBox.warning(self, "校验失败", "节点 ID 只能包含字母、数字、下划线和中划线。")
            return

        if node_id in self.existing_ids:
            QMessageBox.warning(self, "校验失败", f"节点 ID “{node_id}” 已存在。")
            return

        self.accept()

    def get_node_data(self) -> Dict[str, Any]:
        command_text = self.command_edit.toPlainText().strip()
        commands = list(self.template_commands)
        if not commands and command_text:
            commands = [{
                "name": self.command_name_edit.text().strip() or "新命令",
                "command": command_text,
            }]
        return {
            "template_id": self.template_combo.currentData(),
            "node_id": self.node_id_edit.text().strip(),
            "name": self.name_edit.text().strip(),
            "icon": self.icon_combo.currentText(),
            "description": self.desc_edit.toPlainText().strip(),
            "working_dir": self.workdir_edit.text().strip(),
            "terminal_type": normalize_terminal_type(self.terminal_combo.currentData()),
            "continue_on_error": self.continue_check.isChecked(),
            "connect_after_selected": bool(self.connect_after_check and self.connect_after_check.isChecked()),
            "command_name": self.command_name_edit.text().strip() or "新命令",
            "command": command_text,
            "commands": commands,
        }


class ConnectNodesDialog(QDialog):
    """连接节点对话框。"""

    def __init__(self, task_manager: TaskFlowManager, selected_node_id: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.task_manager = task_manager
        self.selected_node_id = selected_node_id

        self.setWindowTitle("连接节点")
        self.setMinimumWidth(520)
        self.setStyleSheet(build_dialog_stylesheet())
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        hint = QLabel("选择起点和终点，建立节点之间的链路。")
        hint.setStyleSheet(f"color: {get_theme_palette().get('muted')};")
        layout.addWidget(hint)

        form = QFormLayout()
        self.source_combo = QComboBox()
        self.target_combo = QComboBox()

        for node_id in self.task_manager.node_order:
            node = self.task_manager.nodes[node_id]
            label = f"{node.icon} {node.name} ({node_id})"
            self.source_combo.addItem(label, node_id)
            self.target_combo.addItem(label, node_id)

        if self.selected_node_id:
            source_index = self.source_combo.findData(self.selected_node_id)
            target_index = self.target_combo.findData(self.selected_node_id)
            if source_index >= 0:
                self.source_combo.setCurrentIndex(source_index)
            if target_index >= 0 and self.target_combo.count() > 1:
                next_index = 0 if target_index != 0 else 1
                self.target_combo.setCurrentIndex(next_index)

        self.insert_into_chain_check = QCheckBox("插入到链路中，并同步调整执行顺序")
        self.insert_into_chain_check.setChecked(True)
        self.condition_combo = QComboBox()
        for condition_value, condition_label in CONNECTION_CONDITION_OPTIONS:
            self.condition_combo.addItem(condition_label, condition_value)
        self.condition_combo.currentIndexChanged.connect(self._on_condition_changed)

        form.addRow("源节点:", self.source_combo)
        form.addRow("目标节点:", self.target_combo)
        form.addRow("触发条件:", self.condition_combo)
        form.addRow("连接方式:", self.insert_into_chain_check)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._on_condition_changed(self.condition_combo.currentIndex())

    def _on_condition_changed(self, _index: int):
        is_success = normalize_connection_condition(self.condition_combo.currentData()) == "success"
        self.insert_into_chain_check.setEnabled(is_success)
        if not is_success:
            self.insert_into_chain_check.setChecked(False)

    def _validate_and_accept(self):
        if self.source_combo.currentData() == self.target_combo.currentData():
            QMessageBox.warning(self, "校验失败", "源节点和目标节点不能是同一个。")
            return
        self.accept()

    def get_connection_data(self) -> Dict[str, Any]:
        condition = normalize_connection_condition(self.condition_combo.currentData())
        return {
            "source_id": self.source_combo.currentData(),
            "target_id": self.target_combo.currentData(),
            "condition": condition,
            "insert_into_chain": self.insert_into_chain_check.isChecked() and condition == "success",
        }
