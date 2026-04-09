"""Tests for critic.py."""
from pathlib import Path
from unittest.mock import patch
import json

import critic
from code_quality_loop.common import load_issue_types


RAW_ISSUES = [
    {
        "fingerprint": "division by zero risk in calculate_average",
        "severity": "HIGH",
        "location": "calculate_average (lines 12-18)",
        "description": "No check for empty input.",
        "fix": "Add `if not values: return 0.0` before the division.",
    }
]

# Number of LLM calls = number of issue types (one per type including "other")
_NUM_ISSUE_TYPES = len(load_issue_types())


def test_run_assigns_ids_and_writes_issues_json(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def calculate_average(values):\n    return sum(values) / len(values)\n")

    # One type returns an issue, all others return []
    responses = ["[]"] * _NUM_ISSUE_TYPES
    responses[0] = json.dumps(RAW_ISSUES)

    with patch("critic.call_llm", side_effect=responses):
        critic.run(source)

    result_path = tmp_path / "sample.issues.json"
    assert result_path.exists()
    written = json.loads(result_path.read_text())
    assert len(written) == 1
    assert written[0]["id"] == 1
    assert written[0]["fingerprint"] == RAW_ISSUES[0]["fingerprint"]


def test_run_assigns_sequential_ids(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n")

    two_issues = RAW_ISSUES + [{**RAW_ISSUES[0], "fingerprint": "second issue"}]
    # First type returns two issues, rest return []
    responses = ["[]"] * _NUM_ISSUE_TYPES
    responses[0] = json.dumps(two_issues)

    with patch("critic.call_llm", side_effect=responses):
        critic.run(source)

    result_path = tmp_path / "sample.issues.json"
    written = json.loads(result_path.read_text())
    assert written[0]["id"] == 1
    assert written[1]["id"] == 2


def test_run_returns_issues_path_next_to_source(tmp_path: Path) -> None:
    source = tmp_path / "mymodule.py"
    source.write_text("x = 1\n")

    responses = ["[]"] * _NUM_ISSUE_TYPES

    with patch("critic.call_llm", side_effect=responses):
        critic.run(source)

    result_path = tmp_path / "mymodule.issues.json"
    assert result_path.exists()
    assert result_path.parent == tmp_path
    assert result_path.name == "mymodule.issues.json"


def test_issues_from_multiple_types_get_sequential_ids(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("x = 1\n")

    issue_a = [{
        "fingerprint": "issue from type A",
        "severity": "HIGH",
        "location": "foo",
        "description": "desc a",
        "fix": "fix a",
    }]
    issue_b = [{
        "fingerprint": "issue from type B",
        "severity": "MEDIUM",
        "location": "bar",
        "description": "desc b",
        "fix": "fix b",
    }]
    responses = ["[]"] * _NUM_ISSUE_TYPES
    responses[0] = json.dumps(issue_a)
    responses[2] = json.dumps(issue_b)

    with patch("critic.call_llm", side_effect=responses):
        critic.run(source)

    written = json.loads((tmp_path / "sample.issues.json").read_text())
    assert len(written) == 2
    assert written[0]["id"] == 1
    assert written[1]["id"] == 2
    assert written[0]["fingerprint"] == "issue from type A"
    assert written[1]["fingerprint"] == "issue from type B"
