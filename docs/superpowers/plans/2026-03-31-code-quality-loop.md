# Code Quality Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a three-script Python pipeline that critiques a Python file with an
LLM, triages issues via a senior SE LLM (escalating unclear ones to the human),
and applies approved fixes one at a time.

**Architecture:** Three focused modules (`critic.py`, `senior_se.py`, `rewriter.py`)
each called by a thin orchestrator (`code_quality_loop.py`). Each module calls the
Anthropic API with a dedicated system prompt loaded from a sibling `.md` file.
JSON artifacts are written to the same directory as the input file.

**Tech Stack:** Python 3.11+, `anthropic` SDK (v0.84+), `pytest`, `unittest.mock`

**Spec:** `docs/superpowers/specs/2026-03-31-code-quality-loop-design.md`

---

## File Map

| File | Role |
|------|------|
| `scripts/code_quality_loop/critic_prompt.md` | System prompt for critic LLM |
| `scripts/code_quality_loop/senior_se_triage_prompt.md` | System prompt for autonomous triage LLM |
| `scripts/code_quality_loop/senior_se_custom_prompt.md` | System prompt for "something else" option |
| `scripts/code_quality_loop/relevance_check_prompt.md` | System prompt for relevance check LLM |
| `scripts/code_quality_loop/rewriter_prompt.md` | System prompt for rewriter LLM |
| `scripts/code_quality_loop/critic.py` | Phase 1: calls LLM, writes issues JSON |
| `scripts/code_quality_loop/senior_se.py` | Phase 2: triage + human consultation |
| `scripts/code_quality_loop/rewriter.py` | Phase 3: relevance check + apply fixes |
| `scripts/code_quality_loop/code_quality_loop.py` | Orchestrator entry point |
| `tests/code_quality_loop/test_critic.py` | Tests for critic module |
| `tests/code_quality_loop/test_senior_se.py` | Tests for senior_se module |
| `tests/code_quality_loop/test_rewriter.py` | Tests for rewriter module |

---

## Task 1: Create directory structure and prompt files

**Files:**

- Create: `scripts/code_quality_loop/` (directory)
- Create: `tests/code_quality_loop/` (directory)
- Create: `scripts/code_quality_loop/critic_prompt.md`
- Create: `scripts/code_quality_loop/senior_se_triage_prompt.md`
- Create: `scripts/code_quality_loop/senior_se_custom_prompt.md`
- Create: `scripts/code_quality_loop/relevance_check_prompt.md`
- Create: `scripts/code_quality_loop/rewriter_prompt.md`

- [ ] **Step 1: Create directories**

```bash
mkdir -p scripts/code_quality_loop tests/code_quality_loop
touch tests/code_quality_loop/__init__.py
```

- [ ] **Step 2: Write `critic_prompt.md`**

Copy from `sandbox/critic_prompt.md` — it is already complete and correct.

```bash
cp sandbox/critic_prompt.md scripts/code_quality_loop/critic_prompt.md
```

- [ ] **Step 3: Write `senior_se_triage_prompt.md`**

Create `scripts/code_quality_loop/senior_se_triage_prompt.md`:

```markdown
# Senior Software Engineer — Issue Triage

You are a senior software engineer reviewing a list of code issues flagged by an
automated critic. Your job is to decide, for each issue, what action to take.

## Input

You will receive a JSON array of issue objects. Each has these fields:
fingerprint, severity, location, description, fix.

## Output

Return ONLY a valid JSON array. No prose before or after. No markdown fences.
One entry per input issue, in the same order.

Each entry must have exactly these fields:

{
  "fingerprint":         "<copied exactly from the input issue>",
  "triage":              "implement" | "no" | "needs_human_approval",
  "senior_se_reasoning": "<one sentence explaining the decision>"
}

## Triage rules

- implement: The fix is clearly correct, essential, and safe to apply without
  further review. The description and fix are unambiguous.
- no: The fix is wrong, unnecessary, or would make the code worse. Do not apply it.
- needs_human_approval: The fix involves a design trade-off, is ambiguous, or
  requires knowledge of intent that you cannot infer from the code alone.

## Important

- Every input issue must produce exactly one output entry.
- Preserve the exact fingerprint string — it is used to match output back to input.
- Be decisive: only escalate to needs_human_approval when genuinely unclear.
```

