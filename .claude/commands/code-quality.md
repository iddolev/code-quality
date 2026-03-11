---
description: "Run python code quality tool suite on file or folder"
argument-hint: <filepath>
---

# Code Quality Review

Run code quality checks on the python file or folder `$ARGUMENTS`.

## Run instructions

If `$ARGUMENTS` is empty, issue an error message and STOP.

If the folder `tmp/quality_review` does not exist, create it.

Let timestamp = the current date and time in format YYYYMMDDhhmm.
Let raw_output_path = tmp/quality_review/<name>_<timestamp>.raw.log.
Let output_path = tmp/quality_review/<name>_<timestamp>.log.

Run .claude/scripts/code-quality.bat and give it two input parameters:`$ARGUMENTS` and raw_output_path.
Read the output and convert to the following format in output_path:

<a id="output-format"/>

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
  Auto-fixable: Yes/No
```

### 3. Auto-fixable changes

List only the changes that are marked as "Auto-fixable: Yes" and that are SAFE to apply automatically:

- Comment placement moves
- Method reordering within classes
- Line split / formatting fixes
- Adding missing `else: raise NotImplementedError(...)` (simple cases only)

### 4. Manual approval changes

List all the other items not included in section 3.

## Ignore unwanted items

Now that you wrote to the log file, 
do a final pass on the log file, and remove from it:

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
