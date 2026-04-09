"""Tests for common.py utilities."""
import re
from pathlib import Path

from common import (
    strip_markdown_fence,
    issues_path,
    decisions_path,
    log_path,
    now_utc,
    format_examples_for_type,
    load_issue_types,
    parse_llm_response,
)


# --- strip_markdown_fence ---

def test_strip_fence_json():
    text = '```json\n{"a": 1}\n```'
    assert strip_markdown_fence(text) == '{"a": 1}\n'


def test_strip_fence_plain():
    text = '```\nsome code\n```'
    assert strip_markdown_fence(text) == 'some code\n'


def test_strip_fence_no_fence():
    text = 'just plain text'
    assert strip_markdown_fence(text) == 'just plain text'


def test_strip_fence_empty_fence():
    text = '```'
    assert strip_markdown_fence(text) == ''


def test_strip_fence_preserves_inner_backticks():
    text = '```\ncode with `backticks`\n```'
    assert '`backticks`' in strip_markdown_fence(text)


# --- path helpers ---

def test_issues_path():
    p = Path("foo/bar.py")
    assert issues_path(p) == Path("foo/bar.issues.json")


def test_decisions_path():
    p = Path("foo/bar.py")
    assert decisions_path(p) == Path("foo/bar.decisions.json")


def test_log_path():
    p = Path("foo/bar.py")
    assert log_path(p) == Path("foo/bar.log.jsonl")


def test_paths_with_double_extension():
    p = Path("foo/bar.test.py")
    # stem is "bar.test", so result preserves the inner dot
    assert issues_path(p) == Path("foo/bar.test.issues.json")


# --- now_utc ---

def test_now_utc_format():
    result = now_utc()
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", result)


# --- format_examples_for_type ---

def test_format_examples_empty():
    assert format_examples_for_type({}, "unknown") == ""


def test_format_examples_with_data():
    examples = {
        "edge-case": {
            "HIGH": ["Example 1"],
            "LOW": ["Example 2"],
        }
    }
    result = format_examples_for_type(examples, "edge-case")
    assert "## Examples" in result
    assert "HIGH" in result
    assert "Example 1" in result
    assert "LOW" in result


def test_format_examples_respects_severity_order():
    examples = {
        "test": {
            "LOW": ["low ex"],
            "CRITICAL": ["critical ex"],
        }
    }
    result = format_examples_for_type(examples, "test")
    assert result.index("CRITICAL") < result.index("LOW")


# --- load_issue_types ---

def test_load_issue_types_returns_list():
    result = load_issue_types()
    assert isinstance(result, list)
    assert len(result) > 0


def test_load_issue_types_has_id_and_body():
    result = load_issue_types()
    for item in result:
        assert "id" in item
        assert "body" in item


# --- Issue-specific tests (fixes verified) ---

def test_dotenv_uses_find_dotenv():
    """load_dotenv uses find_dotenv() instead of hardcoded parents[4]."""
    import inspect
    import call_llm
    source = inspect.getsource(call_llm)
    assert "find_dotenv" in source
    assert "parents[4]" not in source


def test_lazy_client_initialization():
    """Client is initialized lazily via _get_anthropic_client(), not at module level."""
    import call_llm
    assert hasattr(call_llm, "_get_anthropic_client")
    assert callable(call_llm._get_anthropic_client)


def test_cli_timeout_from_env():
    """CLI timeout is configurable via LLM_CLI_TIMEOUT env var."""
    import inspect
    import call_llm
    source = inspect.getsource(call_llm)
    assert "LLM_CLI_TIMEOUT" in source


def test_max_tokens_constant():
    """max_tokens default comes from a module constant."""
    import call_llm
    assert hasattr(call_llm, "DEFAULT_MAX_TOKENS")


def test_default_model_from_env():
    """Default model is readable from LLM_DEFAULT_MODEL env var."""
    import inspect
    import call_llm
    source = inspect.getsource(call_llm)
    assert "LLM_DEFAULT_MODEL" in source


def test_cli_stderr_logged_on_success():
    """Non-empty stderr on success is logged/warned."""
    import inspect
    import call_llm
    source = inspect.getsource(call_llm._call_via_cli)
    after_error_block = source.split("return result.stdout", maxsplit=1)[0]
    assert "warn" in after_error_block.lower() or "log" in after_error_block.lower()


def test_parse_llm_response_accepts_label():
    """parse_llm_response accepts a label parameter."""
    import inspect
    sig = inspect.signature(parse_llm_response)
    assert "label" in sig.parameters


def test_call_llm_has_logging():
    """call_llm logs invocations."""
    import inspect
    import call_llm as call_llm_module
    source = inspect.getsource(call_llm_module.call_llm)
    assert "log" in source.lower()


# --- Issue-specific xfail tests (Phase 4 TDD) ---

def test_parse_llm_response_normalizes_single_object_to_list():
    """parse_llm_response should always return list[dict] | None, never a bare dict."""
    # A single JSON object (not wrapped in an array) — this is what the LLM
    # sometimes returns.  The fix should wrap it into [dict].
    response = '{"fingerprint": "test-issue", "severity": "LOW"}'
    result = parse_llm_response(response)
    assert result is not None
    assert isinstance(result, list), f"Expected list, got {type(result).__name__}"
    assert len(result) == 1
    assert result[0]["fingerprint"] == "test-issue"
