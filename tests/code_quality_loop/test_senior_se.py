"""Tests for senior_se.py."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"))
import senior_se


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


def _make_fake_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


def test_triage_implement_decision_has_only_decision_fields(tmp_path: Path) -> None:
    issues_path = tmp_path / "sample.issues.json"
    issues_path.write_text(json.dumps([ISSUE]), encoding="utf-8")

    with patch("senior_se.anthropic.Anthropic") as mock_cls, \
         patch("senior_se._consult_human") as mock_human:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_fake_response(
            json.dumps(TRIAGE_RESPONSE)
        )
        decisions_path = senior_se.run(issues_path)

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
    mock_human.assert_not_called()


def test_triage_no_sets_action_no(tmp_path: Path) -> None:
    issues_path = tmp_path / "sample.issues.json"
    issues_path.write_text(json.dumps([ISSUE]), encoding="utf-8")

    triage_no = [{**TRIAGE_RESPONSE[0], "triage": "no",
                  "senior_se_reasoning": "Fix is unnecessary."}]

    with patch("senior_se.anthropic.Anthropic") as mock_cls, \
         patch("senior_se._consult_human"):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_fake_response(json.dumps(triage_no))
        decisions_path = senior_se.run(issues_path)

    record = json.loads(decisions_path.read_text())[0]
    assert record["action"] == "no"
    assert record["decision_by"] == "senior_se"
    assert "fix" not in record


def test_triage_needs_human_calls_consult(tmp_path: Path) -> None:
    issues_path = tmp_path / "sample.issues.json"
    issues_path.write_text(json.dumps([ISSUE]), encoding="utf-8")

    triage_human = [{**TRIAGE_RESPONSE[0], "triage": "needs_human_approval",
                     "senior_se_reasoning": "Trade-off unclear."}]

    human_result = {"id": 1, "action": "skip_for_now", "decision_by": "human",
                    "senior_se_reasoning": "Trade-off unclear.", "status": "pending"}

    with patch("senior_se.anthropic.Anthropic") as mock_cls, \
         patch("senior_se._consult_human", return_value=human_result) as mock_human:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_fake_response(
            json.dumps(triage_human)
        )
        decisions_path = senior_se.run(issues_path)

    mock_human.assert_called_once()
    record = json.loads(decisions_path.read_text())[0]
    assert record["action"] == "skip_for_now"
    assert record["decision_by"] == "human"


def test_decisions_written_to_same_directory(tmp_path: Path) -> None:
    issues_path = tmp_path / "mymodule.issues.json"
    issues_path.write_text(json.dumps([ISSUE]), encoding="utf-8")

    with patch("senior_se.anthropic.Anthropic") as mock_cls, \
         patch("senior_se._consult_human"):
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_fake_response(
            json.dumps(TRIAGE_RESPONSE)
        )
        decisions_path = senior_se.run(issues_path)

    assert decisions_path.parent == tmp_path
    assert decisions_path.name == "mymodule.decisions.json"
