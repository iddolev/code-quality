"""Tests for critic.py."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"))
import critic


RAW_ISSUES = [
    {
        "fingerprint": "division by zero risk in calculate_average",
        "severity": "HIGH",
        "location": "calculate_average (lines 12-18)",
        "description": "No check for empty input.",
        "fix": "Add `if not values: return 0.0` before the division.",
    }
]


def test_run_assigns_ids_and_writes_issues_json(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def calculate_average(values):\n    return sum(values) / len(values)\n")

    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps(RAW_ISSUES))]

    with patch("critic.ANTHROPIC_CLIENT") as mock_client:
        mock_client.messages.create.return_value = fake_response
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
    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps(two_issues))]

    with patch("critic.ANTHROPIC_CLIENT") as mock_client:
        mock_client.messages.create.return_value = fake_response
        critic.run(source)

    result_path = tmp_path / "sample.issues.json"
    written = json.loads(result_path.read_text())
    assert written[0]["id"] == 1
    assert written[1]["id"] == 2


def test_run_returns_issues_path_next_to_source(tmp_path: Path) -> None:
    source = tmp_path / "mymodule.py"
    source.write_text("x = 1\n")

    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="[]")]

    with patch("critic.ANTHROPIC_CLIENT") as mock_client:
        mock_client.messages.create.return_value = fake_response
        critic.run(source)

    result_path = tmp_path / "mymodule.issues.json"
    assert result_path.exists()
    assert result_path.parent == tmp_path
    assert result_path.name == "mymodule.issues.json"