- [ ] **Step 4: Write `senior_se_custom_prompt.md`**

Create `scripts/code_quality_loop/senior_se_custom_prompt.md`:

```markdown
# Senior Software Engineer — Custom Instruction Interpreter

You are a senior software engineer. The human has reviewed a code issue and
provided a custom instruction instead of picking a standard option.

## Input

You will receive a JSON object with two keys:
- "issue": the original issue object (fingerprint, severity, location,
  description, fix)
- "user_input": the human's free-text instruction

## Output

Return ONLY a valid JSON object representing the updated issue. No prose before
or after. No markdown fences.

The returned object must include all original issue fields. You may:
- Update the "fix" field to reflect the human's intent (ALWAYS do this if the
  intent changes the fix — the "fix" field is what the rewriter will implement)
- Add a "user_note" field with a brief summary of the human's intent
- Update "description" if the human clarified what the real problem is

The "fix" field is always authoritative: make it a clear, concrete instruction
for the rewriter.

## Important

- Interpret the human's intent charitably and precisely.
- If the human's instruction is to do nothing or skip, set fix to an empty
  string and add user_note explaining why.
- Never invent changes the human did not request.
```

- [ ] **Step 5: Write `relevance_check_prompt.md`**

Create `scripts/code_quality_loop/relevance_check_prompt.md`:

```markdown
# Relevance Check

You are reviewing whether a previously identified code issue is still applicable
given the current state of the file (which may have been modified by prior fixes).

## Input

You will receive:
1. The current content of the Python file
2. A JSON object describing the issue (fingerprint, location, description, fix)

## Output

Return ONLY one of these three words, with no other text:

applicable
impossible
no_longer_relevant

## Definitions

- applicable: The issue still exists in the current file and the described fix
  can be applied as written.
- impossible: The issue location or structure no longer exists in the file in a
  way that allows the fix to be applied (e.g. the function was restructured or
  removed by a prior fix).
- no_longer_relevant: The issue has already been resolved by a prior fix (the
  problem described no longer exists in the code).
```

- [ ] **Step 6: Write `rewriter_prompt.md`**

Create `scripts/code_quality_loop/rewriter_prompt.md`:

```markdown
# Code Rewriter

You are a precise code editor. You will apply exactly one fix to a Python file.

## Input

You will receive:
1. The current content of the Python file
2. A JSON object describing the fix to apply (the "fix" field is the instruction)

## Output

Return ONLY the complete rewritten Python file content. No prose before or after.
No markdown fences. No explanation.

## Rules

- Apply ONLY the fix described in the "fix" field of the issue object.
- Do not fix anything else, even if you notice other issues.
- Preserve all formatting, comments, docstrings, and unrelated code exactly.
- If the fix instruction is empty or says to do nothing, return the file unchanged.
```

- [ ] **Step 7: Commit**

```bash
git add scripts/code_quality_loop/ tests/code_quality_loop/
git commit -m "feat: add prompt files and directory structure for code quality loop"
```

---

## Task 2: Critic module

**Files:**

- Create: `scripts/code_quality_loop/critic.py`
- Create: `tests/code_quality_loop/test_critic.py`

The critic reads a Python file, calls Claude with the critic prompt, and writes
the returned JSON array to `<stem>.issues.json` in the same directory.

- [ ] **Step 1: Write the failing test**

Create `tests/code_quality_loop/test_critic.py`:

```python
"""Tests for critic.py."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"))
import critic


SAMPLE_ISSUES = [
    {
        "fingerprint": "division by zero risk in calculate_average",
        "severity": "HIGH",
        "location": "calculate_average (lines 12-18)",
        "description": "No check for empty input.",
        "fix": "Add `if not values: return 0.0` before the division.",
    }
]


def test_run_writes_issues_json(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def calculate_average(values):\n    return sum(values) / len(values)\n")

    fake_response = MagicMock()
    fake_response.content = [MagicMock(text=json.dumps(SAMPLE_ISSUES))]

    with patch("critic.anthropic.Anthropic") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        mock_client.messages.create.return_value = fake_response

        result_path = critic.run(source)

    assert result_path == tmp_path / "sample.issues.json"
    assert result_path.exists()
    written = json.loads(result_path.read_text())
    assert written == SAMPLE_ISSUES


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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/code_quality_loop/test_critic.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'critic'`

- [ ] **Step 3: Implement `critic.py`**

