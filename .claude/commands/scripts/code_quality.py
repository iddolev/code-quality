"""Run code quality tools on a Python file or folder."""

import subprocess
import sys
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


def _cmd_from_template(path: Path, cmd_tempate: Tuple[str, ...]) -> list[str]:
    """Build a command list by replacing 'path' placeholders with the actual path."""
    return [str(path) if part == "path" else part
            for part in cmd_tempate]


def _run_tool(path: Path, cmd_template: tuple[str, ...]) -> None:
    """Run a single tool command and print its output."""
    cmd = _cmd_from_template(path, cmd_template)
    print(f"{TOOL_SEPARATOR} {cmd[0]} {TOOL_SEPARATOR}")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)
    except FileNotFoundError:
        print(f"ERROR: {cmd[0]} is not installed.")
    print()


def _check_file(path: Path) -> None:
    """Run all file-level quality tools on a single Python file."""
    for cmd_template in FILE_TOOLS:
        _run_tool(path, cmd_template)


def _collect_python_files(folder: Path) -> list[Path]:
    """Recursively collect .py files, skipping excluded directories."""
    files = [item
             for item in sorted(folder.rglob("*.py"))
             if not any(part in EXCLUDED_DIRS
                        # Check only parent directory names (not the filename) against EXCLUDED_DIRS
                        for part in item.relative_to(folder).parent.parts)]
    return files


def main() -> None:
    if len(sys.argv) < 2:
        print("Error: No path provided.")
        print("Usage: python code_quality.py <file_or_folder>")
        sys.exit(1)

    path = Path(sys.argv[1])

    if not path.exists():
        print(f'Error: "{path}" does not exist.')
        sys.exit(1)

    if path.is_file():
        if path.suffix.lower() != ".py":
            print(f'Error: "{path}" is not a Python file (.py).')
            sys.exit(1)
        _check_file(path)
    elif path.is_dir():
        py_files = _collect_python_files(path)
        if not py_files:
            print(f'No Python files found in "{path}".')
            sys.exit(1)
        for py_file in py_files:
            print(f"{FILE_SEPARATOR} {py_file} {FILE_SEPARATOR}")
            _check_file(py_file)
        for cmd_template in FOLDER_TOOLS:
            _run_tool(path, cmd_template)
    else:
        print(f'Error: "{path}" is not a file or directory.')
        sys.exit(1)


if __name__ == "__main__":
    main()
