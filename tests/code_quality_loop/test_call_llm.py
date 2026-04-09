"""Tests for call_llm.py.

Lives under tests/code_quality_loop/ so it can reuse the existing conftest
that puts the scripts/ directory on sys.path.
"""
from __future__ import annotations

import logging
import os
import subprocess
import types
from unittest.mock import MagicMock, patch

import pytest

import call_llm


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_text_response(text: str) -> MagicMock:
    """Build a fake Anthropic SDK response containing a single text block."""
    block = types.SimpleNamespace(type="text", text=text)
    return types.SimpleNamespace(content=[block], stop_reason="end_turn")


def _fake_non_text_response() -> MagicMock:
    """Build a fake response whose first content block is a tool_use (no .text)."""
    block = types.SimpleNamespace(type="tool_use", id="t1", name="f", input={})
    return types.SimpleNamespace(content=[block], stop_reason="tool_use")


def _fake_empty_response() -> MagicMock:
    return types.SimpleNamespace(content=[], stop_reason="end_turn")


# ---------------------------------------------------------------------------
# Baseline: API path
# ---------------------------------------------------------------------------

def test_call_via_api_returns_text() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_text_response("hello")
    with patch.object(call_llm, "_get_anthropic_client", return_value=client):
        out = call_llm._call_via_api("sys", "user", 100, "claude-opus-4-6")
    # _call_via_api returns (text, input_tokens, output_tokens)
    text, _in, _out = out
    assert text == "hello"
    client.messages.create.assert_called_once()


def test_call_via_api_raises_when_client_none() -> None:
    with patch.object(call_llm, "_get_anthropic_client", return_value=None):
        with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
            call_llm._call_via_api("sys", "user", 100, "claude-opus-4-6")


# ---------------------------------------------------------------------------
# Baseline: CLI path
# ---------------------------------------------------------------------------

def _fake_popen(rc: int, stdout: str = "", stderr: str = "",
                timeout: bool = False, captured: dict | None = None) -> MagicMock:
    """Build a fake Popen-like object whose .communicate returns the given outputs."""
    proc = MagicMock()
    proc.returncode = rc
    if timeout:
        proc.communicate.side_effect = subprocess.TimeoutExpired(
            cmd="claude", timeout=1)
    else:
        proc.communicate.return_value = (stdout, stderr)

    def factory(*args, **kwargs):
        if captured is not None:
            captured["env"] = kwargs.get("env")
            captured["args"] = args[0] if args else None
        return proc

    return factory, proc


def test_call_via_cli_returns_stdout_on_success() -> None:
    factory, _ = _fake_popen(0, "ok\n")
    with patch("call_llm.subprocess.Popen", side_effect=factory):
        out = call_llm._call_via_cli("sys", "user", "claude-opus-4-6")
    assert out == "ok\n"


def test_call_via_cli_raises_on_nonzero_returncode() -> None:
    factory, _ = _fake_popen(1, "", "boom")
    with patch("call_llm.subprocess.Popen", side_effect=factory):
        with pytest.raises(RuntimeError, match="claude CLI exited with code 1"):
            call_llm._call_via_cli("sys", "user", "claude-opus-4-6")


def test_call_via_cli_rejects_invalid_model_name() -> None:
    with pytest.raises(ValueError, match="Invalid model name"):
        call_llm._call_via_cli("sys", "user", "bad model;rm -rf")


def test_call_via_cli_strips_anthropic_api_key_from_env() -> None:
    captured: dict = {}
    factory, _ = _fake_popen(0, "x", captured=captured)
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "secret", "OTHER": "y"}, clear=False):
        with patch("call_llm.subprocess.Popen", side_effect=factory):
            call_llm._call_via_cli("sys", "user", "claude-opus-4-6")

    assert "ANTHROPIC_API_KEY" not in captured["env"]
    assert captured["env"].get("OTHER") == "y"


# ---------------------------------------------------------------------------
# Baseline: call_llm dispatcher
# ---------------------------------------------------------------------------

def test_call_llm_unknown_backend_raises() -> None:
    with patch.object(call_llm, "LLM_BACKEND", "bogus"):
        with pytest.raises(ValueError, match="Unknown LLM_BACKEND"):
            call_llm.call_llm(system_message="s", user_message="u")


def test_call_llm_dispatches_to_api() -> None:
    with patch.object(call_llm, "LLM_BACKEND", "api"), \
         patch.object(call_llm, "_call_via_api",
                      return_value=("api-result", 1, 2)) as m:
        out = call_llm.call_llm(system_message="s", user_message="u",
                                model="claude-opus-4-6")
    assert out == "api-result"
    m.assert_called_once()


def test_call_llm_dispatches_to_cli() -> None:
    with patch.object(call_llm, "LLM_BACKEND", "cli"), \
         patch.object(call_llm, "_call_via_cli", return_value="cli-result") as m:
        out = call_llm.call_llm(system_message="s", user_message="u",
                                model="claude-opus-4-6")
    assert out == "cli-result"
    m.assert_called_once()