Create `scripts/code_quality_loop/critic.py`:

```python
"""Phase 1 — Critic.

Reads a Python source file, sends it to Claude for review,
and writes the resulting issues to a JSON file.
"""
from __future__ import annotations

import json
from pathlib import Path

import anthropic

_PROMPTS_DIR = Path(__file__).resolve().parent
_MODEL = "claude-opus-4-6"


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def run(source_path: Path) -> Path:
    """Run the critic on *source_path* and return the path to the issues JSON."""
    source_code = source_path.read_text(encoding="utf-8")
    system_prompt = _load_prompt("critic_prompt.md")

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": source_code}],
    )
    issues = json.loads(response.content[0].text)

    issues_path = source_path.with_suffix("").with_suffix(".issues.json")
    issues_path.write_text(json.dumps(issues, indent=2), encoding="utf-8")
    return issues_path
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/code_quality_loop/test_critic.py -v
```

Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/code_quality_loop/critic.py tests/code_quality_loop/test_critic.py
git commit -m "feat: implement critic module (phase 1)"
```

---

## Task 3: Senior SE module — autonomous triage

**Files:**

- Create: `scripts/code_quality_loop/senior_se.py`
- Create: `tests/code_quality_loop/test_senior_se.py`

The triage step sends all issues to Claude and receives one triage entry per
issue. The result is merged back into the issue objects.

- [ ] **Step 1: Write the failing test**

Create `tests/code_quality_loop/test_senior_se.py`:

```python
"""Tests for senior_se.py."""
from pathlib import Path
from unittest.mock import MagicMock, patch
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"))
import senior_se


ISSUE = {
    "fingerprint": "division by zero risk in calculate_average",
    "severity": "HIGH",
    "location": "calculate_average (lines 12-18)",
    "description": "No check for empty input.",
    "fix": "Add `if not values: return 0.0` before the division.",
}

TRIAGE_RESPONSE = [
    {
        "fingerprint": "division by zero risk in calculate_average",
        "triage": "implement",
        "senior_se_reasoning": "Straightforward guard clause, clearly correct.",
    }
]


def _make_fake_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


def test_triage_implement_sets_action_and_decision_by(tmp_path: Path) -> None:
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
    assert record["action"] == "implement"
    assert record["decision_by"] == "senior_se"
    assert record["senior_se_reasoning"] == "Straightforward guard clause, clearly correct."
    assert record["status"] == "pending"
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


