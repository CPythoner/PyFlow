import json
from typing import Any, Dict, List, Optional

from .models import TaskFlowManager
from .persistence import load_flows_config, load_json_file, save_flows_to_file
from .sample_flow import build_sample_flow_manager
from .theme import CURRENT_THEME_NAME
from .utils import ensure_unique_flow_id


class FlowWorkspace:
    def __init__(self, theme_name: str = CURRENT_THEME_NAME):
        self.theme_name = theme_name
        self.task_manager = TaskFlowManager()
        self.flows: Dict[str, TaskFlowManager] = {}
        self.flow_order: List[str] = []
        self.current_flow_id: Optional[str] = None
        self.undo_stack: List[Dict[str, Any]] = []
        self.redo_stack: List[Dict[str, Any]] = []
        self.restoring_history = False

    def select_flow(self, flow_id: str) -> Optional[TaskFlowManager]:
        if flow_id not in self.flows:
            return None
        self.current_flow_id = flow_id
        self.task_manager = self.flows[flow_id]
        return self.task_manager

    def load_from_config(self, config: Dict[str, Any]) -> None:
        loaded = load_flows_config(config)
        if loaded.theme_name:
            self.theme_name = loaded.theme_name
        self.flows = loaded.flows
        self.flow_order = loaded.flow_order
        self.select_flow(loaded.current_flow_id)

    def export_config(self) -> Dict[str, Any]:
        return {
            "current_flow_id": self.current_flow_id,
            "theme": self.theme_name,
            "flows": [
                self.flows[flow_id].to_dict(include_flow_meta=True)
                for flow_id in self.flow_order
                if flow_id in self.flows
            ],
        }

    def capture_history_snapshot(self) -> Dict[str, Any]:
        return json.loads(json.dumps(self.export_config(), ensure_ascii=False))

    def push_undo_snapshot(self) -> None:
        if self.restoring_history:
            return
        snapshot = self.capture_history_snapshot()
        if self.undo_stack and self.undo_stack[-1] == snapshot:
            return
        self.undo_stack.append(snapshot)
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def restore_history_snapshot(self, snapshot: Dict[str, Any]) -> None:
        self.restoring_history = True
        try:
            self.load_from_config(snapshot)
        finally:
            self.restoring_history = False

    def can_undo(self) -> bool:
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        return bool(self.redo_stack)

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        current_snapshot = self.capture_history_snapshot()
        snapshot = self.undo_stack.pop()
        if snapshot == current_snapshot and self.undo_stack:
            snapshot = self.undo_stack.pop()
        self.redo_stack.append(current_snapshot)
        self.restore_history_snapshot(snapshot)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        current_snapshot = self.capture_history_snapshot()
        snapshot = self.redo_stack.pop()
        self.undo_stack.append(current_snapshot)
        self.restore_history_snapshot(snapshot)
        return True

    def add_flow(self, flow_name: str) -> str:
        flow_id = ensure_unique_flow_id(flow_name, self.flows.keys())
        manager = TaskFlowManager()
        manager.flow_id = flow_id
        manager.flow_name = flow_name
        self.flows[flow_id] = manager
        self.flow_order.append(flow_id)
        self.select_flow(flow_id)
        return flow_id

    def rename_flow(self, flow_id: str, flow_name: str) -> None:
        self.flows[flow_id].flow_name = flow_name

    def delete_flow(self, flow_id: str) -> Optional[str]:
        if flow_id not in self.flows:
            return None
        index = self.flow_order.index(flow_id)
        del self.flows[flow_id]
        self.flow_order.remove(flow_id)
        next_flow_id = self.flow_order[max(0, index - 1)] if self.flow_order else None
        if next_flow_id:
            self.select_flow(next_flow_id)
        return next_flow_id

    def reset_history(self) -> None:
        self.undo_stack.clear()
        self.redo_stack.clear()

    def load_from_file(self, filepath: str) -> None:
        self.load_from_config(load_json_file(filepath))

    def save_to_file(self, filepath: str) -> None:
        save_flows_to_file(
            filepath,
            self.flows,
            self.flow_order,
            self.current_flow_id,
            self.theme_name,
        )

    def load_sample_flow(self) -> None:
        sample_manager = build_sample_flow_manager()
        self.flows = {sample_manager.flow_id: sample_manager}
        self.flow_order = [sample_manager.flow_id]
        self.select_flow(sample_manager.flow_id)
        self.reset_history()