# ---------------------------------------------------------------------------
# Issue-specific tests (xfail until Phase 5 fixes land)
# ---------------------------------------------------------------------------

def test_api_empty_content_list_raises_clear_error() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_empty_response()
    with patch.object(call_llm, "_get_anthropic_client", return_value=client):
        with pytest.raises(RuntimeError):
            call_llm._call_via_api("sys", "user", 100, "claude-opus-4-6")


def test_api_non_text_first_block_raises_clear_error() -> None:
    client = MagicMock()
    client.messages.create.return_value = _fake_non_text_response()
    with patch.object(call_llm, "_get_anthropic_client", return_value=client):
        with pytest.raises(RuntimeError):
            call_llm._call_via_api("sys", "user", 100, "claude-opus-4-6")


def test_cli_empty_stdout_raises_runtime_error() -> None:
    factory, _ = _fake_popen(0, "   \n")
    with patch("call_llm.subprocess.Popen", side_effect=factory):
        with pytest.raises(RuntimeError):
            call_llm._call_via_cli("sys", "user", "claude-opus-4-6")


def test_default_max_tokens_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    monkeypatch.setenv("LLM_MAX_TOKENS", "12345")
    reloaded = importlib.reload(call_llm)
    try:
        assert reloaded.DEFAULT_MAX_TOKENS == 12345
    finally:
        monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
        importlib.reload(call_llm)


def test_call_llm_failure_logs_exception_info(caplog: pytest.LogCaptureFixture) -> None:
    boom = RuntimeError("kaboom-detail")
    with patch.object(call_llm, "LLM_BACKEND", "api"), \
         patch.object(call_llm, "_call_via_api", side_effect=boom), \
         caplog.at_level(logging.ERROR, logger=call_llm.logger.name):
        with pytest.raises(RuntimeError):
            call_llm.call_llm(system_message="s", user_message="u",
                              model="claude-opus-4-6")
    # exc_info / exception() should include the message text
    assert any("kaboom-detail" in rec.getMessage() or rec.exc_info
               for rec in caplog.records)


def test_cli_unlink_failure_logged(caplog: pytest.LogCaptureFixture) -> None:
    factory, _ = _fake_popen(0, "ok")
    with patch("call_llm.subprocess.Popen", side_effect=factory), \
         patch("call_llm.os.unlink", side_effect=OSError("denied")), \
         caplog.at_level(logging.WARNING, logger=call_llm.logger.name):
        call_llm._call_via_cli("sys", "user", "claude-opus-4-6")
    assert any("unlink" in rec.getMessage().lower()
               or "temp" in rec.getMessage().lower()
               for rec in caplog.records)