def test_triage_needs_human_calls_consult(tmp_path: Path) -> None:
    issues_path = tmp_path / "sample.issues.json"
    issues_path.write_text(json.dumps([ISSUE]), encoding="utf-8")

    triage_human = [{**TRIAGE_RESPONSE[0], "triage": "needs_human_approval",
                     "senior_se_reasoning": "Trade-off unclear."}]

    human_result = {**ISSUE, "action": "skip_for_now", "decision_by": "human",
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
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/code_quality_loop/test_senior_se.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'senior_se'`

- [ ] **Step 3: Implement triage logic in `senior_se.py`**

Create `scripts/code_quality_loop/senior_se.py`:

```python
"""Phase 2 — Senior Software Engineer.

Triages issues autonomously via LLM, then consults the human for
escalated (needs_human_approval) issues.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic

_PROMPTS_DIR = Path(__file__).resolve().parent
_MODEL = "claude-opus-4-6"

_TRIAGE_TO_ACTION = {
    "implement": "implement",
    "no": "no",
}


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _triage_issues(
    issues: list[dict[str, Any]],
    client: anthropic.Anthropic,
) -> list[dict[str, Any]]:
    """Call Claude to triage all issues. Returns list of triage dicts."""
    system_prompt = _load_prompt("senior_se_triage_prompt.md")
    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(issues, indent=2)}],
    )
    return json.loads(response.content[0].text)


def _consult_human(
    issue: dict[str, Any],
    senior_se_reasoning: str,
    issue_index: int,
    total: int,
    client: anthropic.Anthropic,
) -> dict[str, Any]:
    """Display the issue to the human and return the updated decision record."""
    print(f"\n{'─' * 53}")
    print(f"Issue {issue_index}/{total}  [{issue['severity']}]  ⚠ Needs your input")
    print(f"Location:    {issue['location']}")
    print(f"Fingerprint: {issue['fingerprint']}")
    print(f"\nDescription: {issue['description']}")
    print(f"\nFix: {issue['fix']}")
    print(f"\nSenior SE note: {senior_se_reasoning}")
    print(f"{'─' * 53}")
    print("  1) Do it")
    print("  2) Don't do it")
    print("  3) Skip for now")
    print("  4) Something else")

    while True:
        choice = input("> ").strip()
        if choice in ("1", "2", "3", "4"):
            break
        print("Please enter 1, 2, 3, or 4.")

    record = {
        **issue,
        "decision_by": "human",
        "senior_se_reasoning": senior_se_reasoning,
        "status": "pending",
    }

    if choice == "1":
        record["action"] = "implement"
    elif choice == "2":
        record["action"] = "no"
    elif choice == "3":
        record["action"] = "skip_for_now"
    else:
        user_input = input("Describe what you'd like instead:\n> ").strip()
        record = _apply_custom_instruction(issue, user_input, senior_se_reasoning, client)

    return record


def _apply_custom_instruction(
    issue: dict[str, Any],
    user_input: str,
    senior_se_reasoning: str,
    client: anthropic.Anthropic,
) -> dict[str, Any]:
    """Send the issue + user free text to Claude and return the updated record."""
    system_prompt = _load_prompt("senior_se_custom_prompt.md")
    payload = {"issue": issue, "user_input": user_input}
    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
    )
    updated_issue = json.loads(response.content[0].text)
    return {
        **updated_issue,
        "action": "custom",
        "decision_by": "human",
        "senior_se_reasoning": senior_se_reasoning,
        "status": "pending",
    }


def run(issues_path: Path) -> Path:
    """Run the senior SE phase and return the path to the decisions JSON."""
    issues = json.loads(issues_path.read_text(encoding="utf-8"))
    decisions_path = issues_path.with_name(
        issues_path.name.replace(".issues.json", ".decisions.json")
    )

    client = anthropic.Anthropic()
    triage_results = _triage_issues(issues, client)

    # Index triage results by fingerprint for O(1) lookup
    triage_by_fingerprint = {t["fingerprint"]: t for t in triage_results}

    decisions: list[dict[str, Any]] = []
    total = len(issues)

    for i, issue in enumerate(issues, start=1):
        triage = triage_by_fingerprint[issue["fingerprint"]]
        triage_label = triage["triage"]
        reasoning = triage["senior_se_reasoning"]

        if triage_label in _TRIAGE_TO_ACTION:
            record = {
                **issue,
                "action": _TRIAGE_TO_ACTION[triage_label],
                "decision_by": "senior_se",
                "senior_se_reasoning": reasoning,
                "status": "pending",
            }
        else:
            record = _consult_human(issue, reasoning, i, total, client)

        decisions.append(record)
        decisions_path.write_text(json.dumps(decisions, indent=2), encoding="utf-8")

    return decisions_path
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/code_quality_loop/test_senior_se.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/code_quality_loop/senior_se.py tests/code_quality_loop/test_senior_se.py
git commit -m "feat: implement senior SE module (phase 2) — triage + human consultation"
```

---

## Task 4: Rewriter module

**Files:**

- Create: `scripts/code_quality_loop/rewriter.py`
- Create: `tests/code_quality_loop/test_rewriter.py`

The rewriter iterates over `implement`/`custom` decisions, checks relevance,
applies fixes one at a time, and updates the decisions JSON after each step.

- [ ] **Step 1: Write the failing test**

Create `tests/code_quality_loop/test_rewriter.py`:

```python
"""Tests for rewriter.py."""
from pathlib import Path
from unittest.mock import MagicMock, patch, call
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"))
import rewriter

ISSUE_IMPLEMENT = {
    "fingerprint": "division by zero risk in calculate_average",
    "severity": "HIGH",
    "location": "calculate_average (lines 12-18)",
    "description": "No check for empty input.",
    "fix": "Add `if not values: return 0.0` before the division.",
    "action": "implement",
    "decision_by": "senior_se",
    "senior_se_reasoning": "Clear fix.",
    "status": "pending",
}

ISSUE_NO = {**ISSUE_IMPLEMENT, "fingerprint": "some other issue", "action": "no"}
ISSUE_SKIP = {**ISSUE_IMPLEMENT, "fingerprint": "yet another issue", "action": "skip_for_now"}

ORIGINAL_SOURCE = "def calculate_average(values):\n    return sum(values) / len(values)\n"
FIXED_SOURCE = "def calculate_average(values):\n    if not values:\n        return 0.0\n    return sum(values) / len(values)\n"


def _make_fake_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    return resp


def test_applicable_fix_applied_and_status_done(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(ORIGINAL_SOURCE)
    decisions_path = tmp_path / "sample.decisions.json"
    decisions_path.write_text(json.dumps([ISSUE_IMPLEMENT]))

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


def test_impossible_updates_status_and_skips_fix(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(ORIGINAL_SOURCE)
    decisions_path = tmp_path / "sample.decisions.json"
    decisions_path.write_text(json.dumps([ISSUE_IMPLEMENT]))

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_fake_response(
            "impossible\nThe function was removed."
        )
        rewriter.run(source, decisions_path)

    assert source.read_text() == ORIGINAL_SOURCE  # file unchanged
    decisions = json.loads(decisions_path.read_text())
    assert decisions[0]["status"] == "impossible"
    assert "explanation" in decisions[0]


def test_no_longer_relevant_updates_status(tmp_path: Path) -> None:
    source = tmp_path / "sample.py"
    source.write_text(ORIGINAL_SOURCE)
    decisions_path = tmp_path / "sample.decisions.json"
    decisions_path.write_text(json.dumps([ISSUE_IMPLEMENT]))

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
    source = tmp_path / "sample.py"
    source.write_text(ORIGINAL_SOURCE)
    decisions_path = tmp_path / "sample.decisions.json"
    decisions_path.write_text(json.dumps([ISSUE_NO, ISSUE_SKIP]))

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        rewriter.run(source, decisions_path)

    mock_client.messages.create.assert_not_called()
    assert source.read_text() == ORIGINAL_SOURCE


def test_fix_counter_only_increments_on_done(tmp_path: Path, capsys) -> None:
    source = tmp_path / "sample.py"
    source.write_text(ORIGINAL_SOURCE)

    issue2 = {**ISSUE_IMPLEMENT, "fingerprint": "second issue", "fix": "do something else"}
    decisions_path = tmp_path / "sample.decisions.json"
    decisions_path.write_text(json.dumps([ISSUE_IMPLEMENT, issue2]))

    with patch("rewriter.anthropic.Anthropic") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [
            _make_fake_response("impossible"),       # issue 1 relevance check → impossible
            _make_fake_response("applicable"),       # issue 2 relevance check → applicable
            _make_fake_response(FIXED_SOURCE),       # issue 2 fix applied
        ]
        rewriter.run(source, decisions_path)

    captured = capsys.readouterr()
    # Only 1 fix was applied (out of 2 to-process), counter should show 1/2
    assert "1/2" in captured.out
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/code_quality_loop/test_rewriter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'rewriter'`

- [ ] **Step 3: Implement `rewriter.py`**

Create `scripts/code_quality_loop/rewriter.py`:

```python
"""Phase 3 — Rewriter.

For each approved issue, checks relevance against the current file state,
then applies the fix if still applicable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic

_PROMPTS_DIR = Path(__file__).resolve().parent
_MODEL = "claude-opus-4-6"
_ACTIONABLE = {"implement", "custom"}


def _load_prompt(filename: str) -> str:
    return (_PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _check_relevance(
    source_code: str,
    issue: dict[str, Any],
    client: anthropic.Anthropic,
) -> tuple[str, str]:
    """Return (verdict, explanation). verdict is one of: applicable, impossible, no_longer_relevant."""
    system_prompt = _load_prompt("relevance_check_prompt.md")
    user_content = f"{source_code}\n\n---ISSUE---\n{json.dumps(issue, indent=2)}"
    response = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    first_line = raw.splitlines()[0].strip()
    explanation = "\n".join(raw.splitlines()[1:]).strip()
    return first_line, explanation


def _apply_fix(
    source_code: str,
    issue: dict[str, Any],
    client: anthropic.Anthropic,
) -> str:
    """Apply the fix described in the issue and return the new file content."""
    system_prompt = _load_prompt("rewriter_prompt.md")
    user_content = f"{source_code}\n\n---ISSUE---\n{json.dumps(issue, indent=2)}"
    response = client.messages.create(
        model=_MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


def _save_decisions(decisions: list[dict[str, Any]], decisions_path: Path) -> None:
    decisions_path.write_text(json.dumps(decisions, indent=2), encoding="utf-8")


def run(source_path: Path, decisions_path: Path) -> None:
    """Apply all approved fixes from *decisions_path* to *source_path*."""
    decisions = json.loads(decisions_path.read_text(encoding="utf-8"))
    client = anthropic.Anthropic()

    actionable = [d for d in decisions if d["action"] in _ACTIONABLE]
    total = len(actionable)
    applied = 0

    for decision in actionable:
        source_code = source_path.read_text(encoding="utf-8")
        verdict, explanation = _check_relevance(source_code, decision, client)

        if verdict in ("impossible", "no_longer_relevant"):
            decision["status"] = verdict
            decision["explanation"] = explanation
            _save_decisions(decisions, decisions_path)
            print(f"Skipped ({verdict}): {decision['fingerprint']}")
            continue

        # verdict == "applicable"
        new_source = _apply_fix(source_code, decision, client)
        source_path.write_text(new_source, encoding="utf-8")
        decision["status"] = "done"
        _save_decisions(decisions, decisions_path)
        applied += 1
        print(f"Applied fix {applied}/{total}: {decision['fingerprint']}")
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
pytest tests/code_quality_loop/test_rewriter.py -v
```

Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/code_quality_loop/rewriter.py tests/code_quality_loop/test_rewriter.py
git commit -m "feat: implement rewriter module (phase 3)"
```

---

## Task 5: Orchestrator

**Files:**

- Create: `scripts/code_quality_loop/code_quality_loop.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/code_quality_loop/test_critic.py` (append at the end of the file):

```python
# ── orchestrator smoke test ───────────────────────────────────────────────────

def test_orchestrator_calls_all_phases(tmp_path: Path) -> None:
    """The orchestrator imports critic, senior_se, rewriter and calls run() on each."""
    import importlib, types, sys as _sys

    # Stub all three modules before importing the orchestrator
    for name in ("critic", "senior_se", "rewriter"):
        mod = types.ModuleType(name)
        mod.run = MagicMock(return_value=tmp_path / f"stub.{name}.json")  # type: ignore[attr-defined]
        _sys.modules[name] = mod

    # Remove cached orchestrator if present
    _sys.modules.pop("code_quality_loop", None)
    orch_path = Path(__file__).resolve().parents[2] / "scripts" / "code_quality_loop"
    _sys.path.insert(0, str(orch_path))

    import code_quality_loop
    source = tmp_path / "sample.py"
    code_quality_loop.main(source)

    _sys.modules["critic"].run.assert_called_once_with(source)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/code_quality_loop/test_critic.py::test_orchestrator_calls_all_phases -v
```

Expected: FAIL with `ImportError` or `AttributeError: module has no attribute 'main'`

- [ ] **Step 3: Implement `code_quality_loop.py`**

Create `scripts/code_quality_loop/code_quality_loop.py`:

```python
"""Code Quality Loop — Orchestrator.

Usage:
    python scripts/code_quality_loop/code_quality_loop.py <path/to/file.py>
"""
from __future__ import annotations

import sys
from pathlib import Path

import critic
import senior_se
import rewriter


def main(source_path: Path) -> None:
    issues_path = critic.run(source_path)
    decisions_path = senior_se.run(issues_path)
    rewriter.run(source_path, decisions_path)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
```

- [ ] **Step 4: Run all tests**

```bash
pytest tests/code_quality_loop/ -v
```

Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add scripts/code_quality_loop/code_quality_loop.py
git commit -m "feat: add orchestrator — code_quality_loop.py"
```

---

## Task 6: Smoke test with a real file

Verify the full pipeline works end-to-end against a real Python file before
declaring the feature complete.

- [ ] **Step 1: Run the pipeline on the sandbox file**

```bash
python scripts/code_quality_loop/code_quality_loop.py docs/todo/code_quality.py
```

This requires `ANTHROPIC_API_KEY` to be set. Walk through the senior SE approval
prompts. After completion, verify:

- `docs/todo/code_quality.issues.json` exists and contains valid JSON
- `docs/todo/code_quality.decisions.json` exists and reflects your choices
- The source file reflects any applied fixes

- [ ] **Step 2: Commit final state**

```bash
git add scripts/code_quality_loop/
git commit -m "feat: code quality loop — complete implementation"
```
