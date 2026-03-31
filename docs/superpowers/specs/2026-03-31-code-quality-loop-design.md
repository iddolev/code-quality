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

- `myfile.issues.json` — raw critic output, each issue assigned a unique `id`
- `myfile.decisions.json` — one decision record per issue, referenced by `id`
  only (no repeated content from `issues.json`)

---

## File Structure

```
scripts/code_quality_loop/
├── code_quality_loop.py               # orchestrator: runs critic → senior_se → rewriter
├── critic.py                          # phase 1 module
├── senior_se.py                       # phase 2 module
├── rewriter.py                        # phase 3 module
└── prompts/
    ├── critic_prompt.md               # system prompt for critic
    ├── senior_se_triage_prompt.md     # system prompt for autonomous triage LLM
    ├── senior_se_custom_prompt.md     # system prompt for option 4 "something else" LLM call only
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
2. Call Claude with `prompts/critic_prompt.md` as system prompt and the file
   content as user message.
3. Parse the returned JSON array.
4. Assign a sequential `id` (starting at 1) to each issue object.
5. Write the array to `myfile.issues.json`.

Each issue object:

```json
{
  "id":          1,
  "fingerprint": "division by zero risk in calculate_average",
  "severity":    "HIGH",
  "location":    "calculate_average (lines 12-18)",
  "description": "No check for empty input — crashes with ZeroDivisionError.",
  "fix":         "Add `if not values: return 0.0` before the division."
}
```

The `id` is the sole join key between `issues.json` and `decisions.json`.

---

## Phase 2 — Senior SE (`senior_se.py`)

**Input:** path to `myfile.issues.json`
**Output:** `myfile.decisions.json` (written to same directory as input)

Phase 2 has two steps: autonomous LLM triage, then human consultation only for
escalated issues.

### Step 1 — Autonomous triage

Send all issues to Claude with `prompts/senior_se_triage_prompt.md` as system
prompt. The LLM acts as a senior software engineer and labels each issue with one
of:

| Triage label | Meaning |
|---|---|
| `implement` | Fix is clear, essential, and safe to apply without human review |
| `no` | Fix should not be done (wrong, unnecessary, or harmful) |
| `needs_human_approval` | Fix is complex, ambiguous, or has trade-offs requiring human judgement |

The LLM returns a JSON array, one entry per issue, with:

- `id` — to match back to the original issue
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
original issue are sent to Claude with `prompts/senior_se_custom_prompt.md` as
system prompt. Claude returns a JSON object with only the decision fields:
`action` (always `"custom"`), optionally `custom_fix` (an updated fix instruction
that overrides the issue's `fix` field), and optionally `user_note`. The rewriter
uses `custom_fix` from the decision record if present; otherwise falls back to the
issue's `fix`.

### Write timing

The decisions file is written (or overwritten) after **each** individual decision
(triage or human), so progress is preserved if the process is interrupted.

### Decisions JSON record fields

Every record in `myfile.decisions.json` contains only decision fields — no
repeated content from `issues.json`:

| Field | Set by | Values |
|---|---|---|
| `id` | Phase 2 | Integer matching the issue's `id` |
| `action` | Phase 2 | `implement`, `no`, `skip_for_now`, `custom` |
| `decision_by` | Phase 2 | `senior_se`, `human` |
| `senior_se_reasoning` | Phase 2 | Brief explanation from triage LLM |
| `status` | Phase 2 (initial) / Phase 3 (updates) | See status table |
| `custom_fix` | Phase 2, option 4 only | Updated fix instruction overriding the issue's `fix` |
| `user_note` | Phase 2, option 4 only | Free text summary of human's intent |
| `explanation` | Phase 3 | Set when `status` is `impossible` or `no_longer_relevant` |

Phase 2 always writes `"status": "pending"` as the initial value.

**Example — senior SE decides autonomously:**

```json
{
  "id":                  1,
  "action":              "implement",
  "decision_by":         "senior_se",
  "senior_se_reasoning": "Straightforward guard clause, clearly correct, no trade-offs.",
  "status":              "pending"
}
```

**Example — escalated to human, human picks option 1:**

```json
{
  "id":                  1,
  "action":              "implement",
  "decision_by":         "human",
  "senior_se_reasoning": "Unclear whether silent default or exception is preferred here.",
  "status":              "pending"
}
```

**Example — escalated to human, human picks option 4 ("something else"):**

```json
{
  "id":                  1,
  "action":              "custom",
  "decision_by":         "human",
  "senior_se_reasoning": "Unclear whether silent default or exception is preferred here.",
  "custom_fix":          "Raise ValueError('values must not be empty') instead of returning 0.0.",
  "user_note":           "user wants an exception, not a silent default",
  "status":              "pending"
}
```

---

## Phase 3 — Rewriter (`rewriter.py`)

**Input:** path to `myfile.py`, path to `myfile.decisions.json`
**Output:** `myfile.py` (overwritten in place after each fix); `myfile.decisions.json`
updated in place after each issue is processed.

On startup, the rewriter loads both `myfile.issues.json` (derived from the
decisions path) and `myfile.decisions.json`, and joins them by `id` to build a
combined working set.

Process only decisions with `action=implement` or `action=custom`, in original
order. The fix counter denominator is the **total count of such decisions at the
start of Phase 3** (before any relevance checks filter some out). The numerator
increments only when a fix is successfully applied (status becomes `done`); issues
that turn out `impossible` or `no_longer_relevant` do not increment it.

**Fix instruction:** For `action=implement`, use the `fix` field from `issues.json`.
For `action=custom`, use `custom_fix` from the decision record (which overrides the
issue's `fix`).

For each actionable decision:

### Step 1 — Relevance check

Read the current state of `myfile.py`. Call Claude with
`prompts/relevance_check_prompt.md` as system prompt, passing the current file and
the full issue (from `issues.json`). Claude returns one of:

- `applicable` — proceed to apply the fix; no write to decisions JSON at this point
  (the decision remains `status=pending` until Step 2 completes)
- `impossible` — the fix cannot be applied (e.g. the relevant function was
  restructured by a prior fix)
- `no_longer_relevant` — the issue was made moot by a prior fix

For `impossible`, update the decision in `myfile.decisions.json` with:

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

Print a notice and move to the next decision.

### Step 2 — Apply fix

Call Claude with `prompts/rewriter_prompt.md` as system prompt, passing the
current file and the effective fix instruction. The prompt instructs Claude to:

- Apply **only** the described fix, nothing else
- Preserve all formatting, comments, and unrelated code exactly
- Return the **complete rewritten file** with no markdown fences or explanation

Overwrite `myfile.py` with the result. Update the decision in
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

Decisions with `action=no` or `action=skip_for_now` retain `status=pending` forever.

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