def test_get_anthropic_client_logs_when_api_key_missing(
        caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(call_llm, "LLM_BACKEND", "api")
    monkeypatch.setattr(call_llm, "_ANTHROPIC_CLIENT", None)
    monkeypatch.setattr(call_llm, "_ANTHROPIC_INIT_DONE", False)
    with caplog.at_level(logging.ERROR, logger=call_llm.logger.name):
        client = call_llm._get_anthropic_client()
    assert client is None
    assert any("ANTHROPIC_API_KEY" in rec.getMessage() for rec in caplog.records)


def test_cli_subprocess_error_log_includes_exception(
        caplog: pytest.LogCaptureFixture) -> None:
    factory, _ = _fake_popen(0, "", timeout=True)
    with patch("call_llm.subprocess.Popen", side_effect=factory), \
         caplog.at_level(logging.ERROR, logger=call_llm.logger.name):
        # Issue #23: TimeoutExpired is wrapped in a RuntimeError with context.
        with pytest.raises((subprocess.TimeoutExpired, RuntimeError)):
            call_llm._call_via_cli("sys", "user", "claude-opus-4-6")
    # logger.exception or exc_info=True should attach traceback info
    assert any(rec.exc_info for rec in caplog.records)


def test_get_anthropic_client_uses_lock() -> None:
    import threading
    # The module should expose a threading.Lock used to guard init.
    lock = getattr(call_llm, "_ANTHROPIC_INIT_LOCK", None)
    assert isinstance(lock, type(threading.Lock()))


def test_call_llm_docstring_mentions_max_tokens_api_only() -> None:
    doc = (call_llm.call_llm.__doc__ or "").lower()
    assert "max_tokens" in doc
    assert "api" in doc and ("only" in doc or "ignored" in doc)


def test_cli_temp_file_removed_on_write_failure(
        tmp_path: "object") -> None:
    """Issue #10 baseline: if writing system prompt fails, temp file is cleaned up."""
    created: list[str] = []
    real_ntf = call_llm.tempfile.NamedTemporaryFile

    def tracking_ntf(*args, **kwargs):
        f = real_ntf(*args, **kwargs)
        created.append(f.name)
        orig_write = f.write

        def boom(_data):
            raise OSError("disk full")
        f.write = boom  # type: ignore[method-assign]
        return f

    with patch("call_llm.tempfile.NamedTemporaryFile", side_effect=tracking_ntf):
        with pytest.raises(OSError, match="disk full"):
            call_llm._call_via_cli("sys", "user", "claude-opus-4-6")
    # The created temp file should have been cleaned up.
    assert created, "expected NamedTemporaryFile to be called"
    for path in created:
        assert not os.path.exists(path), f"temp file leaked: {path}"


# ---------------------------------------------------------------------------
# Round-2 issue-specific tests (xfail until Phase 5 fixes land)
# ---------------------------------------------------------------------------

def test_invalid_max_tokens_env_falls_back(
        monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    monkeypatch.setenv("LLM_MAX_TOKENS", "not-a-number")
    try:
        reloaded = importlib.reload(call_llm)
        assert reloaded.DEFAULT_MAX_TOKENS == 16000
    finally:
        monkeypatch.delenv("LLM_MAX_TOKENS", raising=False)
        importlib.reload(call_llm)


def test_model_regex_rejects_leading_dash() -> None:
    with pytest.raises(ValueError, match="Invalid model name"):
        call_llm._call_via_cli("sys", "user", "-rm")


def test_model_regex_rejects_leading_dot() -> None:
    with pytest.raises(ValueError, match="Invalid model name"):
        call_llm._call_via_cli("sys", "user", ".evil")


def test_empty_system_message_rejected() -> None:
    with pytest.raises(ValueError):
        call_llm.call_llm(system_message="", user_message="u",
                          model="claude-opus-4-6")


def test_empty_user_message_rejected() -> None:
    with pytest.raises(ValueError):
        call_llm.call_llm(system_message="s", user_message="",
                          model="claude-opus-4-6")


def test_api_no_text_blocks_error_includes_context() -> None:
    """Issue #25: non-text-only response raises with stop_reason and block types."""
    client = MagicMock()
    resp = _fake_non_text_response()  # content=[tool_use block]
    resp.stop_reason = "tool_use"
    client.messages.create.return_value = resp
    with patch.object(call_llm, "_get_anthropic_client", return_value=client):
        with pytest.raises(RuntimeError, match="tool_use"):
            call_llm._call_via_api("sys", "user", 100, "claude-opus-4-6")


def test_anthropic_init_flag_set_after_client_assigned(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """If anthropic.Anthropic(...) raises, _ANTHROPIC_INIT_DONE must stay False
    so a subsequent call can retry instead of seeing a None client."""
    monkeypatch.setattr(call_llm, "_ANTHROPIC_CLIENT", None)
    monkeypatch.setattr(call_llm, "_ANTHROPIC_INIT_DONE", False)
    monkeypatch.setattr(call_llm, "LLM_BACKEND", "api")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")

    fake_mod = types.SimpleNamespace(
        Anthropic=MagicMock(side_effect=RuntimeError("init boom")),
    )
    import sys
    monkeypatch.setitem(sys.modules, "anthropic", fake_mod)

    with pytest.raises(RuntimeError, match="init boom"):
        call_llm._get_anthropic_client()
    # Flag must not be sticky on failure.
    assert call_llm._ANTHROPIC_INIT_DONE is False


def test_cli_path_env_var_used(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict = {}
    factory, _ = _fake_popen(0, "ok", captured=captured)
    monkeypatch.setenv("LLM_CLI_PATH", "custom-claude-bin")
    import importlib
    reloaded = importlib.reload(call_llm)
    try:
        with patch.object(reloaded, "subprocess") as subp:
            subp.Popen.side_effect = factory
            subp.TimeoutExpired = subprocess.TimeoutExpired
            reloaded._call_via_cli("sys", "user", "claude-opus-4-6")
        assert captured["args"][0] == "custom-claude-bin"
    finally:
        monkeypatch.delenv("LLM_CLI_PATH", raising=False)
        importlib.reload(call_llm)


def test_call_llm_success_log_includes_token_usage(
        caplog: pytest.LogCaptureFixture) -> None:
    client = MagicMock()
    resp = _fake_text_response("hi there")
    resp.usage = types.SimpleNamespace(input_tokens=42, output_tokens=7)
    client.messages.create.return_value = resp
    with patch.object(call_llm, "LLM_BACKEND", "api"), \
         patch.object(call_llm, "_get_anthropic_client", return_value=client), \
         caplog.at_level(logging.INFO, logger=call_llm.logger.name):
        call_llm.call_llm(system_message="s", user_message="u",
                          model="claude-opus-4-6")
    messages = " ".join(rec.getMessage() for rec in caplog.records)
    assert "42" in messages or "input_tokens" in messages
    assert "7" in messages or "output_tokens" in messages
