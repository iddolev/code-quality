"""Run code quality tools on a Python file or folder."""

import subprocess
import sys
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path

EXCLUDED_DIRS = {"venv", "sandbox", "tmp", "__pycache__", ".git"}

FILE_TOOLS = [
    ("ruff", "check", "path"),
    ("pylint", "path"),
    ("pyright", "path"),
    ("radon", "cc", "path", "-s", "-n", "C"),
    ("bandit", "path"),
    ("vulture", "path"),
]

FOLDER_TOOLS = [
    ("deptry", "path"),
    # pip-audit doesn't need a target as it checks venv
    ("pip-audit",),
]


TOOL_SEPARATOR = "-" * 20
FILE_SEPARATOR = "=" * 20


def _cmd_from_template(path: Path, cmd_template: tuple[str, ...]) -> list[str]:
    """Build a command list by replacing 'path' placeholders with the actual path."""
    return [str(path) if part == "path" else part
            for part in cmd_template]


def _run_tool(path: Path, cmd_template: tuple[str, ...], log_file: TextIOWrapper, missing_tools: list[str]) -> None:
    """Run a single tool command and write its output to log_file."""
    cmd = _cmd_from_template(path, cmd_template)
    log_file.write(f"{TOOL_SEPARATOR} {cmd[0]} {TOOL_SEPARATOR}\n")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            log_file.write(result.stdout)
            if not result.stdout.endswith("\n"):
                log_file.write("\n")
        if result.stderr:
            for line in result.stderr.splitlines():
                log_file.write(f"[stderr] {line}\n")
        if not result.stdout and not result.stderr:
            log_file.write("No issues found.\n")
    except FileNotFoundError:
        log_file.write(f"ERROR: {cmd[0]} is not installed.\n")
        missing_tools.append(cmd[0])
    log_file.write("\n")


def _check_file(path: Path, log_file: TextIOWrapper, missing_tools: list[str]) -> None:
    """Run all file-level quality tools on a single Python file."""
    for cmd_template in FILE_TOOLS:
        _run_tool(path, cmd_template, log_file, missing_tools)


def _collect_python_files(folder: Path) -> list[Path]:
    """Recursively collect .py files, skipping excluded directories."""
    files = [item
             for item in sorted(folder.rglob("*.py"))
             if not any(part in EXCLUDED_DIRS
                        # Check only parent directory names (not the filename) against EXCLUDED_DIRS
                        for part in item.relative_to(folder).parent.parts)]
    return files


def _build_log_path(target: Path) -> Path:
    """Build the log file path: tmp/quality_review/<name>_YYYYMMDDhhmm.log."""
    name = target.stem if target.is_file() else target.name
    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    log_dir = Path("tmp/quality_review")
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{name}_{timestamp}.log"


def _run_checks(path: Path, log_file: TextIOWrapper, missing_tools: list[str]) -> None:
    """Run file-level and folder-level checks, dispatching by path type."""
    if path.is_file():
        if path.suffix.lower() != ".py":
            print(f'Error: "{path}" is not a Python file (.py).')
            sys.exit(1)
        _check_file(path, log_file, missing_tools)
    elif path.is_dir():
        py_files = _collect_python_files(path)
        if not py_files:
            print(f'No Python files found in "{path}".')
            sys.exit(1)
        for py_file in py_files:
            log_file.write(f"{FILE_SEPARATOR} {py_file} {FILE_SEPARATOR}\n")
            _check_file(py_file, log_file, missing_tools)
        for cmd_template in FOLDER_TOOLS:
            _run_tool(path, cmd_template, log_file, missing_tools)
    else:
        print(f'Error: "{path}" is not a file or directory.')
        sys.exit(1)


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: No path provided.")
        print("Usage: python code_quality.py <file_or_folder>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if not path.exists():
        print(f'Error: "{path}" does not exist.')
        sys.exit(1)

    log_path = _build_log_path(path)
    missing_tools: list[str] = []

    with open(log_path, "w", encoding="utf-8") as log_file:
        _run_checks(path, log_file, missing_tools)

        if missing_tools:
            log_file.write(f"{FILE_SEPARATOR} MISSING TOOLS SUMMARY {FILE_SEPARATOR}\n")
            for tool in sorted(set(missing_tools)):
                log_file.write(f"  - {tool}\n")
            log_file.write("\n")

    print(f"Report written to {log_path}")


if __name__ == "__main__":
    main()
