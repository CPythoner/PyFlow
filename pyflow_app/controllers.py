from typing import Callable, Dict, List, Optional

from PySide6.QtCore import QObject, Signal

from .executor import ExecuteWorker
from .models import Command, FlowConnection, TaskFlowManager
from .utils import ensure_unique_node_id, ensure_unique_node_name, normalize_connection_condition, normalize_terminal_type


class ExecutionController(QObject):
    node_started = Signal(str)
    node_finished = Signal(str, bool)
    command_executing = Signal(str, str, str)
    command_finished = Signal(str, str, bool, float)
    log_message = Signal(str)
    output_message = Signal(str, str)
    all_finished = Signal(bool)
    finished = Signal()
    stopped = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker: Optional[ExecuteWorker] = None
        self.execution_was_stopped = False

    def is_running(self) -> bool:
        return self.worker is not None and self.worker.isRunning()

    def start(self, task_manager: TaskFlowManager, node_ids: List[str], respect_skip: bool = True, route_by_connections: bool = False):
        if self.is_running():
            raise RuntimeError("当前已有 Flow 正在执行")
        self.worker = ExecuteWorker(task_manager, node_ids, respect_skip=respect_skip, route_by_connections=route_by_connections)
        self.worker.node_started.connect(self.node_started)
        self.worker.node_finished.connect(self.node_finished)
        self.worker.command_executing.connect(self.command_executing)
        self.worker.command_finished.connect(self.command_finished)
        self.worker.log_message.connect(self.log_message)
        self.worker.output_message.connect(self.output_message)
        self.worker.all_finished.connect(self.all_finished)
        self.worker.finished.connect(self._on_worker_finished)
        self.worker.stopped.connect(self._on_worker_stopped)
        self.execution_was_stopped = False
        self.worker.start()

    def stop(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()

    def _on_worker_stopped(self):
        self.execution_was_stopped = True
        self.stopped.emit()

    def _on_worker_finished(self):
        self.worker = None
        self.finished.emit()


class FlowEditController:
    def __init__(self, task_manager_getter: Callable[[], TaskFlowManager], selected_node_getter: Callable[[], Optional[str]]):
        self._task_manager_getter = task_manager_getter
        self._selected_node_getter = selected_node_getter

    @property
    def task_manager(self) -> TaskFlowManager:
        return self._task_manager_getter()

    @property
    def selected_node_id(self) -> Optional[str]:
        return self._selected_node_getter()

    def insert_node_after(self, anchor_id: str, node_id: str):
        if anchor_id == node_id:
            return
        task_manager = self.task_manager
        if anchor_id not in task_manager.node_order or node_id not in task_manager.node_order:
            return
        task_manager.node_order.remove(node_id)
        selected_index = task_manager.node_order.index(anchor_id)
        task_manager.node_order.insert(selected_index + 1, node_id)

    def connect_nodes(self, source_id: str, target_id: str, insert_into_chain: bool = False, condition: str = "success"):
        if source_id == target_id:
            return
        task_manager = self.task_manager
        condition = normalize_connection_condition(condition)
        previous_targets = []
        if insert_into_chain:
            previous_targets = [
                connection.to_id for connection in task_manager.connections
                if connection.from_id == source_id and connection.to_id != target_id and connection.normalized_condition() == "success"
            ]
            task_manager.connections = [
                connection for connection in task_manager.connections
                if not (connection.from_id == source_id and connection.to_id in previous_targets and connection.normalized_condition() == "success")
            ]

        if task_manager.find_connection(source_id, target_id, condition) is None:
            task_manager.connections.append(FlowConnection(source_id, target_id, condition))

        if insert_into_chain:
            for next_id in previous_targets:
                if next_id != target_id and task_manager.find_connection(target_id, next_id, "success") is None:
                    task_manager.connections.append(FlowConnection(target_id, next_id, "success"))
            self.insert_node_after(source_id, target_id)

    def delete_connection(self, source_id: str, target_id: str, condition: str):
        task_manager = self.task_manager
        normalized = normalize_connection_condition(condition)
        task_manager.connections = [
            connection for connection in task_manager.connections
            if not (connection.from_id == source_id and connection.to_id == target_id and connection.normalized_condition() == normalized)
        ]

    def update_connection_condition(self, source_id: str, target_id: str, old_condition: str, new_condition: str) -> bool:
        task_manager = self.task_manager
        old_condition = normalize_connection_condition(old_condition)
        new_condition = normalize_connection_condition(new_condition)
        if old_condition == new_condition:
            return False
        connection = task_manager.find_connection(source_id, target_id, old_condition)
        if connection is None or task_manager.find_connection(source_id, target_id, new_condition) is not None:
            return False
        connection.condition = new_condition
        return True

    def add_node(self, node_data: Dict[str, object], position: Dict[str, float]):
        task_manager = self.task_manager
        node = task_manager.add_node(str(node_data["node_id"]), str(node_data["name"]), str(node_data["icon"]))
        node.description = str(node_data.get("description", ""))
        node.working_dir = str(node_data.get("working_dir", "")) or None
        node.terminal_type = normalize_terminal_type(node_data.get("terminal_type"))
        node.continue_on_error = bool(node_data.get("continue_on_error", False))
        node.position = position
        for cmd_data in node_data.get("commands", []):
            if cmd_data.get("command"):
                node.commands.append(Command(name=cmd_data.get("name", "新命令"), command=cmd_data["command"]))
        if node_data.get("connect_after_selected") and self.selected_node_id:
            self.connect_nodes(self.selected_node_id, node.id, insert_into_chain=True)
        return node

    def copy_selected_node(self, position_getter: Callable[[], Dict[str, float]]):
        selected_node_id = self.selected_node_id
        task_manager = self.task_manager
        if not selected_node_id or selected_node_id not in task_manager.nodes:
            return None
        source_node = task_manager.nodes[selected_node_id]
        new_node_id = ensure_unique_node_id(f"{source_node.id}_copy", set(task_manager.nodes.keys()))
        new_node_name = ensure_unique_node_name(f"{source_node.name} 副本", {node.name for node in task_manager.nodes.values()})
        copied_node = task_manager.add_node(new_node_id, new_node_name, source_node.icon)
        copied_node.description = source_node.description
        copied_node.working_dir = source_node.working_dir
        copied_node.terminal_type = normalize_terminal_type(source_node.terminal_type)
        copied_node.continue_on_error = source_node.continue_on_error
        copied_node.skip_in_flow = source_node.skip_in_flow
        base_position = source_node.position or position_getter()
        copied_node.position = {"x": float(base_position.get("x", 50.0)) + 60.0, "y": float(base_position.get("y", 50.0)) + 60.0}
        copied_node.commands = [Command(name=cmd.name, command=cmd.command) for cmd in source_node.commands]
        self.insert_node_after(selected_node_id, copied_node.id)
        return copied_node

    def delete_selected_node(self) -> bool:
        selected_node_id = self.selected_node_id
        task_manager = self.task_manager
        if not selected_node_id:
            return False
        task_manager.connections = [connection for connection in task_manager.connections if connection.from_id != selected_node_id and connection.to_id != selected_node_id]
        if selected_node_id in task_manager.node_order:
            task_manager.node_order.remove(selected_node_id)
        if selected_node_id in task_manager.nodes:
            del task_manager.nodes[selected_node_id]
        return True
