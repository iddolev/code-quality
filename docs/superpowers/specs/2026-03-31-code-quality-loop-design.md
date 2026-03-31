---
title: Code Quality Loop
date: 2026-03-31
status: approved
---

# Code Quality Loop

A three-phase pipeline that reviews a Python file, gets human approval on each
suggested fix, and applies approved fixes one at a time.

## Overview

```
python scripts/code_quality_loop/code_quality_loop.py myfile.py
```

Produces two JSON artifact files alongside the source:

- `myfile.issues.json` — raw critic output
- `myfile.decisions.json` — issues with human decisions and final status

---

## File Structure

```
scripts/code_quality_loop/
├── code_quality_loop.py       # orchestrator: runs critic → senior_se → rewriter
├── critic.py                  # phase 1 module
├── senior_se.py               # phase 2 module
├── rewriter.py                # phase 3 module
├── critic_prompt.md           # system prompt for critic
├── senior_se_prompt.md        # system prompt for "something else" interpretation
├── relevance_check_prompt.md  # system prompt for relevance check
└── rewriter_prompt.md         # system prompt for rewriter
```

---

## Phase 1 — Critic (`critic.py`)

**Input:** `myfile.py`
**Output:** `myfile.issues.json`

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

**Input:** `myfile.issues.json`
**Output:** `myfile.decisions.json`

For each issue, display to the terminal:

```
─────────────────────────────────────────────
Issue 3/7  [HIGH]
Location:  calculate_average (lines 12-18)
Fingerprint: division by zero risk in calculate_average

Description: No check for empty input — crashes with ZeroDivisionError.

Fix: Add `if not values: return 0.0` before the division.
─────────────────────────────────────────────
  1) Do it
  2) Don't do it
  3) Skip for now
  4) Something else
>
```

User selections map to `action` values:

| Choice | `action` value |
|--------|---------------|
| 1 | `implement` |
| 2 | `no` |
| 3 | `skip_for_now` |
| 4 | `custom` |

**Option 4 — "Something else":** The user types free text. That text is sent to
Claude with `senior_se_prompt.md` as system prompt, along with the original issue.
Claude interprets the intent and returns an updated issue object — it may modify the
`fix` field, replace the description, add a `user_note`, or make any other
reasonable adjustment. The result is written to the decisions file with
`"action": "custom"`.

The decisions file is the issues array with `action` (and any Claude-added fields)
appended to each object.

---

## Phase 3 — Rewriter (`rewriter.py`)

**Input:** `myfile.py`, `myfile.decisions.json`
**Output:** `myfile.py` (overwritten in place after each fix)

Process only issues with `action=implement` or `action=custom`, in order.

For each such issue:

### Step 1 — Relevance check

Read the current state of `myfile.py`. Call Claude with
`relevance_check_prompt.md` as system prompt, passing the current file and the
issue. Claude returns one of:

- `applicable` — proceed to apply the fix
- `impossible` — the fix cannot be applied (e.g. the relevant function was
  restructured by a prior fix)
- `no_longer_relevant` — the issue was made moot by a prior fix

For `impossible` or `no_longer_relevant`, update the issue in
`myfile.decisions.json` with:

```json
{
  "status": "impossible",
  "explanation": "The calculate_average function was refactored in a prior fix..."
}
```

Print a notice and move to the next issue.

### Step 2 — Apply fix

Call Claude with `rewriter_prompt.md` as system prompt, passing the current file
and the issue. The prompt instructs Claude to:

- Apply **only** the described fix, nothing else
- Preserve all formatting, comments, and unrelated code exactly
- Return the **complete rewritten file** with no markdown fences or explanation

Overwrite `myfile.py` with the result. Update the issue in
`myfile.decisions.json` with `"status": "done"`. Print:

```
Applied fix 3/5: division by zero risk in calculate_average
```

### Final status values in decisions JSON

| `status` | Meaning |
|----------|---------|
| `done` | Fix was applied successfully |
| `impossible` | Could not apply after prior fixes |
| `no_longer_relevant` | Made moot by prior fixes |
| `no` | User chose not to do it |
| `skip_for_now` | User deferred |

---

## Orchestrator (`code_quality_loop.py`)

Thin entry point:

```
python scripts/code_quality_loop/code_quality_loop.py myfile.py
```

1. Calls `critic.py` → produces `myfile.issues.json`
2. Calls `senior_se.py` → produces `myfile.decisions.json`
3. Calls `rewriter.py` → applies fixes, updates `myfile.decisions.json`
