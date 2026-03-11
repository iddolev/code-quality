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


[TBD: add more]

### Tier 2 — Deterministic script checks (run all in parallel)

[TBD: fill]

### Tier 3 — LLM-assisted review (run after reading the file)

[TBD: fill]

## Output format

Whenever you are invoked:
1. Obtain the current date and time
2. Produce a new structured report in tmp/quality_review/<python-filename>_<current date and time as YYYYMMDDhhmm>.log.
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

[TBD]

## CRITICAL SAFETY RULE

CRITICAL: The guidelines instruct about cosmetic/structural changes only! 
You MUST preserve the exact semantic behavior of the original code. 
If applying a guideline would require changing logic, control flow, 
return values, side effects, error handling behavior, or API contracts - 
don't actually do it but instead list it as a SUGGESTION and not as an auto-fix.
When in doubt, leave the code unchanged, and ask the user.
