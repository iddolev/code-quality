---
name: code-quality
description: Run a comprehensive code quality review on a Python file
argument-hint: <python-filepath>
---

# Code Quality Review

Run ALL code quality checks on the file `$ARGUMENTS`.

First, verify `$ARGUMENTS` exists and is a filepath <python-filepath> to a python file. 
If it's not, issue an error message and STOP execution.

## Strategy

Run checks in three tiers. 
Checks cannot be run in parallel because they can modify the file, and we don't want race conditions.

### Tier 1 — Deterministic tool checks

Run each of these tool commands and collect their output:

1. `/cq:naming-pep8 $ARGUMENTS`
2. `/cq:comment-docstrings $ARGUMENTS`
3. `/cq:comment-todo-format $ARGUMENTS`
4. `/cq:visual-line-length $ARGUMENTS`
5. `/cq:visual-complexity $ARGUMENTS`
6. `/cq:func-param-count $ARGUMENTS`

[TBD: add more]

### Tier 2 — Deterministic script checks (run all in parallel)

[TBD: fill]

### Tier 3 — LLM-assisted review (run after reading the file)

[TBD: fill]

## Output format

Whenever you are invoked:
1. If the folder tmp/quality_review does not exist, create it.
2. Obtain the current date and time.
3. Produce a new structured report in tmp/quality_review/<python-filename>_<current date and time as YYYYMMDDhhmm>.log.
The report should have these sections:

### 1. Summary

- Total findings by severity: Error / Warning / Suggestion
- Total findings by category: Naming / Comments / Formatting / Design / DRY / Encapsulation

### 2. Findings (sorted by line number)

For each finding:
```
Line {N}: [{CATEGORY}] {SEVERITY} — {description}
  Current: {what the code looks like now}
  Suggested: {what it should look like}
  Rule: {which guideline this comes from}
  Auto-fixable: Yes/No
```

### 3. Auto-fixable changes

List only the changes that are marked as "Auto-fixable: Yes" and that are SAFE to apply automatically:

- Comment placement moves
- Method reordering within classes
- Line split / formatting fixes
- Adding missing `else: raise NotImplementedError(...)` (simple cases only)

### 4. Manual approval changes

List the changes that are marked as "Auto-fixable: No".

## Ignore unwanted items

Do a final pass on the log file you created, and remove from it:

- Any item that has PEP 257 / D102 on a private function
- Any item of PEP 257 / D103 on the `main()` function.
- Any item of PEP 257 / D401 on a boolean function.

## Do the fixes

1. Use AskUserQuestion to ask the user whether to apply the safe fixes (from section 3), and act accordingly.
2. [TBD: Don't do this yet, skip. 
   For each item in section 4, a suggested edit should be proposed, showing the diff to the user 
   and using AskUserQuestion to ask the user whether to apply it, and act accordingly, 
   but this must be done in tandem with first creating comprehensive tests that are specific to verifying 
   that the change to the code doesn't change anything semantically. 
   Without such testing we cannot be sure the change is correct.
   Especially for complex changes 
   e.g. instead of a function that loops with a state, 
   defining a class with a state that avoids "message passing" of the state into an update function
   (e.g. relevant for format_markdown.md function fix_heading_and_list_spacing)]

## CRITICAL SAFETY RULE

CRITICAL: The guidelines instruct about cosmetic/structural changes only! 
You MUST ALWAYS preserve the exact semantic behavior of the original code. 
If applying a guideline would require changing logic, control flow, 
return values, side effects, error handling behavior, or API contracts - 
don't actually do it but instead list it as a SUGGESTION and not as an auto-fix.
When in doubt, leave the code unchanged, and ask the user.
