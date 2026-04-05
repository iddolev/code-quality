"""Tests for parse_llm_response and _extract_json."""
import json

from common import parse_llm_response


# --- Clean JSON (no extraction needed) ---

def test_plain_object():
    assert parse_llm_response('{"rule": "x"}') == {"rule": "x"}


def test_plain_array():
    assert parse_llm_response('[{"rule": "x"}]') == [{"rule": "x"}]


def test_empty_object():
    assert parse_llm_response("{}") == {}


def test_empty_array():
    assert parse_llm_response("[]") == []


# --- Fenced JSON ---

def test_fenced_json_object():
    text = 'Here is the result:\n```json\n{"rule": "x"}\n```'
    assert parse_llm_response(text) == {"rule": "x"}


def test_fenced_json_array():
    text = 'Some prose\n```json\n[{"rule": "x"}]\n```\n'
    assert parse_llm_response(text) == [{"rule": "x"}]


def test_fenced_no_lang_tag():
    text = 'Explanation:\n```\n{"rule": "x"}\n```'
    assert parse_llm_response(text) == {"rule": "x"}


def test_fenced_empty_object():
    text = 'No violations:\n```json\n{}\n```'
    assert parse_llm_response(text) == {}


def test_fenced_empty_array():
    text = 'No issues:\n```json\n[]\n```'
    assert parse_llm_response(text) == []


def test_fenced_multiline_with_newlines():
    text = 'Result:\n```json\n{\n  "rule": "x",\n  "location": "foo"\n}\n```'
    assert parse_llm_response(text) == {"rule": "x", "location": "foo"}


def test_fenced_array_with_newlines():
    text = 'Issues:\n```json\n[\n  {\n    "rule": "x"\n  }\n]\n```'
    assert parse_llm_response(text) == [{"rule": "x"}]


# --- Prose + bare JSON ---

def test_prose_before_object():
    text = 'I found a violation.\n{"rule": "x", "location": "foo"}'
    assert parse_llm_response(text) == {"rule": "x", "location": "foo"}


def test_prose_before_array():
    text = 'Here are the issues:\n[{"rule": "x", "fingerprint": "test"}]'
    assert parse_llm_response(text) == [{"rule": "x", "fingerprint": "test"}]


# --- Multiline JSON ---

def test_multiline_fenced_object():
    obj = {"rule": "visual flow #1", "new": "code"}
    text = f'Result:\n```json\n{json.dumps(obj, indent=2)}\n```'
    assert parse_llm_response(text) == obj


def test_multiline_bare_array():
    arr = [{"rule": "x", "severity": "HIGH"}]
    text = f'Found issues:\n{json.dumps(arr, indent=2)}'
    assert parse_llm_response(text) == arr


# --- Failures ---

def test_no_json_returns_none():
    assert parse_llm_response("Just some plain text, no JSON here.") is None


def test_invalid_json_returns_none():
    assert parse_llm_response('{"broken": }') is None


# --- Claude self-correction ---

def test_claude_corrects_fenced_then_outputs_empty():
    """Claude outputs a fenced JSON, then says 'actually no', then outputs []."""
    text = (
        'Here is the issue:\n'
        '```json\n[{"rule": "wrong answer"}]\n```\n'
        'Actually, I realize this is not a real issue.\n'
        '[]'
    )
    assert parse_llm_response(text) == []


def test_claude_corrects_fenced_then_outputs_different():
    """Claude outputs a fenced JSON, then corrects with different JSON at end."""
    text = (
        '```json\n{"rule": "old", "location": "foo"}\n```\n'
        'Wait, the location is actually bar.\n'
        '{"rule": "new", "location": "bar"}'
    )
    assert parse_llm_response(text) == {"rule": "new", "location": "bar"}


def test_newline_after_brace_in_object():
    text = 'Some text\n{\n"rule": "x",\n"location": "foo"\n}'
    assert parse_llm_response(text) == {"rule": "x", "location": "foo"}


def test_newline_after_bracket_in_array():
    text = 'Some text\n[\n{\n"rule": "x"\n}\n]'
    assert parse_llm_response(text) == [{"rule": "x"}]
