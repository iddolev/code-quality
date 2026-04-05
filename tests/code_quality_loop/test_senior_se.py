"""Tests for senior_se_triage.py."""
from pathlib import Path
from unittest.mock import patch
import json
import sys

import senior_se_triage


ISSUE = {
    "id": 1,
    "fingerprint": "division by zero risk in calculate_average",
    "severity": "HIGH",
    "location": "calculate_average (lines 12-18)",
    "description": "No check for empty input.",
    "fix": "Add `if not values: return 0.0` before the division.",
}

TRIAGE_RESPONSE = [
    {
        "id": 1,
        "triage": "implement",
        "senior_se_reasoning": "Straightforward guard clause, clearly correct.",
    }
]


def _write_issues(tmp_path: Path, stem: str = "sample") -> Path:
    """Write issues file and return the source_path."""
    source_path = tmp_path / f"{stem}.py"
    issues_file = tmp_path / f"{stem}.issues.json"
    issues_file.write_text(json.dumps([ISSUE]), encoding="utf-8")
    return source_path


def test_triage_implement_decision_has_only_decision_fields(tmp_path: Path) -> None:
    source_path = _write_issues(tmp_path)

    with patch("senior_se_triage.call_llm", return_value=json.dumps(TRIAGE_RESPONSE)):
        senior_se_triage.run(source_path)

    decisions_path = tmp_path / "sample.decisions.json"
    decisions = json.loads(decisions_path.read_text())
    assert len(decisions) == 1
    record = decisions[0]
    # Must have decision fields
    assert record["id"] == 1
    assert record["action"] == "implement"
    assert record["decision_by"] == "senior_se"
    assert record["senior_se_reasoning"] == "Straightforward guard clause, clearly correct."
    assert record["status"] == "pending"
    # Must NOT repeat issue content
    assert "fingerprint" not in record
    assert "severity" not in record
    assert "description" not in record
    assert "fix" not in record


def test_triage_no_sets_action_no(tmp_path: Path) -> None:
    source_path = _write_issues(tmp_path)

    triage_no = [{**TRIAGE_RESPONSE[0], "triage": "no",
                  "senior_se_reasoning": "Fix is unnecessary."}]

    with patch("senior_se_triage.call_llm", return_value=json.dumps(triage_no)):
        senior_se_triage.run(source_path)

    decisions_path = tmp_path / "sample.decisions.json"
    record = json.loads(decisions_path.read_text())[0]
    assert record["action"] == "no"
    assert record["decision_by"] == "senior_se"
    assert "fix" not in record


def test_triage_needs_human_sets_action(tmp_path: Path) -> None:
    source_path = _write_issues(tmp_path)

    triage_human = [{**TRIAGE_RESPONSE[0], "triage": "needs_human_approval",
                     "senior_se_reasoning": "Trade-off unclear."}]

    with patch("senior_se_triage.call_llm", return_value=json.dumps(triage_human)):
        senior_se_triage.run(source_path)

    decisions_path = tmp_path / "sample.decisions.json"
    record = json.loads(decisions_path.read_text())[0]
    assert record["action"] == "needs_human_approval"
    assert record["decision_by"] == "senior_se"


def test_decisions_written_to_same_directory(tmp_path: Path) -> None:
    source_path = _write_issues(tmp_path, stem="mymodule")

    with patch("senior_se_triage.call_llm", return_value=json.dumps(TRIAGE_RESPONSE)):
        senior_se_triage.run(source_path)

    decisions_path = tmp_path / "mymodule.decisions.json"
    assert decisions_path.exists()
    assert decisions_path.parent == tmp_path
    assert decisions_path.name == "mymodule.decisions.json"
