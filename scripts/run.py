#!/usr/bin/env python3

import argparse
import platform
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "pyflow.py"


def build_command() -> list[str]:
    system = platform.system()
    python_executable = sys.executable

    if system == "Windows":
        return [python_executable, str(ENTRYPOINT)]
    if system in {"Darwin", "Linux"}:
        return [python_executable, str(ENTRYPOINT)]
    raise RuntimeError(f"暂不支持的系统: {system}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run PyFlow with platform-aware defaults.")
    parser.add_argument("--dry-run", action="store_true", help="Only print the command without launching the app.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    command = build_command()
    print(f"[PyFlow] Running on {platform.system()} with: {' '.join(command)}")
    if args.dry_run:
        return 0
    completed = subprocess.run(command, cwd=ROOT)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
