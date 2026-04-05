"""Tests for python_static_analysis_suite.py — tests QualityRunner logic, all subprocess calls mocked."""

import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "scripts"))
import python_static_analysis_suite as suite
from python_static_analysis_suite import QualityRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runner() -> tuple[QualityRunner, StringIO]:
    buf = StringIO()
    return QualityRunner(buf), buf


def _fake_completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Baseline tests — current behaviour
# ---------------------------------------------------------------------------

class TestCmdFromTemplate:
    def test_replaces_path_placeholder(self):
        cmd = QualityRunner._cmd_from_template(Path("foo.py"), ("ruff", "check", suite.REPLACE_PATH))
        assert cmd == ["ruff", "check", "foo.py"]

    def test_no_placeholder(self):
        cmd = QualityRunner._cmd_from_template(Path("x.py"), ("pip-audit",))
        assert cmd == ["pip-audit"]


class TestWriteResult:
    def test_stdout_written(self):
        runner, buf = _make_runner()
        runner._write_result(_fake_completed(stdout="line1\nline2"))
        output = buf.getvalue()
        assert "line1" in output
        assert "line2" in output

    def test_stderr_prefixed(self):
        runner, buf = _make_runner()
        runner._write_result(_fake_completed(stderr="warn"))
        assert "[stderr] warn" in buf.getvalue()

    def test_no_output_shows_no_issues(self):
        runner, buf = _make_runner()
        runner._write_result(_fake_completed())
        assert "No issues found" in buf.getvalue()


