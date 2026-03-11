import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal

from .models import NodeStatus, TaskFlowManager
from .utils import build_node_log_path


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

    def __init__(self, task_manager: TaskFlowManager, node_ids: List[str], respect_skip: bool = True,
                 route_by_connections: bool = False):
        super().__init__()
        self.task_manager = task_manager
        self.node_ids = node_ids
        self.respect_skip = respect_skip
        self.route_by_connections = route_by_connections
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

    def _resolve_runtime_node_ids(self) -> List[str]:
        ordered_ids = [node_id for node_id in self.task_manager.get_execution_order(self.node_ids) if node_id in self.task_manager.nodes]
        return ordered_ids

    def _process_node(self, node_id: str) -> tuple[bool, str, bool]:
        node = self.task_manager.nodes[node_id]
        branch_result = "success"
        stopped_due_to_failure = False

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
            return True, branch_result, stopped_due_to_failure

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
                    self.log_message.emit("⚠️  节点因命令失败而中止")
                    stopped_due_to_failure = True
                    break

        if node_success:
            node.status = NodeStatus.SUCCESS
        else:
            node.status = NodeStatus.FAILED
            branch_result = "failed"

        self.node_finished.emit(node_id, node_success)
        self.log_message.emit(f"\n节点 '{node.name}' 完成 - 状态：{node.get_status_text()}")
        finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._emit_node_output(
            node_id,
            log_path,
            f"\n{'='*60}\n[节点完成] {node.name} | 状态 {node.get_status_text()} | 结束时间 {finished_at}\n{'='*60}\n"
        )
        return node_success, branch_result, stopped_due_to_failure

    def run(self):
        all_success = True
        runtime_node_ids = self._resolve_runtime_node_ids()
        active_nodes = set(runtime_node_ids) if not self.route_by_connections else set(self.task_manager.get_root_node_ids(runtime_node_ids))

        for node_id in runtime_node_ids:
            if self._stop_requested:
                all_success = False
                break
            if node_id not in self.task_manager.nodes or node_id not in active_nodes:
                continue

            node_success, branch_result, stopped_due_to_failure = self._process_node(node_id)
            if not node_success:
                all_success = False

            if self.route_by_connections:
                matching_connections = [
                    connection for connection in self.task_manager.get_outgoing_connections(node_id)
                    if connection.normalized_condition() in (branch_result, "always")
                ]
                for connection in matching_connections:
                    active_nodes.add(connection.to_id)

            if self._stop_requested:
                all_success = False
                break

            if stopped_due_to_failure:
                if not self.route_by_connections:
                    self.log_message.emit("\n⚠️  执行中止")
                    break
                has_failover = bool(self.task_manager.get_outgoing_connections(node_id, "failed") or self.task_manager.get_outgoing_connections(node_id, "always"))
                if not has_failover:
                    self.log_message.emit("\n⚠️  执行中止")
                    break

        self.all_finished.emit(all_success)
        if self._stop_requested:
            self.log_message.emit(f"\n{'='*60}\n⏹️ Flow 执行已停止\n{'='*60}")
            self.stopped.emit()
        elif all_success:
            self.log_message.emit(f"\n{'='*60}\n✅ 所有选中节点执行完成!\n{'='*60}")
        else:
            self.log_message.emit(f"\n{'='*60}\n⚠️ 部分节点执行失败\n{'='*60}")


