"""Run project-level static analysis tools (dependency and vulnerability checks).

Usage:
    python python_project_static_analysis.py <project_folder> <output_filepath>

Tools run:
    deptry     — detect missing, unused, and transitive dependency issues
    pip-audit  — check installed packages for known vulnerabilities

Output format:
    Results are written as a structured XML-like log, similar to
    python_static_analysis_suite.py.  Each tool is wrapped in a <tool>
    element.  A <missing_tools_summary> block lists any tools that could
    not be found, and a <stats> block records timing information.
"""

import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPLACE_PATH = "_path_"
TOOL_TIMEOUT_SECONDS = 120
PROJECT_TOOLS = [
    ("deptry", REPLACE_PATH),
    # pip-audit checks the active environment, no path argument needed
    ("pip-audit",),
]

TAG_ID = 'id'
TOOL_TAG = 'tool'
MISSING_TOOLS_TAG = "missing_tools_summary"
STATS_TAG = "stats"
LINE_INDENT = " " * 4


class ProjectStaticAnalysisRunner:
    """Runs project-level quality tools and writes results to a log file."""

    def __init__(self, log_path: Path):
        self._missing_tools: list[str] = []
        self._tool_times: dict[str, float] = defaultdict(float)
        self._start_time: datetime | None = None
        self._log_path = log_path
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
        self._log_file.write(f'<{TOOL_TAG} {TAG_ID}="{cmd[0]}">\n')
        start = time.monotonic()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=TOOL_TIMEOUT_SECONDS, check=False)
            self._write_result(result)
        except FileNotFoundError as e:
            self._log_file.write(
                f"{LINE_INDENT}ERROR: {cmd[0]} is not installed. ({e})\n")
            self._missing_tools.append(cmd[0])
        except subprocess.TimeoutExpired as e:
            self._log_file.write(
                f"{LINE_INDENT}ERROR: {cmd[0]} timed out after "
                f"{TOOL_TIMEOUT_SECONDS} seconds. ({e})\n"
            )
            if e.stdout:
                self._log_file.write(f"{LINE_INDENT}Partial stdout: {e.stdout}\n")
            if e.stderr:
                self._log_file.write(f"{LINE_INDENT}Partial stderr: {e.stderr}\n")
        self._tool_times[cmd[0]] += time.monotonic() - start
        self._log_file.write(f"</{TOOL_TAG}>  <!-- {cmd[0]} -->\n\n")

    def _write_result(self, result: subprocess.CompletedProcess[str]) -> None:
        """Write a subprocess result to the log, prefixing stderr lines."""
        if result.returncode != 0:
            self._log_file.write(f"{LINE_INDENT}Exit code: {result.returncode}\n")
        for source, prefix in ((result.stdout, ""), (result.stderr, "[stderr] ")):
            if source:
                for line in source.splitlines():
                    self._log_file.write(f"{LINE_INDENT}{prefix}{line}\n")
        if not result.stdout and not result.stderr:
            self._log_file.write(f"{LINE_INDENT}No issues found.\n")

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
        """Run all project-level tools and write the report."""
        self._start_time = datetime.now()
        with open(self._log_path, "w", encoding="utf-8") as log_file:
            self._log_file = log_file
            print(f"Running project-level analysis on: {path}")
            for cmd_template in PROJECT_TOOLS:
                print(f"  {cmd_template[0]}... ", end="")
                self._run_tool(path, cmd_template)
                print("done")
            self._write_missing_tools_summary()
            self._write_stats()


def main() -> None:
    """Parse CLI arguments and run the project-level static analysis."""
    if len(sys.argv) < 3:
        print("Error: Missing arguments.")
        print("Usage: python python_project_static_analysis.py "
              "<project_folder> <output_filepath>")
        sys.exit(1)

    path = Path(sys.argv[1]).resolve()
    log_path = Path(sys.argv[2])

    if not path.is_dir():
        print(f'Error: "{path}" is not a directory.')
        sys.exit(1)

    log_path.parent.mkdir(parents=True, exist_ok=True)

    ProjectStaticAnalysisRunner(log_path).run(path)

    print(f"Report written to {log_path}")


if __name__ == "__main__":
    main()
