import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PySide6.QtGui import QColor

from .config import DEFAULT_TERMINAL_TYPE
from .utils import (
    build_shell_command,
    decode_process_output,
    infer_terminal_type,
    looks_like_powershell_command,
    normalize_connection_condition,
    normalize_shell_command,
    normalize_terminal_type,
)


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


@dataclass
class FlowConnection:
    from_id: str
    to_id: str
    condition: str = "success"

    def normalized_condition(self) -> str:
        return normalize_connection_condition(self.condition)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "from": self.from_id,
            "to": self.to_id,
        }
        condition = self.normalized_condition()
        if condition != "success":
            data["condition"] = condition
        return data


class TaskFlowManager:
    """任务流程管理器"""

    def __init__(self):
        self.flow_id: str = "default"
        self.flow_name: str = "默认流程"
        self.nodes: Dict[str, TaskNode] = {}
        self.node_order: List[str] = []
        self.connections: List[FlowConnection] = []

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
            if not isinstance(connection, dict):
                continue
            self.connect_nodes(
                connection['from'],
                connection['to'],
                connection.get('condition', 'success'),
            )

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
            "connections": [connection.to_dict() for connection in self.connections]
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

    def connect_nodes(self, from_id: str, to_id: str, condition: str = "success") -> None:
        """连接两个节点"""
        if from_id in self.nodes and to_id in self.nodes:
            condition = normalize_connection_condition(condition)
            if self.find_connection(from_id, to_id, condition) is None:
                self.connections.append(FlowConnection(from_id, to_id, condition))

    def find_connection(self, from_id: str, to_id: str, condition: Optional[str] = None) -> Optional[FlowConnection]:
        normalized = normalize_connection_condition(condition) if condition is not None else None
        for connection in self.connections:
            if connection.from_id != from_id or connection.to_id != to_id:
                continue
            if normalized is None or connection.normalized_condition() == normalized:
                return connection
        return None

    def get_outgoing_connections(self, node_id: str, condition: Optional[str] = None) -> List[FlowConnection]:
        normalized = normalize_connection_condition(condition) if condition is not None else None
        return [
            connection for connection in self.connections
            if connection.from_id == node_id and (normalized is None or connection.normalized_condition() == normalized)
        ]

    def get_incoming_connections(self, node_id: str) -> List[FlowConnection]:
        return [connection for connection in self.connections if connection.to_id == node_id]

    def load_from_file(self, filepath: str) -> None:
        """从配置文件加载任务流程"""
        from .persistence import load_json_file

        self.load_from_dict(load_json_file(filepath))

    def save_to_file(self, filepath: str) -> None:
        """保存任务流程到配置文件"""
        from .persistence import save_flow_manager

        save_flow_manager(filepath, self)

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
        for connection in self.connections:
            if connection.from_id in candidate_set and connection.to_id in candidate_set and connection.from_id != connection.to_id:
                outgoing[connection.from_id].add(connection.to_id)
                incoming[connection.to_id].add(connection.from_id)

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

    def validate_flow(self, node_ids: Optional[List[str]] = None) -> List[str]:
        candidate_ids = list(node_ids) if node_ids is not None else list(self.node_order)
        candidate_set = {node_id for node_id in candidate_ids if node_id in self.nodes}
        if not candidate_set:
            return ["没有可执行的节点。"]

        errors: List[str] = []
        try:
            self.get_execution_order(list(candidate_set))
        except ValueError as exc:
            errors.append(str(exc))

        root_nodes = {
            node_id for node_id in candidate_set
            if not any(connection.to_id == node_id and connection.from_id in candidate_set for connection in self.connections)
        }
        if not root_nodes:
            errors.append("流程中没有起始节点。")

        reachable = set(root_nodes)
        queue = list(root_nodes)
        while queue:
            current = queue.pop(0)
            for connection in self.get_outgoing_connections(current):
                if connection.to_id in candidate_set and connection.to_id not in reachable:
                    reachable.add(connection.to_id)
                    queue.append(connection.to_id)
        isolated = sorted(candidate_set.difference(reachable), key=lambda node_id: self.node_order.index(node_id))
        if isolated:
            errors.append(f"存在不可从起始节点到达的节点: {', '.join(isolated)}")

        for node_id in candidate_ids:
            if node_id not in candidate_set:
                continue
            node = self.nodes[node_id]
            if not node.commands:
                errors.append(f"节点“{node.name}”没有配置命令。")
            elif all(not cmd.command.strip() for cmd in node.commands):
                errors.append(f"节点“{node.name}”的命令内容为空。")
            if node.working_dir and not Path(node.working_dir).exists():
                errors.append(f"节点“{node.name}”的工作目录不存在: {node.working_dir}")

            success_edges = self.get_outgoing_connections(node_id, "success")
            failed_edges = self.get_outgoing_connections(node_id, "failed")
            always_edges = self.get_outgoing_connections(node_id, "always")
            if len(success_edges) > 1:
                errors.append(f"节点“{node.name}”存在多条“成功后”连线，请明确唯一分支。")
            if len(failed_edges) > 1:
                errors.append(f"节点“{node.name}”存在多条“失败后”连线，请明确唯一分支。")
            if len(always_edges) > 1:
                errors.append(f"节点“{node.name}”存在多条“总是”连线，请明确唯一分支。")

        return errors

    def get_root_node_ids(self, node_ids: Optional[List[str]] = None) -> List[str]:
        candidate_ids = list(node_ids) if node_ids is not None else list(self.node_order)
        candidate_set = {node_id for node_id in candidate_ids if node_id in self.nodes}
        order_index = {node_id: index for index, node_id in enumerate(self.node_order)}
        roots = [
            node_id for node_id in candidate_set
            if not any(connection.to_id == node_id and connection.from_id in candidate_set for connection in self.connections)
        ]
        return sorted(roots, key=lambda node_id: order_index.get(node_id, 10 ** 9))

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
