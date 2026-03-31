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

    with patch("critic.anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = fake_response

        result_path = critic.run(source)

    assert result_path == tmp_path / "sample.issues.json"
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

    with patch("critic.anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = fake_response

        result_path = critic.run(source)

    written = json.loads(result_path.read_text())
    assert written[0]["id"] == 1
    assert written[1]["id"] == 2


def test_run_returns_issues_path_next_to_source(tmp_path: Path) -> None:
    source = tmp_path / "mymodule.py"
    source.write_text("x = 1\n")

    fake_response = MagicMock()
    fake_response.content = [MagicMock(text="[]")]

    with patch("critic.anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = fake_response

        result_path = critic.run(source)

    assert result_path.parent == tmp_path
    assert result_path.name == "mymodule.issues.json"


# ── orchestrator smoke test ───────────────────────────────────────────────────

def test_orchestrator_calls_all_phases(tmp_path: Path) -> None:
    """The orchestrator imports critic, senior_se, rewriter and calls run() on each."""
    import types
    import sys as _sys

    for name in ("critic", "senior_se", "rewriter"):
        mod = types.ModuleType(name)
        mod.run = MagicMock(return_value=tmp_path / f"stub.{name}.json")  # type: ignore[attr-defined]
        _sys.modules[name] = mod

    _sys.modules.pop("code_quality_loop", None)
    orch_path = Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"
    _sys.path.insert(0, str(orch_path))

    import code_quality_loop
    source = tmp_path / "sample.py"
    code_quality_loop.main(source)

    _sys.modules["critic"].run.assert_called_once_with(source)
