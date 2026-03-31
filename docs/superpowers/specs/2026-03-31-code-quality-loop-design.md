---
title: Code Quality Loop
date: 2026-03-31
status: approved
---

# Code Quality Loop

A three-phase pipeline that reviews a Python file, has a senior SE LLM triage
each issue autonomously, consults the human only for unclear or complex cases,
and applies approved fixes one at a time.

## Overview

```
python scripts/code_quality_loop/code_quality_loop.py myfile.py
```

Produces two JSON artifact files in the **same directory as the input file**,
regardless of where the script is run from:

- `myfile.issues.json` — raw critic output
- `myfile.decisions.json` — issues with decisions and final status

---

## File Structure

```
scripts/code_quality_loop/
├── code_quality_loop.py           # orchestrator: runs critic → senior_se → rewriter
├── critic.py                      # phase 1 module
├── senior_se.py                   # phase 2 module
├── rewriter.py                    # phase 3 module
├── critic_prompt.md               # system prompt for critic
├── senior_se_triage_prompt.md     # system prompt for senior SE autonomous triage
├── senior_se_custom_prompt.md     # system prompt for option 4 "something else" LLM call
├── relevance_check_prompt.md      # system prompt for relevance check
└── rewriter_prompt.md             # system prompt for rewriter
```

Each module exposes a single entry-point function called by the orchestrator:

```python
# critic.py
def run(source_path: Path) -> Path: ...       # returns path to issues JSON

# senior_se.py
def run(issues_path: Path) -> Path: ...       # returns path to decisions JSON

# rewriter.py
def run(source_path: Path, decisions_path: Path) -> None: ...
```

---

## Phase 1 — Critic (`critic.py`)

**Input:** path to `myfile.py`
**Output:** `myfile.issues.json` (written to same directory as input)

1. Read the source file.
2. Call Claude with `critic_prompt.md` as system prompt and the file content as user message.
3. Parse the returned JSON array and write it to `myfile.issues.json`.

Each issue object (defined by `critic_prompt.md`):

```json
{
  "fingerprint": "division by zero risk in calculate_average",
  "severity":    "HIGH",
  "location":    "calculate_average (lines 12-18)",
  "description": "No check for empty input — crashes with ZeroDivisionError.",
  "fix":         "Add `if not values: return 0.0` before the division."
}
```

---

## Phase 2 — Senior SE (`senior_se.py`)

**Input:** path to `myfile.issues.json`
**Output:** `myfile.decisions.json` (written to same directory as input)

Phase 2 has two steps: autonomous LLM triage, then human consultation only for
escalated issues.

### Step 1 — Autonomous triage

Send all issues to Claude with `senior_se_triage_prompt.md` as system prompt.
The LLM acts as a senior software engineer and labels each issue with one of:

| Triage label | Meaning |
|---|---|
| `implement` | Fix is clear, essential, and safe to apply without human review |
| `no` | Fix should not be done (wrong, unnecessary, or harmful) |
| `needs_human_approval` | Fix is complex, ambiguous, or has trade-offs requiring human judgement |

The LLM returns a JSON array, one entry per issue, with:
- `fingerprint` — to match back to the original issue
- `triage` — one of the three labels above
- `senior_se_reasoning` — brief explanation of the decision

### Step 2 — Human consultation (escalated issues only)

For each issue labelled `needs_human_approval`, display to the terminal:

```
─────────────────────────────────────────────
Issue 3/7  [HIGH]  ⚠ Needs your input
Location:  calculate_average (lines 12-18)
Fingerprint: division by zero risk in calculate_average

Description: No check for empty input — crashes with ZeroDivisionError.

Fix: Add `if not values: return 0.0` before the division.

Senior SE note: Unclear whether silent default or exception is preferred here.
─────────────────────────────────────────────
  1) Do it
  2) Don't do it
  3) Skip for now
  4) Something else
>
```

Human choices map to `action` values:

| Choice | `action` value |
|--------|---------------|
| 1 | `implement` |
| 2 | `no` |
| 3 | `skip_for_now` |
| 4 | `custom` |

**Option 4 — "Something else":** The user types free text. That text plus the
original issue are sent to Claude with `senior_se_custom_prompt.md` as system
prompt. Claude interprets the intent and returns an updated issue object — it may
modify the `fix` field, replace the description, add a `user_note`, or make any
other reasonable adjustment. The `fix` field on the returned object is always
authoritative for what the rewriter will implement.

### Write timing

The decisions file is written (or overwritten) after **each** individual
decision (triage or human), so progress is preserved if the process is
interrupted.

### Decisions JSON record fields

Every record in `myfile.decisions.json` contains all original critic fields plus:

| Field | Set by | Values |
|---|---|---|
| `action` | Phase 2 | `implement`, `no`, `skip_for_now`, `custom` |
| `decision_by` | Phase 2 | `senior_se`, `human` |
| `senior_se_reasoning` | Phase 2 | Brief explanation from triage LLM |
| `status` | Phase 2 (initial) / Phase 3 (updates) | See status table below |
| `user_note` | Phase 2, option 4 only | Free text captured from human |

