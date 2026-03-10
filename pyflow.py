#!/usr/bin/env python3
"""
基于 PyQtGraph 的任务流编排管理器
实现类似 PyFlow 的可视化任务流程管理
支持节点编辑功能
"""

import sys
import json
import re
import time
import locale
import subprocess
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from pathlib import Path
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QSplitter,
    QGroupBox, QFormLayout, QLineEdit, QCheckBox, QTextEdit, QListWidget, QListWidgetItem,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QMenu,
    QToolBar, QStatusBar, QDialog, QDialogButtonBox,
    QSizePolicy, QFrame, QScrollArea, QComboBox, QSpinBox, QTabWidget, QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QPointF, QRectF, QSize, QTimer
from PySide6.QtGui import (
    QFont, QColor, QPen, QBrush, QPainter, QPainterPath,
    QPainterPathStroker, QPolygonF, QIcon, QKeySequence, QTransform
)
from PySide6.QtGui import QAction


DIALOG_STYLESHEET = """
    QDialog, QMessageBox, QFileDialog {
        background-color: #232837;
        color: #f3f6fb;
    }
    QDialog QLabel, QMessageBox QLabel, QFileDialog QLabel {
        color: #f3f6fb;
        background: transparent;
    }
    QDialog QPushButton, QMessageBox QPushButton, QFileDialog QPushButton {
        background-color: #2563eb;
        color: white;
        border: 1px solid #60a5fa;
        border-radius: 6px;
        padding: 8px 16px;
        min-width: 96px;
        font-weight: bold;
    }
    QDialog QPushButton:hover, QMessageBox QPushButton:hover, QFileDialog QPushButton:hover {
        background-color: #3b82f6;
    }
    QDialog QPushButton:pressed, QMessageBox QPushButton:pressed, QFileDialog QPushButton:pressed {
        background-color: #1d4ed8;
    }
    QDialog QPushButton:disabled, QMessageBox QPushButton:disabled, QFileDialog QPushButton:disabled {
        background-color: #4b5563;
        border-color: #6b7280;
        color: #cbd5e1;
    }
    QDialog QLineEdit, QDialog QTextEdit, QDialog QListWidget, QDialog QComboBox,
    QMessageBox QLineEdit, QFileDialog QLineEdit, QFileDialog QTextEdit, QFileDialog QListView,
    QFileDialog QTreeView, QFileDialog QComboBox, QFileDialog QStackedWidget, QFileDialog QFrame {
        background-color: #161b26;
        color: #f3f6fb;
        border: 1px solid #3a4154;
        border-radius: 4px;
        selection-background-color: #2563eb;
        selection-color: white;
    }
    QDialog QLineEdit, QDialog QTextEdit, QMessageBox QLineEdit, QFileDialog QLineEdit, QFileDialog QTextEdit {
        padding: 8px;
    }
    QDialog QComboBox::drop-down, QFileDialog QComboBox::drop-down {
        border: none;
    }
    QDialog QAbstractItemView, QFileDialog QAbstractItemView {
        background-color: #161b26;
        color: #f3f6fb;
        selection-background-color: #2563eb;
        selection-color: white;
    }
    QDialog QCheckBox, QFileDialog QCheckBox {
        color: #f3f6fb;
    }
    QDialog QScrollBar:vertical, QFileDialog QScrollBar:vertical,
    QDialog QScrollBar:horizontal, QFileDialog QScrollBar:horizontal {
        background: #1b2030;
        border: none;
    }
    QDialog QScrollBar::handle:vertical, QFileDialog QScrollBar::handle:vertical,
    QDialog QScrollBar::handle:horizontal, QFileDialog QScrollBar::handle:horizontal {
        background: #4b5563;
        border-radius: 4px;
    }
    QMenu {
        background-color: #232837;
        color: #f3f6fb;
        border: 1px solid #3a4154;
        padding: 6px;
    }
    QMenu::item {
        padding: 8px 20px;
        border-radius: 4px;
    }
    QMenu::item:selected {
        background-color: #2563eb;
    }
    QToolTip {
        background-color: #232837;
        color: #f3f6fb;
        border: 1px solid #3a4154;
        padding: 6px;
    }
"""

APP_STYLESHEET = """
    QWidget {
        color: white;
        font-family: 'Microsoft YaHei', sans-serif;
    }
""" + DIALOG_STYLESHEET

NODE_ICON_OPTIONS = ["📦", "🌐", "🧮", "📋", "🤖", "📊", "⚙️", "🔥", "🚀", "✅", "▶️", "❌"]
NODE_TEMPLATES_PATH = Path(__file__).with_name("node_templates.json")
FLOW_CONFIG_PATH = Path(__file__).with_name("flow_config.json")
NODE_LOG_DIR = Path(__file__).with_name("logs")
DEFAULT_TERMINAL_TYPE = "cmd" if sys.platform.startswith("win") else "bash"
TERMINAL_TYPE_OPTIONS = [
    ("cmd", "CMD"),
    ("powershell", "PowerShell"),
    ("bash", "Bash"),
]


def slugify_node_id(text: str) -> str:
    """Convert free-form text to a safe node id."""
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", text.strip().lower())
    return slug.strip("_-") or "node"


def ensure_unique_node_id(base_id: str, existing_ids) -> str:
    """Generate a unique node id based on the provided base id."""
    candidate = slugify_node_id(base_id)
    if candidate not in existing_ids:
        return candidate

    counter = 1
    while f"{candidate}_{counter}" in existing_ids:
        counter += 1
    return f"{candidate}_{counter}"


def ensure_unique_flow_id(base_id: str, existing_ids) -> str:
    """Generate a unique flow id."""
    candidate = slugify_node_id(base_id) or "flow"
    if candidate not in existing_ids:
        return candidate

    counter = 1
    while f"{candidate}_{counter}" in existing_ids:
        counter += 1
    return f"{candidate}_{counter}"


def ensure_unique_node_name(base_name: str, existing_names) -> str:
    """Generate a unique node display name."""
    candidate = (base_name or "新节点").strip()
    if candidate not in existing_names:
        return candidate

    counter = 1
    while f"{candidate} {counter}" in existing_names:
        counter += 1
    return f"{candidate} {counter}"


def normalize_terminal_type(value: Optional[str]) -> str:
    """Normalize terminal type to a supported value."""
    if not value:
        return DEFAULT_TERMINAL_TYPE

    normalized = str(value).strip().lower()
    supported = {item[0] for item in TERMINAL_TYPE_OPTIONS}
    if normalized in supported:
        return normalized
    return DEFAULT_TERMINAL_TYPE


def select_directory(parent, title: str, directory: str = "") -> str:
    """Open a themed directory chooser."""
    dialog = QFileDialog(parent, title, directory or "")
    dialog.setFileMode(QFileDialog.Directory)
    dialog.setOption(QFileDialog.ShowDirsOnly, True)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setStyleSheet(DIALOG_STYLESHEET)
    if dialog.exec():
        files = dialog.selectedFiles()
        if files:
            return files[0]
    return ""


def load_node_templates(path: Path = NODE_TEMPLATES_PATH) -> List[Dict[str, Any]]:
    """Load node templates from JSON file."""
    if not path.exists():
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    templates = config.get("templates", [])
    if not isinstance(templates, list):
        return []

    normalized_templates = []
    for template in templates:
        if not isinstance(template, dict):
            continue

        commands = template.get("commands", [])
        if not isinstance(commands, list):
            commands = []
        terminal_type = (
            normalize_terminal_type(template.get("terminal_type"))
            if "terminal_type" in template
            else infer_terminal_type(
                str(template.get("name", "")),
                str(template.get("description", "")),
                commands,
            )
        )

        normalized_templates.append({
            "id": template.get("id", ""),
            "name": template.get("name", "未命名模板"),
            "default_name": template.get("default_name") or template.get("name", "新节点"),
            "icon": template.get("icon", "📦"),
            "description": template.get("description", ""),
            "working_dir": template.get("working_dir", ""),
            "continue_on_error": bool(template.get("continue_on_error", False)),
            "terminal_type": terminal_type,
            "commands": [
                {
                    "name": cmd.get("name", "新命令"),
                    "command": cmd.get("command", ""),
                }
                for cmd in commands
                if isinstance(cmd, dict)
            ],
        })

    return normalized_templates


def sanitize_filename(name: str) -> str:
    """Create a Windows-safe filename while keeping readable text."""
    cleaned = re.sub(r'[<>:"/\\\\|?*]+', "_", name.strip())
    cleaned = cleaned.rstrip(". ")
    return cleaned or "node"


def build_node_log_path(node_name: str, started_at: datetime) -> Path:
    """Build a per-node log file path."""
    NODE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = started_at.strftime("%Y%m%d-%H%M%S-%f")[:-3]
    return NODE_LOG_DIR / f"{sanitize_filename(node_name)}-{timestamp}.log"


def decode_process_output(data: bytes) -> str:
    """Decode subprocess output robustly across UTF-8/GBK/GB18030 consoles."""
    if not data:
        return ""

    encodings = ["utf-8", locale.getpreferredencoding(False), "gb18030"]
    tried = set()
    for encoding in encodings:
        if not encoding or encoding.lower() in tried:
            continue
        tried.add(encoding.lower())
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    return data.decode("utf-8", errors="replace")


def looks_like_powershell_command(command: str) -> bool:
    """Infer whether a command should run under PowerShell on Windows."""
    stripped = command.strip()
    if not stripped:
        return False

    lowered = stripped.lower()
    explicit_shells = (
        "powershell ",
        "powershell.exe ",
        "pwsh ",
        "pwsh.exe ",
        "cmd ",
        "cmd.exe ",
    )
    if lowered.startswith(explicit_shells):
        return False

    first_token = re.split(r"\s+", stripped, maxsplit=1)[0]
    if re.fullmatch(r"[A-Za-z]+-[A-Za-z][\w-]*", first_token):
        return True

    return stripped.startswith(("$", "@(", "@{", "[")) or "| " in stripped


def normalize_shell_command(command: str) -> str:
    """Normalize smart quotes copied from IME/editors into plain shell quotes."""
    return (
        command
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )


def infer_terminal_type(node_name: str, description: str, commands: List[Dict[str, Any]]) -> str:
    """Infer terminal type for legacy nodes/templates without an explicit setting."""
    combined_text = f"{node_name} {description}".lower()
    if "powershell" in combined_text or "pwsh" in combined_text:
        return "powershell"
    if re.search(r"\bbash\b", combined_text):
        return "bash"

    powershell_cmdlets = (
        "Test-Path",
        "Remove-Item",
        "Copy-Item",
        "Move-Item",
        "New-Item",
        "Get-Item",
        "Set-Item",
        "Join-Path",
        "ForEach-Object",
    )
    for cmd in commands:
        command_text = str(cmd.get("command", "")).strip()
        lowered = command_text.lower()
        if lowered.startswith(("powershell ", "powershell.exe ", "pwsh ", "pwsh.exe ")):
            return "powershell"
        if lowered.startswith(("bash ", "bash.exe ", "/bin/bash ", "sh ", "/bin/sh ")):
            return "bash"
        if any(token in command_text for token in powershell_cmdlets):
            return "powershell"
        if looks_like_powershell_command(command_text):
            return "powershell"

    return DEFAULT_TERMINAL_TYPE


