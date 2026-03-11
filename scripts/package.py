#!/usr/bin/env python3

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "pyflow.py"
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"


def detect_system() -> tuple[str, str, str]:
    system = platform.system()
    if system == "Windows":
        return system, ";", ".exe"
    if system == "Darwin":
        return system, ":", ""
    if system == "Linux":
        return system, ":", ""
    raise RuntimeError(f"暂不支持的系统: {system}")


def ensure_pyinstaller() -> None:
    if shutil.which("pyinstaller"):
        return
    raise RuntimeError(
        "未找到 pyinstaller，请先执行: "
        f"{sys.executable} -m pip install pyinstaller"
    )


def build_command() -> tuple[list[str], Path]:
    system, data_separator, executable_suffix = detect_system()
    target_name = f"pyflow-{system.lower()}"
    target_path = DIST_DIR / f"{target_name}{executable_suffix}"

    command = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--name",
        target_name,
        "--add-data",
        f"node_templates.json{data_separator}.",
        "--add-data",
        f"flow_config.json{data_separator}.",
        str(ENTRYPOINT),
    ]
    return command, target_path


def cleanup() -> None:
    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Package PyFlow with PyInstaller using platform-aware settings.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the packaging command without executing it.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command, target_path = build_command()
    print(f"[PyFlow] Packaging for {platform.system()} with: {' '.join(command)}")
    if args.dry_run:
        print(f"[PyFlow] Expected output: {target_path}")
        return 0

    ensure_pyinstaller()
    completed = subprocess.run(command, cwd=ROOT)
    if completed.returncode != 0:
        return completed.returncode

    cleanup()
    print(f"[PyFlow] Package created: {target_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
