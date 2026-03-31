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
    return source, decisions_path


def test_applicable_fix_applied_and_status_done(tmp_path: Path) -> None:
    source, decisions_path = _write_files(tmp_path, [ISSUE], [DECISION_IMPLEMENT])

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_fake_response("applicable"),
            _make_fake_response(FIXED_SOURCE),
        ]
        rewriter.run(source, decisions_path)

    assert source.read_text() == FIXED_SOURCE
    decisions = json.loads(decisions_path.read_text())
    assert decisions[0]["status"] == "done"


def test_custom_fix_overrides_issue_fix(tmp_path: Path) -> None:
    custom_decision = {**DECISION_IMPLEMENT, "action": "custom",
                       "custom_fix": "raise ValueError('empty')"}
    source, decisions_path = _write_files(tmp_path, [ISSUE], [custom_decision])

    call_args = []

    def capturing_create(**kwargs):
        call_args.append(kwargs)
        return _make_fake_response(FIXED_SOURCE)

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = capturing_create

        rewriter.run(source, decisions_path)

    # call_args[0] = relevance check call, call_args[1] = fix application call
    fix_call_content = call_args[1]["messages"][0]["content"]
    assert "raise ValueError" in fix_call_content
    assert "return 0.0" not in fix_call_content


def test_impossible_updates_status_and_skips_fix(tmp_path: Path) -> None:
    source, decisions_path = _write_files(tmp_path, [ISSUE], [DECISION_IMPLEMENT])

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_fake_response(
            "impossible\nThe function was removed."
        )
        rewriter.run(source, decisions_path)

    assert source.read_text() == ORIGINAL_SOURCE
    decisions = json.loads(decisions_path.read_text())
    assert decisions[0]["status"] == "impossible"
    assert "explanation" in decisions[0]


def test_no_longer_relevant_updates_status(tmp_path: Path) -> None:
    source, decisions_path = _write_files(tmp_path, [ISSUE], [DECISION_IMPLEMENT])

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_fake_response(
            "no_longer_relevant\nAlready fixed."
        )
        rewriter.run(source, decisions_path)

    decisions = json.loads(decisions_path.read_text())
    assert decisions[0]["status"] == "no_longer_relevant"
    assert "explanation" in decisions[0]


def test_action_no_and_skip_are_ignored(tmp_path: Path) -> None:
    source, decisions_path = _write_files(
        tmp_path,
        [ISSUE_NO, ISSUE_SKIP],
        [DECISION_NO, DECISION_SKIP],
    )

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        rewriter.run(source, decisions_path)

    mock_client.messages.create.assert_not_called()
    assert source.read_text() == ORIGINAL_SOURCE


def test_fix_counter_only_increments_on_done(tmp_path: Path, capsys) -> None:
    issue2 = {**ISSUE, "id": 2, "fingerprint": "second issue", "fix": "do something else"}
    decision2 = {**DECISION_IMPLEMENT, "id": 2}
    source, decisions_path = _write_files(
        tmp_path, [ISSUE, issue2], [DECISION_IMPLEMENT, decision2]
    )

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_fake_response("impossible"),    # issue 1: impossible
            _make_fake_response("applicable"),    # issue 2: applicable
            _make_fake_response(FIXED_SOURCE),    # issue 2: fix applied
        ]
        rewriter.run(source, decisions_path)

    captured = capsys.readouterr()
    assert "1/2" in captured.out


def test_empty_string_custom_fix_is_used_not_overridden(tmp_path: Path) -> None:
    # custom_fix="" means "apply nothing" — should NOT fall back to issue fix
    custom_decision = {**DECISION_IMPLEMENT, "action": "custom", "custom_fix": ""}
    source, decisions_path = _write_files(tmp_path, [ISSUE], [custom_decision])

    call_args = []

    def capturing_create(**kwargs):
        call_args.append(kwargs)
        return _make_fake_response(FIXED_SOURCE)

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = capturing_create

        rewriter.run(source, decisions_path)

    # Second call is fix application — empty string should be passed, not issue fix
    fix_call_content = call_args[1]["messages"][0]["content"]
    assert "return 0.0" not in fix_call_content  # issue fix NOT used