def build_shell_command(command: str, terminal_type: str):
    """Build subprocess arguments for the selected terminal."""
    normalized = normalize_terminal_type(terminal_type)

    if sys.platform.startswith("win"):
        if normalized == "powershell":
            return [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                command,
            ]
        if normalized == "bash":
            return ["bash", "-lc", command]
        return ["cmd.exe", "/d", "/s", "/c", command]

    if normalized == "powershell":
        return ["pwsh", "-NoLogo", "-NoProfile", "-Command", command]
    if normalized == "cmd":
        return ["/bin/sh", "-lc", command]
    return ["bash", "-lc", command]


class NodeStatus(Enum):
    """节点状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class Command:
    """命令定义"""
    name: str
    command: str
    status: NodeStatus = NodeStatus.PENDING
    output: str = ""
    error: str = ""
    exit_code: Optional[int] = None
    duration: float = 0.0

    def get_status_text(self) -> str:
        texts = {
            NodeStatus.PENDING: "待执行",
            NodeStatus.RUNNING: "执行中",
            NodeStatus.SUCCESS: "成功",
            NodeStatus.FAILED: "失败",
            NodeStatus.SKIPPED: "已跳过",
        }
        return texts.get(self.status, "未知")


@dataclass
class TaskNode:
    """任务节点定义"""
    id: str
    name: str
    icon: str = "📦"
    commands: List[Command] = field(default_factory=list)
    status: NodeStatus = NodeStatus.PENDING
    working_dir: Optional[str] = None
    continue_on_error: bool = False
    description: str = ""
    position: Optional[Dict[str, float]] = None
    skip_in_flow: bool = False
    terminal_type: str = DEFAULT_TERMINAL_TYPE

    def get_status_text(self) -> str:
        texts = {
            NodeStatus.PENDING: "待执行",
            NodeStatus.RUNNING: "执行中",
            NodeStatus.SUCCESS: "成功",
            NodeStatus.FAILED: "失败",
            NodeStatus.SKIPPED: "已跳过",
        }
        return texts.get(self.status, "未知")

    def get_status_color(self) -> QColor:
        colors = {
            NodeStatus.PENDING: QColor(108, 117, 125),
            NodeStatus.RUNNING: QColor(13, 110, 253),
            NodeStatus.SUCCESS: QColor(25, 135, 84),
            NodeStatus.FAILED: QColor(220, 53, 69),
            NodeStatus.SKIPPED: QColor(255, 193, 7),
        }
        return colors.get(self.status, QColor(108, 117, 125))


class TaskFlowManager:
    """任务流程管理器"""

    def __init__(self):
        self.flow_id: str = "default"
        self.flow_name: str = "默认流程"
        self.nodes: Dict[str, TaskNode] = {}
        self.node_order: List[str] = []
        self.connections: List[tuple] = []  # (from_id, to_id)

    def clear(self) -> None:
        self.nodes.clear()
        self.node_order.clear()
        self.connections.clear()

    def clone(self):
        copied = TaskFlowManager()
        copied.load_from_dict(self.to_dict(include_flow_meta=True))
        return copied

    def load_from_dict(self, config: Dict[str, Any]) -> None:
        self.clear()
        self.flow_id = config.get("id", self.flow_id)
        self.flow_name = config.get("name", self.flow_name)

        for node_config in config.get('nodes', []):
            commands_config = node_config.get('commands', [])
            if not isinstance(commands_config, list):
                commands_config = []
            node = self.add_node(
                node_id=node_config['id'],
                name=node_config['name'],
                icon=node_config.get('icon', '📦')
            )
            node.description = node_config.get('description', '')
            node.working_dir = node_config.get('working_dir')
            node.continue_on_error = node_config.get('continue_on_error', False)
            node.position = node_config.get('position')
            node.skip_in_flow = node_config.get('skip_in_flow', False)
            node.terminal_type = (
                normalize_terminal_type(node_config.get('terminal_type'))
                if 'terminal_type' in node_config
                else infer_terminal_type(node.name, node.description, commands_config)
            )

            for cmd_config in commands_config:
                cmd = Command(
                    name=cmd_config.get('name', cmd_config['command']),
                    command=cmd_config['command']
                )
                node.commands.append(cmd)

        for connection in config.get('connections', []):
            self.connect_nodes(connection['from'], connection['to'])

    def to_dict(self, include_flow_meta: bool = False) -> Dict[str, Any]:
        config = {
            "nodes": [
                {
                    "id": node.id,
                    "name": node.name,
                    "icon": node.icon,
                    "description": node.description,
                    "working_dir": node.working_dir,
                    "continue_on_error": node.continue_on_error,
                    "position": node.position,
                    "skip_in_flow": node.skip_in_flow,
                    "terminal_type": normalize_terminal_type(node.terminal_type),
                    "commands": [
                        {"name": cmd.name, "command": cmd.command}
                        for cmd in node.commands
                    ]
                }
                for node_id in self.node_order
                for node in [self.nodes[node_id]]
            ],
            "connections": [{"from": f, "to": t} for f, t in self.connections]
        }
        if include_flow_meta:
            config["id"] = self.flow_id
            config["name"] = self.flow_name
        return config

    def add_node(self, node_id: str, name: str, icon: str = "📦") -> TaskNode:
        """添加任务节点"""
        node = TaskNode(id=node_id, name=name, icon=icon)
        self.nodes[node_id] = node
        self.node_order.append(node_id)
        return node

    def connect_nodes(self, from_id: str, to_id: str) -> None:
        """连接两个节点"""
        if from_id in self.nodes and to_id in self.nodes:
            self.connections.append((from_id, to_id))

    def load_from_file(self, filepath: str) -> None:
        """从配置文件加载任务流程"""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"配置文件不存在：{filepath}")

        with open(path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self.load_from_dict(config)

    def save_to_file(self, filepath: str) -> None:
        """保存任务流程到配置文件"""
        config = self.to_dict(include_flow_meta=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)

    def reset_status(self) -> None:
        """重置所有节点状态"""
        for node in self.nodes.values():
            node.status = NodeStatus.PENDING
            for cmd in node.commands:
                cmd.status = NodeStatus.PENDING
                cmd.output = ""
                cmd.error = ""
                cmd.exit_code = None
                cmd.duration = 0.0

    def get_execution_order(self, node_ids: Optional[List[str]] = None) -> List[str]:
        """Return node ids sorted by graph topology, using node_order as a stable tie-breaker."""
        candidate_ids = list(node_ids) if node_ids is not None else list(self.node_order)
        candidate_set = {node_id for node_id in candidate_ids if node_id in self.nodes}
        if not candidate_set:
            return []

        order_index = {
            node_id: index
            for index, node_id in enumerate(self.node_order)
        }
        incoming: Dict[str, set] = {node_id: set() for node_id in candidate_set}
        outgoing: Dict[str, set] = {node_id: set() for node_id in candidate_set}
        for from_id, to_id in self.connections:
            if from_id in candidate_set and to_id in candidate_set and from_id != to_id:
                outgoing[from_id].add(to_id)
                incoming[to_id].add(from_id)

        ready = sorted(
            [node_id for node_id in candidate_set if not incoming[node_id]],
            key=lambda node_id: order_index.get(node_id, 10 ** 9),
        )
        execution_order: List[str] = []

        while ready:
            current_id = ready.pop(0)
            execution_order.append(current_id)
            next_nodes = sorted(
                outgoing[current_id],
                key=lambda node_id: order_index.get(node_id, 10 ** 9),
            )
            for next_id in next_nodes:
                incoming[next_id].discard(current_id)
                if not incoming[next_id] and next_id not in execution_order and next_id not in ready:
                    ready.append(next_id)
                    ready.sort(key=lambda node_id: order_index.get(node_id, 10 ** 9))

        if len(execution_order) != len(candidate_set):
            cyclic_nodes = sorted(
                candidate_set.difference(execution_order),
                key=lambda node_id: order_index.get(node_id, 10 ** 9),
            )
            raise ValueError(f"检测到循环依赖，无法按链路执行: {', '.join(cyclic_nodes)}")

        return execution_order

    def execute_command(self, cmd: Command, working_dir: Optional[str] = None,
                        terminal_type: Optional[str] = None,
                        output_callback: Optional[Callable[[str], None]] = None,
                        should_stop_callback: Optional[Callable[[], bool]] = None,
                        register_process_callback: Optional[Callable[[Optional[subprocess.Popen]], None]] = None
                        ) -> NodeStatus:
        """执行单个命令"""
        start_time = time.time()
        cmd.status = NodeStatus.RUNNING

        try:
            effective_command = normalize_shell_command(cmd.command)
            resolved_terminal = normalize_terminal_type(terminal_type)
            if terminal_type is None and sys.platform.startswith("win") and looks_like_powershell_command(effective_command):
                resolved_terminal = "powershell"

            popen_command = build_shell_command(effective_command, resolved_terminal)
            process = subprocess.Popen(
                popen_command,
                shell=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=working_dir,
                bufsize=1
            )
            if register_process_callback is not None:
                register_process_callback(process)
            output_chunks: List[str] = []
            if process.stdout is not None:
                for line in iter(process.stdout.readline, b''):
                    if not line:
                        break
                    if should_stop_callback is not None and should_stop_callback():
                        break
                    decoded_line = decode_process_output(line)
                    output_chunks.append(decoded_line)
                    if output_callback is not None:
                        output_callback(decoded_line)
                process.stdout.close()

            cmd.exit_code = process.wait()
            cmd.output = "".join(output_chunks)
            cmd.error = cmd.output if cmd.exit_code != 0 else ""
            cmd.duration = time.time() - start_time

            if should_stop_callback is not None and should_stop_callback():
                cmd.status = NodeStatus.FAILED
                if not cmd.error:
                    cmd.error = "Execution stopped by user."
                if cmd.exit_code is None:
                    cmd.exit_code = -1
            elif cmd.exit_code == 0:
                cmd.status = NodeStatus.SUCCESS
            else:
                cmd.status = NodeStatus.FAILED

        except Exception as e:
            cmd.status = NodeStatus.FAILED
            cmd.error = str(e)
            cmd.duration = time.time() - start_time
        finally:
            if register_process_callback is not None:
                register_process_callback(None)

        return cmd.status


class FlowNodeItem(QGraphicsItem):
    """流程节点图形项"""

    def __init__(self, node: TaskNode, parent=None):
        super().__init__(parent)
        self.node = node
        # 启用节点拖动和选择
        self.setFlag(QGraphicsItem.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self.setZValue(1)

        # 节点尺寸
        self.width = 280
        self.height = 150
        self.corner_radius = 15

        # 输入输出端口位置
        self.input_pos = QPointF(0, self.height / 2)
        self.output_pos = QPointF(self.width, self.height / 2)

        # 动画效果
        self.glow_intensity = 0.0
        self.is_running = False
        self.is_hovered = False
        self.highlighted_ports = set()

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.width, self.height)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)

        # 获取状态颜色
        status_color = self.node.get_status_color()
        skip_marked = self.node.skip_in_flow or self.node.status == NodeStatus.SKIPPED

        # 绘制外发光效果
        if self.is_running or self.isSelected() or self.is_hovered:
            glow_margin = 8 if self.is_hovered and not (self.is_running or self.isSelected()) else 5
            glow_rect = QRectF(-glow_margin, -glow_margin, self.width + glow_margin * 2, self.height + glow_margin * 2)
            glow_path = QPainterPath()
            glow_path.addRoundedRect(glow_rect, self.corner_radius + glow_margin / 2, self.corner_radius + glow_margin / 2)
            glow_color = QColor(120, 187, 255) if self.is_hovered and not (self.is_running or self.isSelected()) else QColor(status_color)
            glow_color.setAlphaF(0.42 if self.is_hovered and not (self.is_running or self.isSelected()) else 0.3 + self.glow_intensity * 0.3)
            painter.fillPath(glow_path, QBrush(glow_color))

        # 绘制节点背景
        node_path = QPainterPath()
        node_path.addRoundedRect(0, 0, self.width, self.height, self.corner_radius, self.corner_radius)

        # 背景渐变
        bg_gradient = QColor(43, 43, 59)
        painter.fillPath(node_path, QBrush(bg_gradient))
        if skip_marked:
            painter.save()
            painter.setClipPath(node_path)
            painter.fillPath(node_path, QBrush(QColor(255, 193, 7, 28)))
            stripe_pen = QPen(QColor(255, 214, 102, 70), 2)
            painter.setPen(stripe_pen)
            for offset in range(-self.height, self.width + self.height, 18):
                painter.drawLine(offset, self.height, offset + self.height, 0)
            painter.restore()

        # 绘制边框
        border_color = QColor(120, 187, 255) if self.is_hovered and not (self.is_running or self.isSelected()) else QColor(status_color)
        if skip_marked and not (self.is_running or self.isSelected()):
            border_color = QColor(255, 214, 102)
        pen = QPen(border_color, 4 if self.is_hovered and not (self.is_running or self.isSelected()) else 3)
        if skip_marked:
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.drawPath(node_path)

        # 绘制节点内容
        content_x = 15
        content_y = 15

        # 图标
        painter.setFont(QFont("Segoe UI Emoji", 24))
        painter.drawText(QRectF(content_x, content_y, 40, 40), Qt.AlignCenter, self.node.icon)

        # 名称
        painter.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        painter.setPen(QColor(255, 255, 255))
        name_rect = QRectF(content_x + 45, content_y, self.width - 70, 30)
        painter.drawText(name_rect, Qt.AlignVCenter, self.node.name)

        # 状态指示器
        status_rect = QRectF(self.width - 35, 10, 25, 25)
        status_path = QPainterPath()
        status_path.addEllipse(status_rect)
        painter.fillPath(status_path, QBrush(status_color))
        if skip_marked:
            badge_rect = QRectF(self.width - 92, 12, 48, 22)
            badge_path = QPainterPath()
            badge_path.addRoundedRect(badge_rect, 8, 8)
            painter.fillPath(badge_path, QBrush(QColor(255, 193, 7, 220)))
            painter.setPen(QColor(64, 45, 0))
            painter.setFont(QFont("Microsoft YaHei", 8, QFont.Bold))
            painter.drawText(badge_rect, Qt.AlignCenter, "SKIP")

        # 描述
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor(150, 150, 150))
        desc_rect = QRectF(content_x, content_y + 45, self.width - 30, 30)
        painter.drawText(desc_rect, Qt.AlignTop | Qt.AlignLeft, self.node.description[:40] + "..." if len(self.node.description) > 40 else self.node.description)

        # 命令数量
        cmd_count = len(self.node.commands)
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(QColor(100, 150, 100))
        cmd_rect = QRectF(content_x, content_y + 75, self.width - 30, 20)
        painter.drawText(cmd_rect, Qt.AlignLeft, f"📝 {cmd_count} 个命令")

        # 状态文本
        painter.setFont(QFont("Microsoft YaHei", 9))
        painter.setPen(status_color)
        status_rect = QRectF(content_x, content_y + 95, self.width - 30, 20)
        status_text = "执行时跳过" if self.node.skip_in_flow and self.node.status == NodeStatus.PENDING else self.node.get_status_text()
        painter.drawText(status_rect, Qt.AlignLeft, status_text)

        # 绘制输入端口
        self._draw_port(painter, self.input_pos, "input", True, status_color)

        # 绘制输出端口
        self._draw_port(painter, self.output_pos, "output", False, status_color)

    def _draw_port(self, painter: QPainter, pos: QPointF, port_name: str, is_input: bool, color: QColor):
        """绘制端口"""
        is_highlighted = port_name in self.highlighted_ports
        radius = 10 if is_highlighted else 8
        port_rect = QRectF(pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)
        port_path = QPainterPath()
        port_path.addEllipse(port_rect)
        fill_color = QColor(96, 165, 250) if is_highlighted else color
        painter.fillPath(port_path, QBrush(fill_color))
        painter.setPen(QPen(QColor(255, 255, 255), 3 if is_highlighted else 2))
        painter.drawPath(port_path)

        if is_highlighted:
            outer_rect = QRectF(pos.x() - 15, pos.y() - 15, 30, 30)
            outer_path = QPainterPath()
            outer_path.addEllipse(outer_rect)
            highlight_color = QColor(96, 165, 250, 70)
            painter.fillPath(outer_path, QBrush(highlight_color))

    def update_status(self):
        """更新状态"""
        self.update()

    def set_running(self, running: bool):
        """设置运行状态"""
        self.is_running = running
        self.update()

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def get_port_scene_pos(self, port_name: str) -> QPointF:
        if port_name == "input":
            return self.mapToScene(self.input_pos)
        return self.mapToScene(self.output_pos)

    def port_at_scene_pos(self, scene_pos: QPointF, tolerance: float = 16.0) -> Optional[str]:
        for port_name in ("input", "output"):
            port_pos = self.get_port_scene_pos(port_name)
            dx = port_pos.x() - scene_pos.x()
            dy = port_pos.y() - scene_pos.y()
            if (dx * dx + dy * dy) <= tolerance * tolerance:
                return port_name
        return None

    def set_highlighted_ports(self, *ports: str):
        new_ports = {port for port in ports if port}
        if new_ports != self.highlighted_ports:
            self.highlighted_ports = new_ports
            self.update()

    def itemChange(self, change, value):
        """节点位置变化后刷新连线。"""
        if change == QGraphicsItem.ItemPositionHasChanged and self.scene():
            self.node.position = {"x": float(self.pos().x()), "y": float(self.pos().y())}
            if isinstance(self.scene(), FlowScene):
                self.scene().node_position_changed.emit(self.node.id)
            self.scene().update()
        return super().itemChange(change, value)


class ConnectionItem(QGraphicsItem):
    """连接线"""

    def __init__(self, from_node: FlowNodeItem, to_node: FlowNodeItem,
                 from_node_id: str, to_node_id: str, parent=None):
        super().__init__(parent)
        self.from_node = from_node
        self.to_node = to_node
        self.from_node_id = from_node_id
        self.to_node_id = to_node_id
        self.is_hovered = False
        self.setZValue(0)
        self.setFlag(QGraphicsItem.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

    def boundingRect(self) -> QRectF:
        return QRectF(-1000, -1000, 2000, 2000)

    def _build_path(self) -> QPainterPath:
        start = self.from_node.mapToScene(self.from_node.output_pos)
        end = self.to_node.mapToScene(self.to_node.input_pos)
        start = self.mapFromScene(start)
        end = self.mapFromScene(end)

        path = QPainterPath(start)
        ctrl1 = QPointF(start.x() + 50, start.y())
        ctrl2 = QPointF(end.x() - 50, end.y())
        path.cubicTo(ctrl1, ctrl2, end)
        return path

    def shape(self) -> QPainterPath:
        path = self._build_path()
        stroker = QPainterPathStroker()
        stroker.setWidth(12)
        return stroker.createStroke(path)

    def paint(self, painter: QPainter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        path = self._build_path()
        end = path.pointAtPercent(1.0)

        line_color = QColor(96, 165, 250) if self.is_hovered else QColor(100, 100, 100)
        pen = QPen(line_color, 4 if self.is_hovered else 2)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)

        self._draw_arrow(painter, path, end, line_color)

    def _draw_arrow(self, painter: QPainter, path: QPainterPath, end_point: QPointF, color: QColor):
        arrow_size = 10
        arrow_path = QPainterPath()
        arrow_path.moveTo(end_point)
        arrow_path.lineTo(
            end_point.x() - arrow_size * 0.866,
            end_point.y() - arrow_size * 0.5
        )
        arrow_path.lineTo(
            end_point.x() - arrow_size * 0.866,
            end_point.y() + arrow_size * 0.5
        )
        arrow_path.closeSubpath()
        painter.fillPath(arrow_path, QBrush(color))

    def hoverEnterEvent(self, event):
        self.is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)


class FlowScene(QGraphicsScene):
    """流程场景"""

    node_clicked = Signal(str)
    node_double_clicked = Signal(str)
    node_position_changed = Signal(str)
    connection_delete_requested = Signal(str, str)
    connection_create_requested = Signal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node_items: Dict[str, FlowNodeItem] = {}
        self.connection_items: List[ConnectionItem] = []
        self.task_manager: Optional[TaskFlowManager] = None
        self._dragging_connection = False
        self._drag_source_node_id: Optional[str] = None
        self._drag_source_port: Optional[str] = None
        self._drag_current_pos = QPointF()
        self._drag_target_node_id: Optional[str] = None
        self._drag_target_port: Optional[str] = None
        self.setBackgroundBrush(QColor(30, 30, 46))

    def load_flow(self, task_manager: TaskFlowManager):
        self.clear()
        self.node_items.clear()
        self.connection_items.clear()
        self.cancel_connection_drag()
        self.task_manager = task_manager

        y_offset = 50
        for node_id in task_manager.node_order:
            node = task_manager.nodes[node_id]
            item = FlowNodeItem(node)
            if node.position and "x" in node.position and "y" in node.position:
                item.setPos(node.position["x"], node.position["y"])
            else:
                item.setPos(50, y_offset)
                node.position = {"x": 50.0, "y": float(y_offset)}
            self.addItem(item)
            self.node_items[node_id] = item

            y_offset += item.height + 80

        # 添加连接
        for from_id, to_id in task_manager.connections:
            if from_id in self.node_items and to_id in self.node_items:
                conn = ConnectionItem(
                    self.node_items[from_id],
                    self.node_items[to_id],
                    from_id,
                    to_id,
                )
                self.addItem(conn)
                self.connection_items.append(conn)

    def _clear_port_highlights(self):
        for item in self.node_items.values():
            item.set_highlighted_ports()

    def _find_node_id_for_item(self, node_item: FlowNodeItem) -> Optional[str]:
        for node_id, item in self.node_items.items():
            if item == node_item:
                return node_id
        return None

    def find_port_target(self, scene_pos: QPointF,
                         exclude_node_id: Optional[str] = None,
                         allowed_port: Optional[str] = None):
        nearest = None
        nearest_distance_sq = None
        tolerance_sq = 18.0 * 18.0
        for node_id, item in self.node_items.items():
            if exclude_node_id and node_id == exclude_node_id:
                continue
            port_names = (allowed_port,) if allowed_port else ("input", "output")
            for port_name in port_names:
                if not port_name:
                    continue
                port_pos = item.get_port_scene_pos(port_name)
                dx = port_pos.x() - scene_pos.x()
                dy = port_pos.y() - scene_pos.y()
                distance_sq = dx * dx + dy * dy
                if distance_sq <= tolerance_sq and (nearest_distance_sq is None or distance_sq < nearest_distance_sq):
                    nearest = (node_id, port_name, item)
                    nearest_distance_sq = distance_sq
        return nearest

    def is_dragging_connection(self) -> bool:
        return self._dragging_connection

    def start_connection_drag(self, node_id: str, port_name: str, scene_pos: QPointF):
        if node_id not in self.node_items:
            return False
        self._dragging_connection = True
        self._drag_source_node_id = node_id
        self._drag_source_port = port_name
        self._drag_current_pos = scene_pos
        self._drag_target_node_id = None
        self._drag_target_port = None
        self._clear_port_highlights()
        self.node_items[node_id].set_highlighted_ports(port_name)
        self.update()
        return True

    def update_connection_drag(self, scene_pos: QPointF):
        if not self._dragging_connection:
            return
        self._drag_current_pos = scene_pos
        self._clear_port_highlights()
        source_item = self.node_items.get(self._drag_source_node_id) if self._drag_source_node_id else None
        if source_item and self._drag_source_port:
            source_item.set_highlighted_ports(self._drag_source_port)

        allowed_target_port = "input" if self._drag_source_port == "output" else "output"
        target = self.find_port_target(
            scene_pos,
            exclude_node_id=self._drag_source_node_id,
            allowed_port=allowed_target_port,
        )
        if target:
            node_id, port_name, item = target
            self._drag_target_node_id = node_id
            self._drag_target_port = port_name
            item.set_highlighted_ports(port_name)
        else:
            self._drag_target_node_id = None
            self._drag_target_port = None
        self.update()

    def finish_connection_drag(self):
        if not self._dragging_connection:
            return False

        created = False
        if self._drag_source_node_id and self._drag_target_node_id and self._drag_source_port and self._drag_target_port:
            if self._drag_source_port == "output" and self._drag_target_port == "input":
                self.connection_create_requested.emit(self._drag_source_node_id, self._drag_target_node_id)
                created = True
            elif self._drag_source_port == "input" and self._drag_target_port == "output":
                self.connection_create_requested.emit(self._drag_target_node_id, self._drag_source_node_id)
                created = True

        self.cancel_connection_drag()
        return created

    def cancel_connection_drag(self):
        self._dragging_connection = False
        self._drag_source_node_id = None
        self._drag_source_port = None
        self._drag_target_node_id = None
        self._drag_target_port = None
        self._clear_port_highlights()
        self.update()

    def mousePressEvent(self, event):
        """处理鼠标点击事件"""
        if self._dragging_connection:
            event.accept()
            return
        # 获取点击位置的项
        pos = event.scenePos()
        item = self.itemAt(pos, self.views()[0].transform() if self.views() else None)

        # 查找是否点击了节点
        while item:
            if isinstance(item, FlowNodeItem):
                # 发出选中信号，但继续走默认事件链，允许节点被拖动。
                for node_id, node_item in self.node_items.items():
                    if node_item == item:
                        self.node_clicked.emit(node_id)
                        break
                break
            item = item.parentItem()

        super().mousePressEvent(event)

    def update_node_status(self, node_id: str):
        if node_id in self.node_items:
            self.node_items[node_id].update_status()

    def set_node_running(self, node_id: str, running: bool):
        if node_id in self.node_items:
            self.node_items[node_id].set_running(running)

    def drawForeground(self, painter: QPainter, rect: QRectF):
        super().drawForeground(painter, rect)
        if not (self._dragging_connection and self._drag_source_node_id and self._drag_source_port):
            return

        source_item = self.node_items.get(self._drag_source_node_id)
        if source_item is None:
            return

        start = source_item.get_port_scene_pos(self._drag_source_port)
        end = self._drag_current_pos
        if self._drag_target_node_id and self._drag_target_port and self._drag_target_node_id in self.node_items:
            end = self.node_items[self._drag_target_node_id].get_port_scene_pos(self._drag_target_port)

        path = QPainterPath(start)
        ctrl_offset = 60
        start_offset = ctrl_offset if self._drag_source_port == "output" else -ctrl_offset
        end_offset = -ctrl_offset if (self._drag_target_port or "input") == "input" else ctrl_offset
        ctrl1 = QPointF(start.x() + start_offset, start.y())
        ctrl2 = QPointF(end.x() + end_offset, end.y())
        path.cubicTo(ctrl1, ctrl2, end)

        pen = QPen(QColor(96, 165, 250, 220), 3, Qt.DashLine)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)

        end_circle = QRectF(end.x() - 6, end.y() - 6, 12, 12)
        end_path = QPainterPath()
        end_path.addEllipse(end_circle)
        painter.fillPath(end_path, QBrush(QColor(96, 165, 250)))

    def contextMenuEvent(self, event):
        if self._dragging_connection:
            event.accept()
            return
        item = self.itemAt(event.scenePos(), self.views()[0].transform() if self.views() else QTransform())
        while item:
            if isinstance(item, ConnectionItem):
                menu = QMenu()
                delete_action = menu.addAction("删除连接")
                chosen_action = menu.exec(event.screenPos())
                if chosen_action == delete_action:
                    self.connection_delete_requested.emit(item.from_node_id, item.to_node_id)
                    event.accept()
                    return
                break
            item = item.parentItem()
        super().contextMenuEvent(event)


class FlowView(QGraphicsView):
    """流程视图"""

    def __init__(self, scene: FlowScene, parent=None):
        super().__init__(scene)
        self.setRenderHint(QPainter.Antialiasing)
        # 默认不拖动，让节点可以单独拖动
        self.setDragMode(QGraphicsView.NoDrag)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setStyleSheet("""
            QGraphicsView {
                background-color: #1e1e2e;
                border: none;
            }
        """)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)

        # 设置鼠标跟踪
        self.setMouseTracking(True)

        # 用于视图拖动
        self._drag_mode = False
        self._last_pos = None

    def wheelEvent(self, event):
        """鼠标滚轮缩放"""
        factor = 1.1
        if event.angleDelta().y() < 0:
            factor = 1.0 / 1.1
        self.scale(factor, factor)
        event.accept()

    def mousePressEvent(self, event):
        """鼠标按下事件"""
        scene = self.scene()
        if event.button() == Qt.MiddleButton:
            # 中键拖动视图
            self._drag_mode = True
            self._last_pos = event.pos()
            self.setDragMode(QGraphicsView.ScrollHandDrag)  # 启用手势拖动
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
        elif event.button() == Qt.LeftButton:
            if isinstance(scene, FlowScene):
                port_target = scene.find_port_target(self.mapToScene(event.pos()))
                if port_target:
                    node_id, port_name, _item = port_target
                    scene.node_clicked.emit(node_id)
                    scene.start_connection_drag(node_id, port_name, self.mapToScene(event.pos()))
                    self.setDragMode(QGraphicsView.NoDrag)
                    event.accept()
                    return
            # 左键点击，检查是否点击在节点上
            pos = self.mapToScene(event.pos())
            item = self.scene().itemAt(pos, self.transform())
            if item and isinstance(item, FlowNodeItem):
                # 点击在节点上，禁用视图拖动，启用项选择和拖动
                self.setDragMode(QGraphicsView.NoDrag)  # 关闭视图拖动
                # 调用父类实现以确保项能接收事件
                QGraphicsView.mousePressEvent(self, event)
            else:
                # 点击在空白处，可以拖动视图
                self._drag_mode = True
                self._last_pos = event.pos()
                self.setDragMode(QGraphicsView.ScrollHandDrag)  # 启用手势拖动
                self.setCursor(Qt.ClosedHandCursor)
                event.accept()
        else:
            QGraphicsView.mousePressEvent(self, event)

    def mouseMoveEvent(self, event):
        """鼠标移动事件"""
        scene = self.scene()
        if isinstance(scene, FlowScene) and scene.is_dragging_connection():
            scene.update_connection_drag(self.mapToScene(event.pos()))
            event.accept()
            return
        # 对于视图拖动的判断要结合是否有选中的项，避免冲突
        selected_items = self.scene().selectedItems()
        if (self._drag_mode and self._last_pos and 
            not any(isinstance(item, FlowNodeItem) for item in selected_items)):
            # 检查是否有节点被选中时的特殊处理，仅当无选择项时启用视图拖动
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
        else:
            # 保留 QGraphicsView 的默认行为
            QGraphicsView.mouseMoveEvent(self, event)

    def mouseReleaseEvent(self, event):
        """鼠标释放事件"""
        scene = self.scene()
        if event.button() == Qt.LeftButton and isinstance(scene, FlowScene) and scene.is_dragging_connection():
            scene.update_connection_drag(self.mapToScene(event.pos()))
            scene.finish_connection_drag()
            event.accept()
            return
        if self._drag_mode:
            self._drag_mode = False
            self._last_pos = None
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.ArrowCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)


class NodeEditorPanel(QWidget):
    """节点编辑面板"""

    node_changed = Signal(str)  # node_id
    save_requested = Signal()
    execute_requested = Signal()

    def __init__(self, task_manager: TaskFlowManager):
        super().__init__()
        self.task_manager = task_manager
        self.current_node_id: Optional[str] = None
        self._is_loading = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # 基本信息组
        basic_group = QGroupBox("📋 基本信息")
        basic_group.setStyleSheet(self._get_group_style())
        basic_layout = QFormLayout(basic_group)

        # 节点 ID
        self.node_id_edit = QLineEdit()
        self.node_id_edit.setStyleSheet(self._get_input_style())
        self.node_id_edit.setReadOnly(True)
        basic_layout.addRow("节点 ID:", self.node_id_edit)

        # 节点名称
        self.node_name_edit = QLineEdit()
        self.node_name_edit.setStyleSheet(self._get_input_style())
        self.node_name_edit.textChanged.connect(self._on_name_changed)
        basic_layout.addRow("节点名称:", self.node_name_edit)

        # 图标
        self.icon_combo = QComboBox()
        self.icon_combo.setStyleSheet(self._get_input_style())
        icons = ["📦", "", "🧮", "📋", "🤖", "", "⚙️", "🔧", "", "🚀", "✅", "❌"]
        self.icon_combo.addItems(icons)
        self.icon_combo.currentTextChanged.connect(self._on_icon_changed)
        basic_layout.addRow("图标:", self.icon_combo)

        # 描述
        self.desc_edit = QTextEdit()
        self.desc_edit.setStyleSheet(self._get_input_style())
        self.desc_edit.setMaximumHeight(80)
        self.desc_edit.textChanged.connect(self._on_desc_changed)
        basic_layout.addRow("描述:", self.desc_edit)

        layout.addWidget(basic_group)

        # 配置组
        config_group = QGroupBox("⚙️ 配置")
        config_group.setStyleSheet(self._get_group_style())
        config_layout = QFormLayout(config_group)

        # 工作目录
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

        # 允许错误继续
        self.continue_check = QCheckBox()
        self.continue_check.setStyleSheet("color: white;")
        self.continue_check.stateChanged.connect(self._on_continue_changed)
        config_layout.addRow("允许错误继续:", self.continue_check)

        # Flow 执行时跳过
        self.skip_check = QCheckBox()
        self.skip_check.setStyleSheet("color: white;")
        self.skip_check.stateChanged.connect(self._on_skip_changed)
        config_layout.addRow("执行时跳过:", self.skip_check)

        # 状态
        self.status_label = QLabel("-")
        self.status_label.setStyleSheet("color: #888;")
        config_layout.addRow("状态:", self.status_label)

        layout.addWidget(config_group)

        # 命令列表组
        cmd_group = QGroupBox("📝 命令列表")
        cmd_group.setStyleSheet(self._get_group_style())
        cmd_layout = QVBoxLayout(cmd_group)

        # 命令列表 - 使用 QListWidget
        self.command_list = QListWidget()
        self.command_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b3b;
                color: #e0e0e0;
                border: 2px solid #59627a;
                border-radius: 6px;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item {
                padding: 10px 12px;
                border: 1px solid #4b556b;
                border-radius: 4px;
                margin: 0 0 6px 0;
                background-color: #303247;
            }
            QListWidget::item:selected {
                background-color: #0d6efd;
                color: white;
                border: 2px solid #7fb0ff;
            }
            QListWidget::item:hover {
                background-color: #3a3f58;
                border: 1px solid #7a849d;
            }
        """)
        self.command_list.setMaximumHeight(200)
        self.command_list.itemSelectionChanged.connect(self._on_command_selection_changed)
        self.command_list.itemDoubleClicked.connect(self._on_command_double_clicked)
        cmd_layout.addWidget(self.command_list)

        # 命令操作按钮
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
        layout.addWidget(cmd_group)

        # 操作按钮
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

    def _get_group_style(self) -> str:
        return """
            QGroupBox {
                color: white;
                border: 1px solid #444;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """

    def _get_input_style(self) -> str:
        return """
            QLineEdit, QTextEdit, QComboBox {
                background-color: #2b2b3b;
                color: white;
                border: 1px solid #444;
                border-radius: 3px;
                padding: 5px;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox::down-arrow {
                width: 12px;
                height: 12px;
            }
            QComboBox QAbstractItemView {
                background-color: #2b2b3b;
                color: white;
                border: 1px solid #59627a;
                selection-background-color: #0d6efd;
                selection-color: white;
                outline: 0;
                padding: 4px;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 6px 10px;
                background-color: #2b2b3b;
                color: white;
            }
            QComboBox QAbstractItemView::item:hover {
                background-color: #3a3f58;
                color: white;
            }
            QComboBox QAbstractItemView::item:selected {
                background-color: #0d6efd;
                color: white;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border-color: #0d6efd;
            }
        """

    def _get_btn_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                padding: 8px 16px;
                border-radius: 5px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {color}dd;
            }}
        """

    def load_node(self, node_id: str):
        """加载节点进行编辑"""
        if self.current_node_id and self.current_node_id != node_id:
            self._apply_form_to_current_node()
        node = self.task_manager.nodes.get(node_id)
        if not node:
            return

        self._is_loading = True
        try:
            self.current_node_id = node_id

            # 基本信息
            self.node_id_edit.setText(node.id)
            self.node_name_edit.setText(node.name)
            self.icon_combo.setCurrentText(node.icon)
            self.desc_edit.setText(node.description)

            # 配置
            self.workdir_edit.setText(node.working_dir or "")
            terminal_index = self.terminal_combo.findData(normalize_terminal_type(node.terminal_type))
            self.terminal_combo.setCurrentIndex(terminal_index if terminal_index >= 0 else 0)
            self.continue_check.setChecked(node.continue_on_error)
            self.skip_check.setChecked(node.skip_in_flow)
            self.status_label.setText(node.get_status_text())
            self.status_label.setStyleSheet(f"color: {node.get_status_color().name()};")

            # 命令列表 - 使用 QListWidget
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
                item.setData(Qt.UserRole, i)  # 存储命令索引
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

    def _on_name_changed(self, text: str):
        if self.current_node_id:
            self.task_manager.nodes[self.current_node_id].name = text
            self._notify_node_changed()

    def _on_icon_changed(self, text: str):
        if self.current_node_id:
            self.task_manager.nodes[self.current_node_id].icon = text
            self._notify_node_changed()

    def _on_desc_changed(self):
        if self.current_node_id:
            self.task_manager.nodes[self.current_node_id].description = self.desc_edit.toPlainText()
            self._notify_node_changed()

    def _on_workdir_changed(self, text: str):
        if self.current_node_id:
            self.task_manager.nodes[self.current_node_id].working_dir = text if text else None
            self._notify_node_changed()

    def _on_terminal_changed(self, _index):
        if self.current_node_id:
            self.task_manager.nodes[self.current_node_id].terminal_type = normalize_terminal_type(
                self.terminal_combo.currentData()
            )
            self._notify_node_changed()

    def _browse_workdir(self):
        directory = select_directory(self, "选择工作目录", self.workdir_edit.text().strip())
        if directory:
            self.workdir_edit.setText(directory)

    def _on_continue_changed(self, state):
        if self.current_node_id:
            self.task_manager.nodes[self.current_node_id].continue_on_error = (state == Qt.Checked)
            self._notify_node_changed()

    def _on_skip_changed(self, state):
        if self.current_node_id:
            self.task_manager.nodes[self.current_node_id].skip_in_flow = (state == Qt.Checked)
            self._notify_node_changed()

    def _on_command_selection_changed(self):
        pass  # 选择改变时的处理

    def _on_command_double_clicked(self, item: QListWidgetItem):
        """双击编辑命令"""
        self._edit_command()

    def _on_commands_changed(self):
        pass  # 命令编辑在保存时处理

    def _get_command_dialog_result(self, name: str = "", command: str = "") -> tuple:
        """获取命令编辑对话框结果"""
        dialog = QDialog(self)
        dialog.setWindowTitle("编辑命令")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet(DIALOG_STYLESHEET)

        layout = QVBoxLayout(dialog)

        # 命令名称
        name_label = QLabel("命令名称:")
        name_edit = QLineEdit(name)
        layout.addWidget(name_label)
        layout.addWidget(name_edit)

        # 命令内容
        cmd_label = QLabel("命令内容:")
        cmd_edit = QTextEdit(command)
        cmd_edit.setMaximumHeight(100)
        layout.addWidget(cmd_label)
        layout.addWidget(cmd_edit)

        # 按钮
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
            node.commands.append(Command(name="新命令", command="echo '新命令'"))
            self.load_node(self.current_node_id)
            self.node_changed.emit(self.current_node_id)

    def _remove_command(self):
        if self.current_node_id:
            node = self.task_manager.nodes[self.current_node_id]
            selected_items = self.command_list.selectedItems()
            if selected_items:
                item = selected_items[0]
                index = item.data(Qt.UserRole)
                if index is not None and 0 <= index < len(node.commands):
                    node.commands.pop(index)
                    self.load_node(self.current_node_id)
                    self.node_changed.emit(self.current_node_id)

    def _edit_command(self):
        """编辑选中的命令"""
        if self.current_node_id:
            node = self.task_manager.nodes[self.current_node_id]
            selected_items = self.command_list.selectedItems()
            if selected_items:
                item = selected_items[0]
                index = item.data(Qt.UserRole)
                if index is not None and 0 <= index < len(node.commands):
                    cmd = node.commands[index]
                    new_name, new_command = self._get_command_dialog_result(cmd.name, cmd.command)
                    if new_name is not None:
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
        self.setStyleSheet(DIALOG_STYLESHEET)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        hint = QLabel("创建一个可立即编辑和执行的新节点。")
        hint.setStyleSheet("color: #cbd5e1;")
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
        self.setStyleSheet(DIALOG_STYLESHEET)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        hint = QLabel("选择起点和终点，建立节点之间的链路。")
        hint.setStyleSheet("color: #cbd5e1;")
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

        form.addRow("源节点:", self.source_combo)
        form.addRow("目标节点:", self.target_combo)
        form.addRow("连接方式:", self.insert_into_chain_check)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _validate_and_accept(self):
        if self.source_combo.currentData() == self.target_combo.currentData():
            QMessageBox.warning(self, "校验失败", "源节点和目标节点不能是同一个。")
            return
        self.accept()

    def get_connection_data(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_combo.currentData(),
            "target_id": self.target_combo.currentData(),
            "insert_into_chain": self.insert_into_chain_check.isChecked(),
        }


class ExecuteWorker(QThread):
    """任务执行工作线程"""
    node_started = Signal(str)
    node_finished = Signal(str, bool)
    command_executing = Signal(str, str, str)
    command_finished = Signal(str, str, bool, float)
    log_message = Signal(str)
    output_message = Signal(str, str)
    all_finished = Signal(bool)
    stopped = Signal()

    def __init__(self, task_manager: TaskFlowManager, node_ids: List[str], respect_skip: bool = True):
        super().__init__()
        self.task_manager = task_manager
        self.node_ids = node_ids
        self.respect_skip = respect_skip
        self._stop_requested = False
        self._current_process: Optional[subprocess.Popen] = None
        self._process_lock = threading.Lock()

    def _write_node_log(self, log_path: Path, message: str):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(message)

    def _emit_node_output(self, node_id: str, log_path: Path, message: str):
        self.output_message.emit(node_id, message)
        self._write_node_log(log_path, message)

    def _set_current_process(self, process: Optional[subprocess.Popen]):
        with self._process_lock:
            self._current_process = process

    def _terminate_current_process(self):
        with self._process_lock:
            process = self._current_process

        if process is None or process.poll() is not None:
            return

        try:
            if sys.platform.startswith("win"):
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                process.terminate()
        except Exception:
            pass

    def request_stop(self):
        self._stop_requested = True
        self._terminate_current_process()

    def is_stop_requested(self) -> bool:
        return self._stop_requested

    def run(self):
        all_success = True

        for node_id in self.node_ids:
            if self._stop_requested:
                all_success = False
                break

            if node_id not in self.task_manager.nodes:
                continue

            node = self.task_manager.nodes[node_id]
            if self.respect_skip and node.skip_in_flow:
                started_at = datetime.now()
                log_path = build_node_log_path(node.name, started_at)
                node.status = NodeStatus.SKIPPED
                for cmd in node.commands:
                    cmd.status = NodeStatus.SKIPPED
                self._write_node_log(
                    log_path,
                    f"{'='*60}\n节点: {node.name} ({node.id})\n开始时间: {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n状态: 已跳过\n{'='*60}\n"
                )
                self.log_message.emit(f"\n⏭️ 跳过节点：{node.icon} {node.name}")
                self.log_message.emit(f"📝 节点日志：{log_path.name}")
                self.node_finished.emit(node_id, True)
                continue

            node.status = NodeStatus.RUNNING
            self.node_started.emit(node_id)
            started_at = datetime.now()
            log_path = build_node_log_path(node.name, started_at)
            header = [
                f"{'='*60}\n",
                f"节点: {node.name} ({node.id})\n",
                f"开始时间: {started_at.strftime('%Y-%m-%d %H:%M:%S')}\n",
            ]
            if node.description:
                header.append(f"描述: {node.description}\n")
            if node.working_dir:
                header.append(f"工作目录: {node.working_dir}\n")
            header.append(f"{'='*60}\n\n")
            self._write_node_log(log_path, "".join(header))
            self.log_message.emit(f"\n{'='*60}")
            self.log_message.emit(f"📦 开始执行节点：{node.icon} {node.name}")
            self.log_message.emit(f"📝 节点日志：{log_path.name}")
            if node.description:
                self.log_message.emit(f"   {node.description}")
            if node.working_dir:
                self.log_message.emit(f"   工作目录：{node.working_dir}")
            self.log_message.emit(f"{'='*60}")

            node_success = True
            for i, cmd in enumerate(node.commands):
                self.log_message.emit(f"\n▶️  执行命令：{cmd.name}")
                self.log_message.emit(f"   命令：{cmd.command}")
                self.command_executing.emit(node_id, cmd.name, cmd.command)
                self._emit_node_output(
                    node_id,
                    log_path,
                    f"\n>>> {cmd.name}\n{cmd.command}\n\n"
                )

                status = self.task_manager.execute_command(
                    cmd,
                    node.working_dir,
                    node.terminal_type,
                    output_callback=lambda text, nid=node_id, path=log_path: self._emit_node_output(nid, path, text),
                    should_stop_callback=self.is_stop_requested,
                    register_process_callback=self._set_current_process,
                )

                if status == NodeStatus.SUCCESS:
                    self.log_message.emit(f"✅ 完成 (耗时：{cmd.duration:.2f}s)")
                    self.command_finished.emit(node_id, cmd.name, True, cmd.duration)
                    self._emit_node_output(
                        node_id,
                        log_path,
                        f"\n[命令完成] {cmd.name} | 耗时 {cmd.duration:.2f}s | 退出码 {cmd.exit_code}\n\n"
                    )
                    if cmd.output:
                        self.log_message.emit(f"📄 输出：{cmd.output[:300]}")
                else:
                    self.log_message.emit(f"❌ 失败 (退出码：{cmd.exit_code})")
                    self.command_finished.emit(node_id, cmd.name, False, cmd.duration)
                    self._emit_node_output(
                        node_id,
                        log_path,
                        f"\n[命令失败] {cmd.name} | 耗时 {cmd.duration:.2f}s | 退出码 {cmd.exit_code}\n\n"
                    )
                    if cmd.error:
                        self.log_message.emit(f"📄 错误：{cmd.error[:300]}")
                        if not cmd.output:
                            self._emit_node_output(node_id, log_path, f"{cmd.error}\n")
                    node_success = False
                    if self._stop_requested:
                        for remaining in node.commands[i + 1:]:
                            remaining.status = NodeStatus.SKIPPED
                        self.log_message.emit("⏹️ 执行已停止")
                        break
                    if not node.continue_on_error:
                        for remaining in node.commands[i + 1:]:
                            remaining.status = NodeStatus.SKIPPED
                        self.log_message.emit(f"⚠️  节点因命令失败而中止")
                        break

            if node_success:
                node.status = NodeStatus.SUCCESS
            else:
                node.status = NodeStatus.FAILED
                all_success = False

            self.node_finished.emit(node_id, node_success)
            self.log_message.emit(f"\n节点 '{node.name}' 完成 - 状态：{node.get_status_text()}")
            finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._emit_node_output(
                node_id,
                log_path,
                f"\n{'='*60}\n[节点完成] {node.name} | 状态 {node.get_status_text()} | 结束时间 {finished_at}\n{'='*60}\n"
            )

            if self._stop_requested:
                all_success = False
                break

            if not node_success and not node.continue_on_error:
                self.log_message.emit(f"\n⚠️  执行中止")
                break

        self.all_finished.emit(all_success)
        if self._stop_requested:
            self.log_message.emit(f"\n{'='*60}\n⏹️ Flow 执行已停止\n{'='*60}")
            self.stopped.emit()
        elif all_success:
            self.log_message.emit(f"\n{'='*60}\n✅ 所有选中节点执行完成!\n{'='*60}")
        else:
            self.log_message.emit(f"\n{'='*60}\n⚠️ 部分节点执行失败\n{'='*60}")


class MainWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.task_manager = TaskFlowManager()
        self.flows: Dict[str, TaskFlowManager] = {}
        self.flow_order: List[str] = []
        self.current_flow_id: Optional[str] = None
        self.node_templates = load_node_templates()
        self.worker = None
        self._execution_was_stopped = False
        self.selected_node_id: Optional[str] = None
        self.init_ui()
        self.load_startup_flow()

    def init_ui(self):
        self.setWindowTitle("🔄 PyFlow 任务流编排管理器")
        self.setMinimumSize(1400, 900)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1e1e2e;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)

        # 左侧 - 流程画布
        left_widget = QWidget()
        left_shell_layout = QHBoxLayout(left_widget)
        left_shell_layout.setContentsMargins(0, 0, 0, 0)
        left_shell_layout.setSpacing(0)

        # 定义按钮样式函数（在 editor_panel 创建之前使用）
        def get_btn_style(color: str) -> str:
            return f"""
                QPushButton {{
                    background-color: {color};
                    color: white;
                    padding: 8px 16px;
                    border-radius: 5px;
                    font-weight: bold;
                }}
                QPushButton:hover {{
                    background-color: {color}dd;
                }}
            """

        flow_sidebar = QFrame()
        flow_sidebar.setFixedWidth(260)
        flow_sidebar.setStyleSheet("""
            QFrame {
                background-color: #202536;
                border-right: 1px solid #3a4154;
            }
        """)
        flow_sidebar_layout = QVBoxLayout(flow_sidebar)
        flow_sidebar_layout.setContentsMargins(16, 18, 16, 18)
        flow_sidebar_layout.setSpacing(12)

        flow_sidebar_title = QLabel("Flow 管理")
        flow_sidebar_title.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        flow_sidebar_title.setStyleSheet("color: white;")
        flow_sidebar_layout.addWidget(flow_sidebar_title)

        flow_sidebar_desc = QLabel("切换、增删改当前项目中的流程。")
        flow_sidebar_desc.setWordWrap(True)
        flow_sidebar_desc.setStyleSheet("color: #9aa6bf;")
        flow_sidebar_layout.addWidget(flow_sidebar_desc)

        flow_action_layout = QHBoxLayout()
        flow_action_layout.setContentsMargins(0, 0, 0, 0)
        flow_action_layout.setSpacing(8)

        self.add_flow_btn = QPushButton("➕")
        self.add_flow_btn.setStyleSheet(get_btn_style("#198754"))
        self.add_flow_btn.setFixedSize(40, 40)
        self.add_flow_btn.setToolTip("新建 Flow")
        self.add_flow_btn.clicked.connect(self.add_flow)
        flow_action_layout.addWidget(self.add_flow_btn)

        self.rename_flow_btn = QPushButton("✏️")
        self.rename_flow_btn.setStyleSheet(get_btn_style("#ffc107"))
        self.rename_flow_btn.setFixedSize(40, 40)
        self.rename_flow_btn.setToolTip("重命名当前 Flow")
        self.rename_flow_btn.clicked.connect(self.rename_flow)
        flow_action_layout.addWidget(self.rename_flow_btn)

        self.delete_flow_btn = QPushButton("🗑️")
        self.delete_flow_btn.setStyleSheet(get_btn_style("#dc3545"))
        self.delete_flow_btn.setFixedSize(40, 40)
        self.delete_flow_btn.setToolTip("删除当前 Flow")
        self.delete_flow_btn.clicked.connect(self.delete_flow)
        flow_action_layout.addWidget(self.delete_flow_btn)
        flow_action_layout.addStretch()
        flow_sidebar_layout.addLayout(flow_action_layout)

        self.flow_list = QListWidget()
        self.flow_list.setStyleSheet("""
            QListWidget {
                background-color: #2b2b3b;
                color: #e5edf7;
                border: 1px solid #4e566d;
                border-radius: 6px;
                padding: 6px;
                outline: 0;
            }
            QListWidget::item {
                background-color: #303247;
                border: 1px solid #49526a;
                border-radius: 5px;
                padding: 10px 12px;
                margin: 0 0 6px 0;
            }
            QListWidget::item:selected {
                background-color: #0d6efd;
                color: white;
                border: 2px solid #7fb0ff;
            }
            QListWidget::item:hover {
                background-color: #3a3f58;
                border: 1px solid #7a849d;
            }
        """)
        self.flow_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.flow_list.currentItemChanged.connect(self.on_flow_selection_changed)
        self.flow_list.customContextMenuRequested.connect(self.show_flow_context_menu)
        flow_sidebar_layout.addWidget(self.flow_list)
        flow_sidebar_layout.addStretch()

        left_shell_layout.addWidget(flow_sidebar)

        canvas_widget = QWidget()
        left_layout = QVBoxLayout(canvas_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)

        flow_header_layout = QHBoxLayout()

        flow_header = QLabel("📊 PyFlow 任务流程")
        flow_header.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        flow_header.setStyleSheet("color: white; padding: 15px; background-color: #2b2b3b;")
        flow_header_layout.addWidget(flow_header)

        flow_header_layout.addStretch()

        # 添加节点按钮
        self.add_node_btn = QPushButton("➕ 添加节点")
        self.add_node_btn.setStyleSheet(get_btn_style("#198754"))
        self.add_node_btn.setFixedHeight(40)
        self.add_node_btn.clicked.connect(self.add_new_node)
        flow_header_layout.addWidget(self.add_node_btn)

        self.copy_node_btn = QPushButton("📄 复制节点")
        self.copy_node_btn.setStyleSheet(get_btn_style("#20c997"))
        self.copy_node_btn.setFixedHeight(40)
        self.copy_node_btn.clicked.connect(self.copy_selected_node)
        flow_header_layout.addWidget(self.copy_node_btn)

        self.connect_node_btn = QPushButton("🔗 连接节点")
        self.connect_node_btn.setStyleSheet(get_btn_style("#fd7e14"))
        self.connect_node_btn.setFixedHeight(40)
        self.connect_node_btn.clicked.connect(self.connect_nodes_dialog)
        flow_header_layout.addWidget(self.connect_node_btn)

        # 删除节点按钮
        self.delete_node_btn = QPushButton("🗑️ 删除节点")
        self.delete_node_btn.setStyleSheet(get_btn_style("#dc3545"))
        self.delete_node_btn.setFixedHeight(40)
        self.delete_node_btn.clicked.connect(self.delete_selected_node)
        flow_header_layout.addWidget(self.delete_node_btn)

        left_layout.addLayout(flow_header_layout)

        self.flow_scene = FlowScene()
        self.flow_scene.node_clicked.connect(self.on_node_clicked)
        self.flow_scene.node_position_changed.connect(self._on_node_changed)
        self.flow_scene.connection_delete_requested.connect(self.delete_connection)
        self.flow_scene.connection_create_requested.connect(self.create_connection_from_drag)
        self.flow_view = FlowView(self.flow_scene)
        left_layout.addWidget(self.flow_view)

        left_shell_layout.addWidget(canvas_widget, 1)

        splitter.addWidget(left_widget)

        # 右侧 - 编辑面板
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(10, 10, 10, 10)

        # 使用选项卡切换视图
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                border-radius: 5px;
            }
            QTabBar::tab {
                background-color: #2b2b3b;
                color: white;
                padding: 10px 20px;
                border: 1px solid #444;
                border-radius: 5px 5px 0 0;
            }
            QTabBar::tab:selected {
                background-color: #0d6efd;
            }
        """)

        # 编辑面板
        self.editor_panel = NodeEditorPanel(self.task_manager)
        self.editor_panel.node_changed.connect(self._on_node_changed)
        self.editor_panel.save_requested.connect(self.save_config)
        self.editor_panel.execute_requested.connect(self.execute_selected_node)
        self.tab_widget.addTab(self.editor_panel, "✏️ 节点编辑")

        # 日志面板
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #2b2b3b;
                color: #ccc;
                border: none;
                font-family: Consolas, monospace;
                font-size: 11px;
            }
        """)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        log_layout.addWidget(self.log_text)
        self.tab_widget.addTab(log_widget, "📜 执行日志")

        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setStyleSheet("""
            QTextEdit {
                background-color: #161b26;
                color: #e5edf7;
                border: none;
                font-family: Consolas, 'Microsoft YaHei UI', monospace;
                font-size: 11px;
            }
        """)
        output_widget = QWidget()
        output_layout = QVBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self.output_text)
        self.tab_widget.addTab(output_widget, "📤 实时输出")
        self.output_tab_index = self.tab_widget.count() - 1

        right_layout.addWidget(self.tab_widget)

        # 底部操作栏
        bottom_layout = QHBoxLayout()

        self.reset_btn = QPushButton("🔄 重置所有状态")
        self.reset_btn.setStyleSheet(get_btn_style("#6c757d"))
        self.reset_btn.clicked.connect(self.reset_all)
        bottom_layout.addWidget(self.reset_btn)

        bottom_layout.addStretch()

        self.execute_node_btn = QPushButton("▶️ 执行选中节点")
        self.execute_node_btn.setStyleSheet(get_btn_style("#198754"))
        self.execute_node_btn.clicked.connect(self.execute_selected_node)
        bottom_layout.addWidget(self.execute_node_btn)

        self.execute_all_btn = QPushButton("▶️ 执行全部")
        self.execute_all_btn.setStyleSheet(get_btn_style("#0d6efd"))
        self.execute_all_btn.clicked.connect(self.execute_all_nodes)
        bottom_layout.addWidget(self.execute_all_btn)

        self.stop_btn = QPushButton("⏹️ 停止")
        self.stop_btn.setStyleSheet(get_btn_style("#dc3545"))
        self.stop_btn.clicked.connect(self.stop_execution)
        self.stop_btn.setEnabled(False)
        bottom_layout.addWidget(self.stop_btn)

        right_layout.addLayout(bottom_layout)

        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        self.create_toolbar()

        self.statusBar = QStatusBar()
        self.statusBar.setStyleSheet("color: #888;")
        self.setStatusBar(self.statusBar)
        self.statusBar.showMessage("就绪 - 点击节点查看详情并编辑")

    def create_toolbar(self):
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        toolbar.setStyleSheet("""
            QToolBar {
                background-color: #2b2b3b;
                border: none;
                padding: 5px;
            }
            QToolButton {
                color: white;
                border: none;
                padding: 5px 10px;
                border-radius: 3px;
            }
            QToolButton:hover {
                background-color: #353545;
            }
        """)
        self.addToolBar(toolbar)

        load_action = QAction("📂 加载配置", self)
        load_action.triggered.connect(self.load_config)
        toolbar.addAction(load_action)

        save_action = QAction("💾 保存配置", self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.setShortcutContext(Qt.WidgetWithChildrenShortcut)
        save_action.triggered.connect(self.save_config)
        toolbar.addAction(save_action)

        toolbar.addSeparator()

        sample_action = QAction("📝 加载示例流程", self)
        sample_action.triggered.connect(self.load_sample_flow)
        toolbar.addAction(sample_action)

    def _show_message_box(self, icon, title: str, text: str,
                          buttons=QMessageBox.Ok,
                          default_button=QMessageBox.NoButton):
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle(title)
        box.setText(text)
        box.setStandardButtons(buttons)
        if default_button != QMessageBox.NoButton:
            box.setDefaultButton(default_button)
        box.setStyleSheet(DIALOG_STYLESHEET)
        return box.exec()

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
        dialog = QFileDialog(self, title, directory, name_filter)
        dialog.setFileMode(QFileDialog.ExistingFile)
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setStyleSheet(DIALOG_STYLESHEET)
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                return files[0]
        return ""

    def _select_save_file(self, title: str, name_filter: str, directory: str = "") -> str:
        dialog = QFileDialog(self, title, directory, name_filter)
        dialog.setFileMode(QFileDialog.AnyFile)
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setOption(QFileDialog.DontUseNativeDialog, True)
        dialog.setStyleSheet(DIALOG_STYLESHEET)
        if dialog.exec():
            files = dialog.selectedFiles()
            if files:
                return files[0]
        return ""

    def _prompt_flow_name(self, title: str, label: str, text: str = "") -> Optional[str]:
        value, ok = QInputDialog.getText(self, title, label, text=text)
        value = value.strip()
        if ok and value:
            return value
        return None

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
        if flow_id not in self.flows:
            return

        self.current_flow_id = flow_id
        self.task_manager = self.flows[flow_id]
        self.editor_panel.task_manager = self.task_manager
        self.selected_node_id = None
        self.editor_panel.clear_node()
        self.log_text.clear()
        self.output_text.clear()
        self.flow_scene.load_flow(self.task_manager)
        self._refresh_flow_selector()
        self.statusBar.showMessage(f"当前 Flow：{self.task_manager.flow_name}")

    def _load_flows_from_config(self, config: Dict[str, Any]):
        self.flows = {}
        self.flow_order = []

        if "flows" in config:
            for flow_config in config.get("flows", []):
                manager = TaskFlowManager()
                manager.load_from_dict(flow_config)
                flow_id = manager.flow_id or ensure_unique_flow_id(manager.flow_name, self.flows.keys())
                manager.flow_id = flow_id
                if not manager.flow_name:
                    manager.flow_name = flow_id
                self.flows[flow_id] = manager
                self.flow_order.append(flow_id)
            current_flow_id = config.get("current_flow_id")
        else:
            manager = TaskFlowManager()
            manager.load_from_dict(config)
            manager.flow_id = ensure_unique_flow_id(manager.flow_id or "default", self.flows.keys())
            if not manager.flow_name:
                manager.flow_name = "默认流程"
            self.flows[manager.flow_id] = manager
            self.flow_order.append(manager.flow_id)
            current_flow_id = manager.flow_id

        if not self.flow_order:
            default_manager = TaskFlowManager()
            self.flows[default_manager.flow_id] = default_manager
            self.flow_order.append(default_manager.flow_id)

        self._set_current_flow(current_flow_id if current_flow_id in self.flows else self.flow_order[0])

    def _export_flows_config(self) -> Dict[str, Any]:
        return {
            "current_flow_id": self.current_flow_id,
            "flows": [
                self.flows[flow_id].to_dict(include_flow_meta=True)
                for flow_id in self.flow_order
            ]
        }

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

        flow_id = ensure_unique_flow_id(flow_name, self.flows.keys())
        manager = TaskFlowManager()
        manager.flow_id = flow_id
        manager.flow_name = flow_name
        self.flows[flow_id] = manager
        self.flow_order.append(flow_id)
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

        manager.flow_name = flow_name
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

        index = self.flow_order.index(flow_id)
        del self.flows[flow_id]
        self.flow_order.remove(flow_id)
        next_flow_id = self.flow_order[max(0, index - 1)]
        self._set_current_flow(next_flow_id)
        self._autosave()

    def _on_node_changed(self, node_id: str):
        self.flow_scene.update_node_status(node_id)
        self._autosave()

    def _set_execution_state(self, is_running: bool):
        self.execute_node_btn.setEnabled(not is_running)
        self.execute_all_btn.setEnabled(not is_running)
        self.stop_btn.setEnabled(is_running)

    def execute_selected_node(self):
        if not self.selected_node_id:
            self._show_warning("警告", "请先选择一个节点")
            return
        self.execute_nodes([self.selected_node_id], respect_skip=False)

    def execute_all_nodes(self):
        try:
            execution_order = self.task_manager.get_execution_order()
        except ValueError as e:
            self._show_error("执行失败", str(e))
            return
        self.execute_nodes(execution_order, respect_skip=True)

    def execute_nodes(self, node_ids: List[str], respect_skip: bool = True):
        if not node_ids:
            self._show_warning("警告", "没有可执行的任务")
            return

        if self.worker is not None and self.worker.isRunning():
            self._show_warning("警告", "当前已有 Flow 正在执行")
            return

        self.worker = ExecuteWorker(self.task_manager, node_ids, respect_skip=respect_skip)
        self.worker.node_started.connect(self.on_node_started)
        self.worker.node_finished.connect(self.on_node_finished)
        self.worker.command_executing.connect(self.on_command_executing)
        self.worker.command_finished.connect(self.on_command_finished)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.output_message.connect(self.on_output_message)
        self.worker.all_finished.connect(self.on_all_finished)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.stopped.connect(self.on_worker_stopped)
        self._execution_was_stopped = False
        self.output_text.clear()
        self.tab_widget.setCurrentIndex(self.output_tab_index)
        self._set_execution_state(True)
        self.worker.start()
        self.statusBar.showMessage("正在执行任务...")

    def stop_execution(self):
        if self.worker is None or not self.worker.isRunning():
            return
        self.worker.request_stop()
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
        self._execution_was_stopped = True
        self.statusBar.showMessage("执行已停止")

    @Slot()
    def on_worker_finished(self):
        was_stopped = self._execution_was_stopped
        self._set_execution_state(False)
        self.worker = None
        self._execution_was_stopped = False
        self.statusBar.showMessage("执行已停止" if was_stopped else "执行完成")

    def reset_all(self):
        self.task_manager.reset_status()
        self.flow_scene.load_flow(self.task_manager)
        self.log_text.clear()
        self.output_text.clear()
        self.selected_node_id = None
        self.statusBar.showMessage("已重置所有状态")

    def _load_config_file(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
        self._load_flows_from_config(config)
        self.reset_all()
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
            config = self._export_flows_config()
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            if show_message:
                self.statusBar.showMessage(f"已保存到 {filepath}")
        except Exception as e:
            self._show_error("错误", f"保存配置失败：{e}")

    def _build_sample_flow_manager(self) -> TaskFlowManager:
        manager = TaskFlowManager()
        manager.flow_id = "sample_flow"
        manager.flow_name = "示例流程"

        node1 = manager.add_node("get_reviews", "获取评论", "🌐")
        node1.description = "从 API 获取用户评论数据"
        node1.commands.append(Command(name="检查网络", command="echo '检查网络连接...'"))
        node1.commands.append(Command(name="获取评论", command="echo 'POST http://qdrant:6333/reviews'"))

        node2 = manager.add_node("kmeans", "K-means 聚类", "🧮")
        node2.description = "应用 K-means 算法进行聚类分析"
        node2.commands.append(Command(name="加载数据", command="echo '加载评论数据...'"))
        node2.commands.append(Command(name="执行聚类", command="echo '运行 K-means 算法...'"))

        node3 = manager.add_node("clusters_list", "转换为列表", "📋")
        node3.description = "将聚类结果转换为列表格式"
        node3.commands.append(Command(name="格式化输出", command="echo '转换聚类结果为列表...'"))

        node4 = manager.add_node("agent", "客户洞察代理", "🤖")
        node4.description = "使用 AI 代理分析客户洞察"
        node4.commands.append(Command(name="加载模型", command="echo '加载 OpenAI 模型...'"))
        node4.commands.append(Command(name="分析数据", command="echo '分析聚类数据生成洞察...'"))

        node5 = manager.add_node("gsheets", "写入表格", "📊")
        node5.description = "将洞察结果写入 Google Sheets"
        node5.commands.append(Command(name="连接表格", command="echo '连接到 Google Sheets...'"))
        node5.commands.append(Command(name="追加数据", command="echo '追加洞察数据到表格...'"))

        manager.connect_nodes("get_reviews", "kmeans")
        manager.connect_nodes("kmeans", "clusters_list")
        manager.connect_nodes("clusters_list", "agent")
        manager.connect_nodes("agent", "gsheets")
        return manager

    def load_sample_flow(self):
        sample_manager = self._build_sample_flow_manager()
        self.flows = {sample_manager.flow_id: sample_manager}
        self.flow_order = [sample_manager.flow_id]
        self._set_current_flow(sample_manager.flow_id)
        self.reset_all()
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

    def _insert_node_after(self, anchor_id: str, node_id: str):
        if anchor_id == node_id:
            return

        if anchor_id not in self.task_manager.node_order or node_id not in self.task_manager.node_order:
            return

        self.task_manager.node_order.remove(node_id)
        selected_index = self.task_manager.node_order.index(anchor_id)
        self.task_manager.node_order.insert(selected_index + 1, node_id)

    def _connect_nodes(self, source_id: str, target_id: str, insert_into_chain: bool = False):
        if source_id == target_id:
            return

        previous_targets = []
        if insert_into_chain:
            previous_targets = [
                to_id for from_id, to_id in self.task_manager.connections
                if from_id == source_id and to_id != target_id
            ]
            self.task_manager.connections = [
                (from_id, to_id)
                for from_id, to_id in self.task_manager.connections
                if not (from_id == source_id and to_id in previous_targets)
            ]

        connection = (source_id, target_id)
        if connection not in self.task_manager.connections:
            self.task_manager.connections.append(connection)

        if insert_into_chain:
            for next_id in previous_targets:
                redirected = (target_id, next_id)
                if next_id != target_id and redirected not in self.task_manager.connections:
                    self.task_manager.connections.append(redirected)
            self._insert_node_after(source_id, target_id)

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
        connection = (source_id, target_id)

        if connection in self.task_manager.connections and not connection_data["insert_into_chain"]:
            self._show_warning("警告", "这两个节点已经连接，无需重复添加")
            return

        self._connect_nodes(source_id, target_id, connection_data["insert_into_chain"])
        self.flow_scene.load_flow(self.task_manager)
        self.on_node_clicked(target_id)
        self._autosave()
        self.statusBar.showMessage(
            f"已连接节点：{self.task_manager.nodes[source_id].name} -> {self.task_manager.nodes[target_id].name}"
        )

    @Slot(str, str)
    def create_connection_from_drag(self, source_id: str, target_id: str):
        if source_id == target_id:
            return

        connection = (source_id, target_id)
        if connection in self.task_manager.connections:
            self.statusBar.showMessage(
                f"连接已存在：{self.task_manager.nodes[source_id].name} -> {self.task_manager.nodes[target_id].name}"
            )
            return

        self._connect_nodes(source_id, target_id, insert_into_chain=False)
        self.flow_scene.load_flow(self.task_manager)
        self.on_node_clicked(target_id)
        self._autosave()
        self.statusBar.showMessage(
            f"已连接节点：{self.task_manager.nodes[source_id].name} -> {self.task_manager.nodes[target_id].name}"
        )

    @Slot(str, str)
    def delete_connection(self, source_id: str, target_id: str):
        if (source_id, target_id) not in self.task_manager.connections:
            return

        source_name = self.task_manager.nodes.get(source_id).name if source_id in self.task_manager.nodes else source_id
        target_name = self.task_manager.nodes.get(target_id).name if target_id in self.task_manager.nodes else target_id
        reply = self._show_question(
            "删除连接",
            f"确定要删除连接 '{source_name} -> {target_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.task_manager.connections = [
            (from_id, to_id)
            for from_id, to_id in self.task_manager.connections
            if not (from_id == source_id and to_id == target_id)
        ]
        self.flow_scene.load_flow(self.task_manager)
        self._autosave()
        self.statusBar.showMessage(f"已删除连接：{source_name} -> {target_name}")

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

        node_data = dialog.get_node_data()
        node = self.task_manager.add_node(
            node_data["node_id"],
            node_data["name"],
            node_data["icon"],
        )
        node.description = node_data["description"]
        node.working_dir = node_data["working_dir"] or None
        node.terminal_type = normalize_terminal_type(node_data.get("terminal_type"))
        node.continue_on_error = node_data["continue_on_error"]
        node.position = self._get_new_node_position()

        for cmd_data in node_data.get("commands", []):
            if cmd_data.get("command"):
                node.commands.append(
                    Command(
                        name=cmd_data.get("name", "新命令"),
                        command=cmd_data["command"],
                    )
                )

        if node_data["connect_after_selected"] and self.selected_node_id:
            self._connect_nodes(self.selected_node_id, node.id, insert_into_chain=True)

        self.flow_scene.load_flow(self.task_manager)
        self.on_node_clicked(node.id)
        self._autosave()
        self.statusBar.showMessage(f"已添加节点：{node.name}")

    def copy_selected_node(self):
        """复制当前选中的节点。"""
        if not self.selected_node_id or self.selected_node_id not in self.task_manager.nodes:
            self._show_warning("警告", "请先选择一个要复制的节点")
            return

        source_node = self.task_manager.nodes[self.selected_node_id]
        existing_ids = set(self.task_manager.nodes.keys())
        existing_names = {node.name for node in self.task_manager.nodes.values()}

        new_node_id = ensure_unique_node_id(f"{source_node.id}_copy", existing_ids)
        new_node_name = ensure_unique_node_name(f"{source_node.name} 副本", existing_names)

        copied_node = self.task_manager.add_node(new_node_id, new_node_name, source_node.icon)
        copied_node.description = source_node.description
        copied_node.working_dir = source_node.working_dir
        copied_node.terminal_type = normalize_terminal_type(source_node.terminal_type)
        copied_node.continue_on_error = source_node.continue_on_error
        copied_node.skip_in_flow = source_node.skip_in_flow

        base_position = source_node.position or self._get_new_node_position()
        copied_node.position = {
            "x": float(base_position.get("x", 50.0)) + 60.0,
            "y": float(base_position.get("y", 50.0)) + 60.0,
        }
        copied_node.commands = [
            Command(name=cmd.name, command=cmd.command)
            for cmd in source_node.commands
        ]

        self._insert_node_after(self.selected_node_id, copied_node.id)
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
            node_id = self.selected_node_id

            # 删除相关连接
            self.task_manager.connections = [
                (f, t) for f, t in self.task_manager.connections
                if f != node_id and t != node_id
            ]

            # 从 node_order 中移除
            if node_id in self.task_manager.node_order:
                self.task_manager.node_order.remove(node_id)

            # 从 nodes 中移除
            if node_id in self.task_manager.nodes:
                del self.task_manager.nodes[node_id]

            # 重新加载流程
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
