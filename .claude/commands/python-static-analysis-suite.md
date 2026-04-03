---
description: "Run python code quality tool suite on file or folder"
argument-hint: <file or folder path>
---

# Code Quality Review

Run code quality checks on the python file or folder `$ARGUMENTS`.

## Run instructions

If `$ARGUMENTS` is empty, issue an error message and STOP.

If the folder `tmp/python_static_analysis_suite` does not exist, create it.

Let timestamp = the current date and time in format YYYYMMDDhhmmss.
Let raw_output_path = tmp/python_static_analysis_suite/<filename>_<timestamp>.raw.log.
Let output_path = tmp/python_static_analysis_suite/<filename>_<timestamp>.log.

Run .claude/scripts/python_static_analysis_suite.py and give it two input parameters:`$ARGUMENTS` and raw_output_path.
Read the output and convert to the following format in output_path:

## Output format

### 1. Summary

- Total findings by severity: Error / Warning / Suggestion
- Total findings by category: (e.g. naming, comments, formatting, design, encapsulation, etc.)

### 2. Findings (sorted by line number)

For each finding:
```
Line {N}: [{CATEGORY}] {SEVERITY} — {description}
  Current: {what the code looks like now}
  Suggested: {what it should look like}
  Tool: {which tool this comes from} 
  Rule: {which tool guideline this comes from}
  Auto-fixable: Yes/No -- see instructions below
```

Auto-fixable should be "Yes" on these issues, (and "No" otherwise)

- Comment placement moves
- Adding missing docstrings and comments
- Method reordering within classes
- Line split / formatting fixes, e.g.: C0301 (line-too-long)
- C0103 (invalid-name)
- C0411 (wrong-import-order)
- W0611 (unused-import)
- W0612 (unused-variable)
- W1309 (f-string-without-interpolation)
- Adding missing `else: raise NotImplementedError(...)` (simple cases only)

### 3. Auto-fixable changes

List only the changes that are marked as "Auto-fixable: Yes".

### 4. Manual approval changes

List all the other items not included in section 3.

## Ignore unwanted items

Now that you wrote to the log file, 
do a final pass on the log file, and remove from it:

- Any item that has PEP 257 / D102 on a private function
- Any item of PEP 257 / D103 on the `main()` function.
- Any item of PEP 257 / D401 on a boolean function.
- Any item of pylint R0903 (too-few-public-methods)        (produces too many false positives)
- Any item of pylint C0116 (missing-function-docstring)    (produces too many false positives)
- Any item of pylint R0902 (too-many-instance-attributes)  (produces too many false positives)
- Any item of pyright [TYPE SAFETY] "Error — Cannot access attribute "text" on non-TextBlock content types"  (because the intended behavior is raising exception when returned content is not a TextBlock)

## Do the fixes

1. Use AskUserQuestion to ask the user whether to apply the safe fixes (from section 3), and act accordingly.
2. [TBD: Don't do this yet, skip. 
   For each item in section 4, a suggested edit should be proposed, showing the diff to the user 
   and using AskUserQuestion to ask the user whether to apply it, and act accordingly, 
   but this must be done in tandem with first creating comprehensive tests that are specific to verifying 
   that the change to the code doesn't change anything semantically. 
   Without such testing we cannot be sure the change is correct.
   Especially for complex changes]

## CRITICAL SAFETY RULE

CRITICAL: The guidelines instruct about cosmetic/structural changes only! 
You MUST ALWAYS preserve the exact semantic behavior of the original code. 
If a modification requires changing logic, control flow, 
return values, side effects, error handling behavior, or API contracts - 
don't actually do it but instead list it as a SUGGESTION and not as an auto-fix.
When in doubt, leave the code unchanged, and ask the user.
