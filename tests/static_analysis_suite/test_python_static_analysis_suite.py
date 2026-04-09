"""Tests for python_static_analysis_suite.py.

Tests StaticAnalysisToolsRunner logic, all subprocess calls mocked.
"""

import subprocess
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(
    Path(__file__).resolve().parents[2]
    / ".claude" / "code-quality" / "scripts" / "python_static_analysis"
))
import python_static_analysis_suite as suite
from python_static_analysis_suite import StaticAnalysisToolsRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_runner() -> tuple[StaticAnalysisToolsRunner, StringIO]:
    buf = StringIO()
    return StaticAnalysisToolsRunner(buf), buf


def _fake_completed(stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


# ---------------------------------------------------------------------------
# Baseline tests — current behaviour
# ---------------------------------------------------------------------------

class TestCmdFromTemplate:
    def test_replaces_path_placeholder(self):
        cmd = StaticAnalysisToolsRunner._cmd_from_template(
            Path("foo.py"), ("ruff", "check", suite.REPLACE_PATH))
        assert cmd == ["ruff", "check", "foo.py"]

    def test_no_placeholder(self):
        cmd = StaticAnalysisToolsRunner._cmd_from_template(Path("x.py"), ("pip-audit",))
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

    @patch("python_static_analysis_suite.subprocess.run",
           side_effect=subprocess.TimeoutExpired(cmd=[], timeout=120))
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
        result = StaticAnalysisToolsRunner._collect_python_files(tmp_path)
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
        assert "<file" in output
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

class TestIssue2MissingClosingBracket:
    def test_closing_tag_is_well_formed(self):
        runner, buf = _make_runner()
        runner._missing_tools = ["ruff"]
        runner.write_missing_tools_summary()
        output = buf.getvalue()
        assert f"</{suite.MISSING_TOOLS_TAG}>" in output


class TestIssue1SingleFileMissingFileWrapper:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_single_file_has_file_tags(self, mock_run, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        runner, buf = _make_runner()
        runner.run(f)
        output = buf.getvalue()
        assert "<file" in output
        assert "</file>" in output


class TestIssue3SymlinkResolution:
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


class TestIssue4FolderToolsSkippedNote:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_single_file_logs_folder_tools_skipped(self, mock_run, tmp_path, capsys):
        f = tmp_path / "hello.py"
        f.write_text("x = 1\n")
        runner, buf = _make_runner()
        runner.run(f)
        combined = buf.getvalue() + capsys.readouterr().out
        lower = combined.lower()
        assert "folder" in lower and "skipped" in lower


class TestIssue9XootRemoved:
    def test_no_xoot_in_file_tools(self):
        tool_names = [t[0] for t in suite.FILE_TOOLS]
        assert "xoot" not in tool_names


class TestIssue13TimeoutConstant:
    def test_timeout_uses_module_constant(self):
        assert hasattr(suite, "TOOL_TIMEOUT_SECONDS")


class TestIssue14ExceptionDetailsLogged:
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


class TestIssue15ReturnCodeLogged:
    @patch("python_static_analysis_suite.subprocess.run",
           return_value=_fake_completed(returncode=2, stderr="err"))
    def test_nonzero_return_code_in_output(self, mock_run):
        runner, buf = _make_runner()
        runner._run_tool(Path("f.py"), ("ruff", "check", suite.REPLACE_PATH))
        assert "2" in buf.getvalue()


class TestIssue16FileCountLogged:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_directory_logs_file_count(self, mock_run, tmp_path, capsys):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        runner, buf = _make_runner()
        runner.run(tmp_path)
        combined = capsys.readouterr().out + buf.getvalue()
        # Must explicitly mention the count of files found
        assert "Found 2" in combined or "2 Python file" in combined


class TestIssue20DashPathSanitized:
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_path_starting_with_dash_is_sanitized(self, mock_run):
        # Use a bare relative-style Path so it starts with "-"
        f = Path("-malicious.py")
        runner, _buf = _make_runner()
        runner._run_tool(f, ("ruff", "check", suite.REPLACE_PATH))
        call_args = mock_run.call_args[0][0]
        path_arg = [a for a in call_args if "malicious" in a][0]
        # After fix, the path arg should be prefixed (e.g., ./-malicious.py) or use '--'
        assert not path_arg.startswith("-") or "--" in call_args


class TestIssue22TimeoutBytesDecoded:
    @pytest.mark.xfail(reason="issue #22: TimeoutExpired stdout stderr bytes not str")
    def test_timeout_partial_output_decoded_not_bytes_repr(self):
        exc = subprocess.TimeoutExpired(cmd=["slow"], timeout=120)
        exc.stdout = b"partial output bytes"
        exc.stderr = b"partial error bytes"
        with patch("python_static_analysis_suite.subprocess.run", side_effect=exc):
            runner, buf = _make_runner()
            runner._run_tool(Path("f.py"), ("slow", suite.REPLACE_PATH))
            output = buf.getvalue()
            # Should contain decoded text, not b'...' representation
            assert "partial output bytes" in output
            assert "b'" not in output


class TestIssue24ExtraArgsWarning:
    @pytest.mark.xfail(reason="issue #24: extra CLI arguments silently ignored")
    def test_extra_args_causes_error(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        log = tmp_path / "out.log"
        with patch("sys.argv", ["prog", str(f), str(log), "--extra", "arg"]):
            with pytest.raises(SystemExit):
                suite.main()


class TestIssue25LogFileOpenErrorHandled:
    @pytest.mark.xfail(reason="issue #25: log file open without error handling in main")
    def test_bad_log_path_gives_friendly_error(self, tmp_path, capsys):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        # Use an invalid path that can't be opened
        bad_log = tmp_path / "nonexistent_dir_xyz" / "sub" / "out.log"
        # Remove the parent so mkdir can't create it
        with patch("sys.argv", ["prog", str(f), str(bad_log)]), \
             patch("pathlib.Path.mkdir", side_effect=OSError("Permission denied")):
            with pytest.raises(SystemExit) as exc_info:
                suite.main()
            assert exc_info.value.code == 1
            output = capsys.readouterr()
            assert "error" in output.out.lower() or "error" in output.err.lower()


class TestIssue26TopLevelOSErrorHandled:
    @pytest.mark.xfail(reason="issue #26: log file write errors unhandled during tool execution")
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_write_error_during_run_caught(self, mock_run, tmp_path, capsys):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        log = tmp_path / "out.log"
        with patch("sys.argv", ["prog", str(f), str(log)]):
            # Make the log file write fail mid-run
            with patch("builtins.open", side_effect=OSError("disk full")):
                with pytest.raises(SystemExit) as exc_info:
                    suite.main()
                assert exc_info.value.code != 0


class TestIssue27SubprocessEncodingError:
    @pytest.mark.xfail(reason="issue #27: subprocess run inherits no encoding-error policy")
    @patch("python_static_analysis_suite.subprocess.run")
    def test_subprocess_uses_error_replacement(self, mock_run):
        runner, _buf = _make_runner()
        # Verify subprocess.run is called with errors= parameter
        runner._run_tool(Path("f.py"), ("ruff", "check", suite.REPLACE_PATH))
        call_kwargs = mock_run.call_args[1] if mock_run.call_args[1] else {}
        call_kwargs.update(dict(zip(
            ["capture_output", "text", "timeout"],
            [mock_run.call_args[0][1:] if len(mock_run.call_args[0]) > 1 else []]
        )))
        # Check the actual keyword args passed to subprocess.run
        actual_kwargs = mock_run.call_args.kwargs
        assert "errors" in actual_kwargs


class TestIssue28ConfigurableTimeout:
    @pytest.mark.xfail(reason="issue #28: hardcoded tool timeout with no configuration option")
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_timeout_cli_arg_respected(self, mock_run, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        log = tmp_path / "out.log"
        with patch("sys.argv", ["prog", str(f), str(log), "--timeout", "60"]):
            suite.main()
        # Verify subprocess was called with timeout=60
        for call in mock_run.call_args_list:
            if "timeout" in call.kwargs:
                assert call.kwargs["timeout"] == 60


class TestIssue29GenericExceptionCaught:
    @pytest.mark.xfail(reason="issue #29: subprocess generic exception not caught or logged")
    @patch("python_static_analysis_suite.subprocess.run",
           side_effect=PermissionError("access denied"))
    def test_permission_error_caught_and_logged(self, mock_run):
        runner, buf = _make_runner()
        # Should not raise, should log the error and continue
        runner._run_tool(Path("f.py"), ("ruff", "check", suite.REPLACE_PATH))
        output = buf.getvalue()
        assert "error" in output.lower() or "permission" in output.lower()


class TestIssue30IncompleteRunMarked:
    @pytest.mark.xfail(reason="issue #30: main crashes with no log on unhandled runner error")
    @patch("python_static_analysis_suite.subprocess.run", side_effect=OSError("disk full"))
    def test_incomplete_run_writes_error_tag(self, mock_run, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        log = tmp_path / "out.log"
        with patch("sys.argv", ["prog", str(f), str(log)]):
            try:
                suite.main()
            except (SystemExit, OSError):
                pass
        content = log.read_text() if log.exists() else ""
        # The report should contain an <error> tag AND still have stats/summary
        # Currently the crash leaves a truncated file with no error marker
        assert "<error>" in content
        assert f"<{suite.STATS_TAG}>" in content


class TestIssue31CoverageCounters:
    @pytest.mark.xfail(reason="issue #31: no file count or completion logged to report")
    @patch("python_static_analysis_suite.subprocess.run", return_value=_fake_completed())
    def test_stats_include_file_count(self, mock_run, tmp_path):
        (tmp_path / "a.py").touch()
        (tmp_path / "b.py").touch()
        runner, buf = _make_runner()
        runner.run(tmp_path)
        runner.write_stats()
        output = buf.getvalue()
        assert "files_checked" in output or "files checked" in output.lower()
