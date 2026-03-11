import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import TaskFlowManager
from .utils import ensure_unique_flow_id


@dataclass
class LoadedFlows:
    flows: Dict[str, TaskFlowManager]
    flow_order: List[str]
    current_flow_id: str
    theme_name: Optional[str] = None


def load_json_file(filepath: str) -> Dict[str, Any]:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在：{filepath}")

    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json_file(filepath: str, payload: Dict[str, Any]) -> None:
    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False)


def load_flow_manager(flow_config: Dict[str, Any]) -> TaskFlowManager:
    manager = TaskFlowManager()
    manager.load_from_dict(flow_config)
    return manager


def save_flow_manager(filepath: str, manager: TaskFlowManager) -> None:
    save_json_file(filepath, manager.to_dict(include_flow_meta=True))


def load_flows_config(config: Dict[str, Any]) -> LoadedFlows:
    flows: Dict[str, TaskFlowManager] = {}
    flow_order: List[str] = []

    if "flows" in config:
        flow_configs = config.get("flows", [])
        current_flow_id = config.get("current_flow_id")
    else:
        flow_configs = [config]
        current_flow_id = None

    for flow_config in flow_configs:
        manager = load_flow_manager(flow_config)
        flow_id = manager.flow_id or ensure_unique_flow_id(manager.flow_name, flows.keys())
        manager.flow_id = flow_id
        if not manager.flow_name:
            manager.flow_name = flow_id if "flows" in config else "默认流程"
        flows[flow_id] = manager
        flow_order.append(flow_id)
        if current_flow_id is None:
            current_flow_id = flow_id

    if not flow_order:
        default_manager = TaskFlowManager()
        flows[default_manager.flow_id] = default_manager
        flow_order.append(default_manager.flow_id)
        current_flow_id = default_manager.flow_id

    return LoadedFlows(
        flows=flows,
        flow_order=flow_order,
        current_flow_id=current_flow_id if current_flow_id in flows else flow_order[0],
        theme_name=config.get("theme"),
    )


def export_flows_config(
    flows: Dict[str, TaskFlowManager],
    flow_order: Iterable[str],
    current_flow_id: Optional[str],
    theme_name: str,
) -> Dict[str, Any]:
    return {
        "current_flow_id": current_flow_id,
        "theme": theme_name,
        "flows": [
            flows[flow_id].to_dict(include_flow_meta=True)
            for flow_id in flow_order
            if flow_id in flows
        ],
    }


def load_flows_from_file(filepath: str) -> LoadedFlows:
    return load_flows_config(load_json_file(filepath))


def save_flows_to_file(
    filepath: str,
    flows: Dict[str, TaskFlowManager],
    flow_order: Iterable[str],
    current_flow_id: Optional[str],
    theme_name: str,
) -> None:
    save_json_file(
        filepath,
        export_flows_config(flows, flow_order, current_flow_id, theme_name),
    )
