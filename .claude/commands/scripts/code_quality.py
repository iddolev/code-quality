"""Run code quality tools on a Python file or folder."""

import subprocess
import sys
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


class QualityRunner:
    """Runs code quality tools and writes results to a log file."""

    def __init__(self, log_file: TextIOWrapper):
        self._log_file = log_file
        self._missing_tools: list[str] = []

    @staticmethod
    def _cmd_from_template(path: Path, cmd_template: tuple[str, ...]) -> list[str]:
        """Build a command list by replacing 'path' placeholders with the actual path."""
        return [str(path) if part == "path" else part
                for part in cmd_template]

    def _run_tool(self, path: Path, cmd_template: tuple[str, ...]) -> None:
        """Run a single tool command and write its output to the log file."""
        cmd = self._cmd_from_template(path, cmd_template)
        self._log_file.write(f"{TOOL_SEPARATOR} {cmd[0]} {TOOL_SEPARATOR}\n")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            self._write_result(result)
        except FileNotFoundError:
            self._log_file.write(f"ERROR: {cmd[0]} is not installed.\n")
            self._missing_tools.append(cmd[0])
        except subprocess.TimeoutExpired:
            self._log_file.write(f"ERROR: {cmd[0]} timed out after 120 seconds.\n")
        self._log_file.write(f"{TOOL_SEPARATOR} {cmd[0]} END {TOOL_SEPARATOR}\n")

    def _write_result(self, result: subprocess.CompletedProcess[str]) -> None:
        """Write a subprocess result to the log, prefixing stderr lines."""
        if result.stdout:
            self._log_file.write(result.stdout)
            if not result.stdout.endswith("\n"):
                self._log_file.write("\n")
        if result.stderr:
            for line in result.stderr.splitlines():
                self._log_file.write(f"[stderr] {line}\n")
        if not result.stdout and not result.stderr:
            self._log_file.write("No issues found.\n")

    def _check_file(self, path: Path) -> None:
        """Run all file-level quality tools on a single Python file."""
        for cmd_template in FILE_TOOLS:
            self._run_tool(path, cmd_template)

    @staticmethod
    def _collect_python_files(folder: Path) -> list[Path]:
        """Recursively collect .py files, skipping excluded directories."""
        return [item
                for item in sorted(folder.rglob("*.py"))
                if not any(part in EXCLUDED_DIRS
                           # Check only parent directory names (not the filename) against EXCLUDED_DIRS
                           for part in item.relative_to(folder).parent.parts)]

    def run(self, path: Path) -> None:
        """Run file-level and folder-level checks, dispatching by path type."""
        if path.is_file():
            if path.suffix.lower() != ".py":
                print(f'Error: "{path}" is not a Python file (.py).')
                sys.exit(1)
            self._check_file(path)
        elif path.is_dir():
            py_files = self._collect_python_files(path)
            if not py_files:
                print(f'No Python files found in "{path}".')
                sys.exit(1)
            for py_file in py_files:
                self._log_file.write(f"{FILE_SEPARATOR} {py_file} {FILE_SEPARATOR}\n")
                self._check_file(py_file)
                self._log_file.write(f"{FILE_SEPARATOR} {py_file} END {FILE_SEPARATOR}\n\n")
            for cmd_template in FOLDER_TOOLS:
                self._run_tool(path, cmd_template)
        else:
            print(f'Error: "{path}" is not a file or directory.')
            sys.exit(1)

    def write_missing_tools_summary(self) -> None:
        """Write a summary of tools that were not found."""
        if not self._missing_tools:
            return
        self._log_file.write(f"{FILE_SEPARATOR} MISSING TOOLS SUMMARY {FILE_SEPARATOR}\n")
        for tool in sorted(set(self._missing_tools)):
            self._log_file.write(f"  - {tool}\n")
        self._log_file.write("\n")


def main() -> None:
    if len(sys.argv) < 3:
        print("Error: Missing arguments.")
        print("Usage: python code_quality.py <file_or_folder> <output_filepath>")
        sys.exit(1)

    path = Path(sys.argv[1])
    log_path = Path(sys.argv[2])

    if not path.exists():
        print(f'Error: "{path}" does not exist.')
        sys.exit(1)

    log_path.parent.mkdir(parents=True, exist_ok=True)

    with open(log_path, "w", encoding="utf-8") as log_file:
        runner = QualityRunner(log_file)
        runner.run(path)
        runner.write_missing_tools_summary()

    print(f"Report written to {log_path}")


if __name__ == "__main__":
    main()
