"""Run existing static analysis tools on a Python file or folder.

Usage example:
    python python_static_analysis_suite.py src/ report.log
    python python_static_analysis_suite.py my_module.py report.log

Output format:
    Results are written as a structured XML-like log.  Each Python file is
    wrapped in a <file> element containing one <tool> element per tool run.
    Folder-level tools (e.g. deptry, pip-audit) appear after all per-file
    sections.  A <missing_tools_summary> block lists any tools that could not
    be found, and a <stats> block records timing information.

Tools run per file:
    ruff (check), pylint, pyright, radon (cyclomatic complexity),
    bandit, fixit (lint).

Tools run per folder:
    deptry, pip-audit.
"""

import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from io import TextIOWrapper
from pathlib import Path

EXCLUDED_DIRS = {"venv", "sandbox", "tmp", "__pycache__", ".git"}
REPLACE_PATH = "_path_"
TOOL_TIMEOUT_SECONDS = 120
FILE_TOOLS = [
    ("ruff", "check", REPLACE_PATH),
    ("pylint", REPLACE_PATH),
    ("pyright", REPLACE_PATH),
    ("radon", "cc", REPLACE_PATH, "-s", "-n", "C"),
    ("bandit", REPLACE_PATH),
    # ("vulture", REPLACE_PATH),  -- commented out because produced many false positives
    ("fixit", "lint", REPLACE_PATH),
]

FOLDER_TOOLS = [
    ("deptry", REPLACE_PATH),
    # pip-audit doesn't need a target as it checks venv
    ("pip-audit",),
]

TAG_ID = 'id'
FILE_TAG = 'file'
TOOL_TAG = 'tool'
MISSING_TOOLS_TAG = "missing_tools_summary"
STATS_TAG = "stats"
LINE_INDENT = " " * 4


