"""Tests for rewriter.py."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"))
import rewriter

ISSUE = {
    "id": 1,
    "fingerprint": "division by zero risk in calculate_average",
    "severity": "HIGH",
    "location": "calculate_average (lines 12-18)",
    "description": "No check for empty input.",
    "fix": "Add `if not values: return 0.0` before the division.",
}

DECISION_IMPLEMENT = {
    "id": 1,
    "action": "implement",
    "decision_by": "senior_se",
    "senior_se_reasoning": "Clear fix.",
    "status": "pending",
}

DECISION_NO = {"id": 2, "action": "no", "decision_by": "senior_se",
               "senior_se_reasoning": "Not needed.", "status": "pending"}
DECISION_SKIP = {"id": 3, "action": "skip_for_now", "decision_by": "senior_se",
                 "senior_se_reasoning": "Defer.", "status": "pending"}

ISSUE_NO = {**ISSUE, "id": 2, "fingerprint": "second issue"}
ISSUE_SKIP = {**ISSUE, "id": 3, "fingerprint": "third issue"}

ORIGINAL_SOURCE = "def calculate_average(values):\n    return sum(values) / len(values)\n"
FIXED_SOURCE = (
    "def calculate_average(values):\n"
    "    if not values:\n"
    "        return 0.0\n"
    "    return sum(values) / len(values)\n"
)


def _make_fake_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


def _write_files(tmp_path, issues, decisions):
    source = tmp_path / "sample.py"
    source.write_text(ORIGINAL_SOURCE)
    issues_path = tmp_path / "sample.issues.json"
    issues_path.write_text(json.dumps(issues))
    decisions_path = tmp_path / "sample.decisions.json"
    decisions_path.write_text(json.dumps(decisions))
    return source


def test_applicable_fix_applied_and_status_done(tmp_path: Path) -> None:
    source = _write_files(tmp_path, [ISSUE], [DECISION_IMPLEMENT])

    with patch("rewriter.ANTHROPIC_CLIENT") as mock_client:
        mock_client.messages.create.return_value = _make_fake_response(FIXED_SOURCE)
        rewriter.run(source, issue_id=1)

    assert source.read_text() == FIXED_SOURCE
    decisions = json.loads((tmp_path / "sample.decisions.json").read_text())
    assert decisions[0]["status"] == "done"


def test_custom_fix_overrides_issue_fix(tmp_path: Path) -> None:
    custom_decision = {**DECISION_IMPLEMENT, "action": "custom",
                       "custom_fix": "raise ValueError('empty')"}
    source = _write_files(tmp_path, [ISSUE], [custom_decision])

    call_args = []

    def capturing_create(**kwargs):
        call_args.append(kwargs)
        return _make_fake_response(FIXED_SOURCE)

    with patch("rewriter.ANTHROPIC_CLIENT") as mock_client:
        mock_client.messages.create.side_effect = capturing_create
        rewriter.run(source, issue_id=1)

    fix_call_content = call_args[0]["messages"][0]["content"]
    assert "raise ValueError" in fix_call_content
    assert "return 0.0" not in fix_call_content


def test_action_no_and_skip_are_not_actionable(tmp_path: Path) -> None:
    source = _write_files(
        tmp_path,
        [ISSUE_NO, ISSUE_SKIP],
        [DECISION_NO, DECISION_SKIP],
    )

    with patch("rewriter.ANTHROPIC_CLIENT") as mock_client:
        # issue_id=2 has action "no" — should not be found as actionable
        try:
            rewriter.run(source, issue_id=2)
            ran = True
        except SystemExit:
            ran = False

    assert not ran
    mock_client.messages.create.assert_not_called()
    assert source.read_text() == ORIGINAL_SOURCE


def test_empty_string_custom_fix_is_used_not_overridden(tmp_path: Path) -> None:
    custom_decision = {**DECISION_IMPLEMENT, "action": "custom", "custom_fix": ""}
    source = _write_files(tmp_path, [ISSUE], [custom_decision])

    call_args = []

    def capturing_create(**kwargs):
        call_args.append(kwargs)
        return _make_fake_response(FIXED_SOURCE)

    with patch("rewriter.ANTHROPIC_CLIENT") as mock_client:
        mock_client.messages.create.side_effect = capturing_create
        rewriter.run(source, issue_id=1)

    fix_call_content = call_args[0]["messages"][0]["content"]
    assert "return 0.0" not in fix_call_content  # issue fix NOT used
