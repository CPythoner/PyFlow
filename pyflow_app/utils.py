import json
import locale
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from PySide6.QtWidgets import QFileDialog

from .config import (
    CONNECTION_CONDITION_OPTIONS,
    DEFAULT_TERMINAL_TYPE,
    NODE_LOG_DIR,
    NODE_TEMPLATES_PATH,
    TERMINAL_TYPE_OPTIONS,
)
from .theme import build_dialog_stylesheet


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


def normalize_connection_condition(value: Optional[str]) -> str:
    if not value:
        return "success"
    normalized = str(value).strip().lower()
    supported = {item[0] for item in CONNECTION_CONDITION_OPTIONS}
    return normalized if normalized in supported else "success"


def get_connection_condition_label(condition: str) -> str:
    labels = dict(CONNECTION_CONDITION_OPTIONS)
    return labels.get(normalize_connection_condition(condition), "成功后")


def select_directory(parent, title: str, directory: str = "") -> str:
    """Open a themed directory chooser."""
    dialog = QFileDialog(parent, title, directory or "")
    dialog.setFileMode(QFileDialog.Directory)
    dialog.setOption(QFileDialog.ShowDirsOnly, True)
    dialog.setOption(QFileDialog.DontUseNativeDialog, True)
    dialog.setStyleSheet(build_dialog_stylesheet())
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