class StaticAnalysisToolsRunner:
    """Runs code quality tools and writes results to a log file."""

    def __init__(self):
        self._missing_tools: list[str] = []
        self._tool_times: dict[str, float] = defaultdict(float)
        self._start_time: datetime | None = None
        self._log_file = None

    @staticmethod
    def _cmd_from_template(path: Path, cmd_template: tuple[str, ...]) -> list[str]:
        """Build a command list by replacing 'path' placeholders with the actual path."""
        path_str = str(path)
        if path_str.startswith("-"):
            path_str = f"./{path_str}"
        return [path_str if part == REPLACE_PATH else part
                for part in cmd_template]

    def _run_tool(self, path: Path, cmd_template: tuple[str, ...]) -> None:
        """Run a single tool command and write its output to the log file."""
        cmd = self._cmd_from_template(path, cmd_template)
        self._log_file.write(f'{LINE_INDENT}<{TOOL_TAG} {TAG_ID}="{cmd[0]}">\n')
        start = time.monotonic()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=TOOL_TIMEOUT_SECONDS)
            self._write_result(result)
        except FileNotFoundError as e:
            self._log_file.write(f"{LINE_INDENT * 2}ERROR: {cmd[0]} is not installed. ({e})\n")
            self._missing_tools.append(cmd[0])
        except subprocess.TimeoutExpired as e:
            self._log_file.write(
                f"{LINE_INDENT * 2}ERROR: {cmd[0]} timed out after {TOOL_TIMEOUT_SECONDS} seconds. ({e})\n"
            )
            if e.stdout:
                self._log_file.write(f"{LINE_INDENT * 2}Partial stdout: {e.stdout}\n")
            if e.stderr:
                self._log_file.write(f"{LINE_INDENT * 2}Partial stderr: {e.stderr}\n")
        self._tool_times[cmd[0]] += time.monotonic() - start
        self._log_file.write(f"{LINE_INDENT}</{TOOL_TAG}>  <!-- {cmd[0]} -->\n")

    def _write_result(self, result: subprocess.CompletedProcess[str]) -> None:
        """Write a subprocess result to the log, prefixing stderr lines."""
        if result.returncode != 0:
            self._log_file.write(f"{LINE_INDENT * 2}Exit code: {result.returncode}\n")
        for source, prefix in ((result.stdout, ""), (result.stderr, "[stderr] ")):
            if source:
                for line in source.splitlines():
                    self._log_file.write(f"{LINE_INDENT * 2}{prefix}{line}\n")
        if not result.stdout and not result.stderr:
            self._log_file.write(f"{LINE_INDENT * 2}No issues found.\n")

    def _check_file(self, path: Path) -> None:
        """Run all file-level quality tools on a single Python file."""
        print(f"Checking: {path}")
        for cmd_template in FILE_TOOLS:
            print(f"{cmd_template[0]}... ", end="")
            self._run_tool(path, cmd_template)
        print()

    @staticmethod
    def _collect_python_files(folder: Path) -> list[Path]:
        """Recursively collect .py files, skipping excluded directories."""
        return [item
                for item in sorted(folder.rglob("*.py"))
                if not any(part in EXCLUDED_DIRS
                           # Check only parent directory names (not the filename) against EXCLUDED_DIRS
                           for part in item.relative_to(folder).parent.parts)]

    def _write_skipped_folder_tools_note(self) -> None:
        """Log a note that folder-level tools were skipped in single-file mode."""
        skipped = [cmd[0] for cmd in FOLDER_TOOLS]
        self._log_file.write(
            f"<!-- NOTE: Folder-level tools skipped in single-file mode:"
            f" {', '.join(skipped)} -->\n\n"
        )

    def _run(self, path: Path) -> None:
        """Run file-level and folder-level checks, dispatching by path type."""
        self._start_time = datetime.now()
        if path.is_file():
            if path.suffix.lower() != ".py":
                print(f'Error: "{path}" is not a Python file (.py).')
                sys.exit(1)
            self._log_file.write(f'<{FILE_TAG} {TAG_ID}="{path}">\n')
            self._check_file(path)
            self._log_file.write(f"</{FILE_TAG}>  <!-- {path} -->\n\n")
            self._write_skipped_folder_tools_note()
        elif path.is_dir():
            py_files = self._collect_python_files(path)
            if not py_files:
                print(f'No Python files found in "{path}".')
                sys.exit(1)
            print(f'Found {len(py_files)} Python file(s) in "{path}".')
            for py_file in py_files:
                self._log_file.write(f'<{FILE_TAG} {TAG_ID}="{py_file}">\n')
                self._check_file(py_file)
                self._log_file.write(f"</{FILE_TAG}>  <!-- {py_file} -->\n\n")
            for cmd_template in FOLDER_TOOLS:
                self._run_tool(path, cmd_template)
        else:
            print(f'Error: "{path}" is not a regular file or directory'
                  f' (type: {type(path)}, exists: {path.exists()}).')
            sys.exit(1)

    def _write_missing_tools_summary(self) -> None:
        """Write a summary of tools that were not found."""
        if not self._missing_tools:
            return
        self._log_file.write(f"<{MISSING_TOOLS_TAG}>\n")
        for tool in sorted(set(self._missing_tools)):
            self._log_file.write(f"  - {tool}\n")
        self._log_file.write(f"</{MISSING_TOOLS_TAG}>\n")

    def _write_stats(self) -> None:
        """Write timing statistics for the report."""
        self._log_file.write(f"<{STATS_TAG}>\n")
        if self._start_time:
            self._log_file.write(
                f"{LINE_INDENT}start_time:"
                f" {self._start_time.strftime('%Y%m%d %H:%M:%S')}\n"
            )
        total = 0.0
        for tool_name, elapsed in sorted(self._tool_times.items()):
            self._log_file.write(f"{LINE_INDENT}{tool_name}: {elapsed:.2f}s\n")
            total += elapsed
        self._log_file.write(f"{LINE_INDENT}total: {total:.2f}s\n")
        self._log_file.write(f"</{STATS_TAG}>\n")

    def run(self, path: Path) -> None:
        with open(path, "w", encoding="utf-8") as log_file:
            self._log_file = log_file
            self._run(path)
            self._write_missing_tools_summary()
            self._write_stats()


def main() -> None:
    """Parse CLI arguments and run the static analysis suite, writing results to the specified output file."""
    if len(sys.argv) < 3:
        print("Error: Missing arguments.")
        print("Usage: python python_static_analysis_suite.py <file_or_folder> <output_filepath>")
        sys.exit(1)

    path = Path(sys.argv[1]).resolve()
    log_path = Path(sys.argv[2])

    if not path.exists():
        print(f'Error: "{path}" does not exist.')
        sys.exit(1)

    log_path.parent.mkdir(parents=True, exist_ok=True)

    StaticAnalysisToolsRunner(log_path).run(path)

    print(f"Report written to {log_path}")


if __name__ == "__main__":
    main()