class TestRunTool:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed(stdout="ok"))
    def test_writes_tool_tags(self, mock_run):
        runner, buf = _make_runner()
        runner._run_tool(Path("f.py"), ("ruff", "check", suite.REPLACE_PATH))
        output = buf.getvalue()
        assert '<tool id="ruff">' in output
        assert "</tool>" in output

    @patch("python_static_analysis_suite.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_tool_recorded(self, mock_run):
        runner, buf = _make_runner()
        runner._run_tool(Path("f.py"), ("nosuchtool", suite.REPLACE_PATH))
        assert "nosuchtool" in runner._missing_tools
        assert "not installed" in buf.getvalue()

    @patch("python_static_analysis_suite.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[], timeout=120))
    def test_timeout_recorded(self, mock_run):
        runner, buf = _make_runner()
        runner._run_tool(Path("f.py"), ("slow", suite.REPLACE_PATH))
        assert "timed out" in buf.getvalue()


class TestCollectPythonFiles:
    def test_excludes_dirs(self, tmp_path):
        (tmp_path / "good.py").touch()
        venv = tmp_path / "venv"
        venv.mkdir()
        (venv / "bad.py").touch()
        result = QualityRunner._collect_python_files(tmp_path)
        names = [p.name for p in result]
        assert "good.py" in names
        assert "bad.py" not in names


class TestRunDirectory:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_directory_wraps_files_in_file_tags(self, mock_run, tmp_path):
        (tmp_path / "a.py").touch()
        runner, buf = _make_runner()
        runner.run(tmp_path)
        output = buf.getvalue()
        assert f"<file" in output
        assert "</file>" in output


class TestWriteMissingToolsSummary:
    def test_no_missing_tools_writes_nothing(self):
        runner, buf = _make_runner()
        runner.write_missing_tools_summary()
        assert buf.getvalue() == ""

    def test_missing_tools_writes_summary(self):
        runner, buf = _make_runner()
        runner._missing_tools = ["ruff", "pylint"]
        runner.write_missing_tools_summary()
        output = buf.getvalue()
        assert f"<{suite.MISSING_TOOLS_TAG}>" in output
        assert "ruff" in output
        assert "pylint" in output


class TestWriteStats:
    def test_writes_stats_tags(self):
        runner, buf = _make_runner()
        runner._tool_times["ruff"] = 1.5
        runner.write_stats()
        output = buf.getvalue()
        assert f"<{suite.STATS_TAG}>" in output
        assert f"</{suite.STATS_TAG}>" in output
        assert "ruff: 1.50s" in output


# ---------------------------------------------------------------------------
# Issue-specific xfail tests — expected to fail until Phase 5 fixes are applied
# ---------------------------------------------------------------------------

class TestIssue2_MissingClosingBracket:
    def test_closing_tag_is_well_formed(self):
        runner, buf = _make_runner()
        runner._missing_tools = ["ruff"]
        runner.write_missing_tools_summary()
        output = buf.getvalue()
        assert f"</{suite.MISSING_TOOLS_TAG}>" in output


class TestIssue1_SingleFileMissingFileWrapper:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_single_file_has_file_tags(self, mock_run, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        runner, buf = _make_runner()
        runner.run(f)
        output = buf.getvalue()
        assert "<file" in output
        assert "</file>" in output


class TestIssue3_SymlinkResolution:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_symlink_is_resolved(self, mock_run, tmp_path):
        real = tmp_path / "real.py"
        real.write_text("x = 1\n")
        link = tmp_path / "link.py"
        link.symlink_to(real)
        log_path = tmp_path / "out.log"
        # Go through main() where resolve happens
        with patch("sys.argv", ["prog", str(link), str(log_path)]):
            suite.main()
        output = log_path.read_text()
        # The file tag should reference the resolved path, not the symlink
        assert str(real) in output or "real.py" in output


class TestIssue4_FolderToolsSkippedNote:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_single_file_logs_folder_tools_skipped(self, mock_run, tmp_path, capsys):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        runner, buf = _make_runner()
        runner.run(f)
        combined = buf.getvalue() + capsys.readouterr().out
        lower = combined.lower()
        assert "folder" in lower and "skipped" in lower


class TestIssue9_XootRemoved:
    def test_no_xoot_in_file_tools(self):
        tool_names = [t[0] for t in suite.FILE_TOOLS]
        assert "xoot" not in tool_names


class TestIssue13_TimeoutConstant:
    def test_timeout_uses_module_constant(self):
        assert hasattr(suite, "TOOL_TIMEOUT_SECONDS")


class TestIssue14_ExceptionDetailsLogged:
    def test_timeout_includes_exception_detail(self):
        exc = subprocess.TimeoutExpired(cmd=["slow"], timeout=120)
        exc.stdout = "partial output"
        exc.stderr = None
        with patch("python_static_analysis_suite.subprocess.run", side_effect=exc):
            runner, buf = _make_runner()
            runner._run_tool(Path("f.py"), ("slow", suite.REPLACE_PATH))
            output = buf.getvalue()
            # After fix, should include some detail beyond the generic message
            assert "partial" in output or "TimeoutExpired" in output


class TestIssue15_ReturnCodeLogged:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed(returncode=2, stderr="err"))
    def test_nonzero_return_code_in_output(self, mock_run):
        runner, buf = _make_runner()
        runner._run_tool(Path("f.py"), ("ruff", "check", suite.REPLACE_PATH))
        assert "2" in buf.getvalue()


class TestIssue16_FileCountLogged:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_directory_logs_file_count(self, mock_run, tmp_path, capsys):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        runner, buf = _make_runner()
        runner.run(tmp_path)
        combined = capsys.readouterr().out + buf.getvalue()
        # Must explicitly mention the count of files found
        assert "Found 2" in combined or "2 Python file" in combined


class TestIssue20_DashPathSanitized:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_path_starting_with_dash_is_sanitized(self, mock_run):
        # Use a bare relative-style Path so it starts with "-"
        f = Path("-malicious.py")
        runner, buf = _make_runner()
        runner._run_tool(f, ("ruff", "check", suite.REPLACE_PATH))
        call_args = mock_run.call_args[0][0]
        path_arg = [a for a in call_args if "malicious" in a][0]
        # After fix, the path arg should be prefixed (e.g., ./-malicious.py) or use '--'
        assert not path_arg.startswith("-") or "--" in call_args