Phase 2 always writes `"status": "pending"` as the initial value. The rewriter
updates this field as it processes issues.

**Example — senior SE decides autonomously:**

```json
{
  "fingerprint":         "division by zero risk in calculate_average",
  "severity":            "HIGH",
  "location":            "calculate_average (lines 12-18)",
  "description":         "No check for empty input — crashes with ZeroDivisionError.",
  "fix":                 "Add `if not values: return 0.0` before the division.",
  "action":              "implement",
  "decision_by":         "senior_se",
  "senior_se_reasoning": "Straightforward guard clause, clearly correct, no trade-offs.",
  "status":              "pending"
}
```

**Example — escalated to human, human picks option 1:**

```json
{
  "fingerprint":         "division by zero risk in calculate_average",
  "severity":            "HIGH",
  "location":            "calculate_average (lines 12-18)",
  "description":         "No check for empty input — crashes with ZeroDivisionError.",
  "fix":                 "Add `if not values: return 0.0` before the division.",
  "action":              "implement",
  "decision_by":         "human",
  "senior_se_reasoning": "Unclear whether silent default or exception is preferred here.",
  "status":              "pending"
}
```

**Example — escalated to human, human picks option 4 ("something else"):**

```json
{
  "fingerprint":         "division by zero risk in calculate_average",
  "severity":            "HIGH",
  "location":            "calculate_average (lines 12-18)",
  "description":         "No check for empty input — crashes with ZeroDivisionError.",
  "fix":                 "Raise ValueError('values must not be empty') instead of returning 0.0.",
  "action":              "custom",
  "decision_by":         "human",
  "senior_se_reasoning": "Unclear whether silent default or exception is preferred here.",
  "user_note":           "user wants an exception, not a silent default",
  "status":              "pending"
}
```

---

## Phase 3 — Rewriter (`rewriter.py`)

**Input:** path to `myfile.py`, path to `myfile.decisions.json`
**Output:** `myfile.py` (overwritten in place after each fix); `myfile.decisions.json`
updated in place after each issue is processed.

Process only issues with `action=implement` or `action=custom`, in original order.
The fix counter denominator is the **total count of such issues at the start of
Phase 3** (before any relevance checks filter some out). The numerator increments
only when a fix is successfully applied (status becomes `done`); issues that turn
out `impossible` or `no_longer_relevant` do not increment it.

For each such issue:

### Step 1 — Relevance check

Read the current state of `myfile.py`. Call Claude with
`relevance_check_prompt.md` as system prompt, passing the current file and the
issue. Claude returns one of:

- `applicable` — proceed to apply the fix; no write to decisions JSON at this point
  (the issue remains `status=pending` until Step 2 completes)
- `impossible` — the fix cannot be applied (e.g. the relevant function was
  restructured by a prior fix)
- `no_longer_relevant` — the issue was made moot by a prior fix

For `impossible`, update the issue in `myfile.decisions.json` with:

```json
{
  "status":      "impossible",
  "explanation": "The calculate_average function was refactored in a prior fix..."
}
```

For `no_longer_relevant`, update with:

```json
{
  "status":      "no_longer_relevant",
  "explanation": "A prior fix already added the empty-input guard..."
}
```

Print a notice and move to the next issue.

### Step 2 — Apply fix

The rewriter uses the `fix` field of the issue as the authoritative instruction.
Call Claude with `rewriter_prompt.md` as system prompt, passing the current file
and the issue. The prompt instructs Claude to:

- Apply **only** the fix described in the `fix` field, nothing else
- Preserve all formatting, comments, and unrelated code exactly
- Return the **complete rewritten file** with no markdown fences or explanation

Overwrite `myfile.py` with the result. Update the issue in
`myfile.decisions.json` with `"status": "done"`. Print:

```
Applied fix 3/5: division by zero risk in calculate_average
```

### Final status values in decisions JSON

| `status` | Set by | Meaning |
|----------|--------|---------|
| `pending` | Phase 2 | Initial value; not yet processed by rewriter |
| `done` | Phase 3 | Fix was applied successfully |
| `impossible` | Phase 3 | Could not apply after prior fixes |
| `no_longer_relevant` | Phase 3 | Made moot by prior fixes |

Issues with `action=no` or `action=skip_for_now` retain `status=pending` forever.

---

## Orchestrator (`code_quality_loop.py`)

Thin entry point that imports and calls each module's `run()` function:

```
python scripts/code_quality_loop/code_quality_loop.py myfile.py
```

```python
import sys
from pathlib import Path
import critic, senior_se, rewriter

source_path = Path(sys.argv[1])
issues_path = critic.run(source_path)
decisions_path = senior_se.run(issues_path)
rewriter.run(source_path, decisions_path)
```
