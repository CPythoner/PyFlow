import sys
from pathlib import Path

NODE_ICON_OPTIONS = ["📦", "🌐", "🧮", "📋", "🤖", "📊", "⚙️", "🔥", "🚀", "✅", "▶️", "❌"]
NODE_TEMPLATES_PATH = Path(__file__).resolve().parent.parent / "node_templates.json"
FLOW_CONFIG_PATH = Path(__file__).resolve().parent.parent / "flow_config.json"
NODE_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
DEFAULT_TERMINAL_TYPE = "cmd" if sys.platform.startswith("win") else "bash"
TERMINAL_TYPE_OPTIONS = [
    ("cmd", "CMD"),
    ("powershell", "PowerShell"),
    ("bash", "Bash"),
]
CONNECTION_CONDITION_OPTIONS = [
    ("success", "成功后"),
    ("failed", "失败后"),
    ("always", "总是"),
]
