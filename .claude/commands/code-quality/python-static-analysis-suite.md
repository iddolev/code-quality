---
description: "Run python code quality tool suite on file or folder"
argument-hint: "<file-or-folder (optional)> or 'all' for all python files"
---

# Code Quality Review

This command will run code quality checks on the python file or folder `$ARGUMENTS`.

## Preparation

First check if all tools are installed by following the instructions in
`.claude/code-quality/scripts/install-static-analysis-tools.md` with `--missing` mode.

If the result is "all installed", proceed to the Run instructions.

If some tools are missing, **tell the user which tools need to be installed** 
and use AskUserQuestion to verify whether they want to:

1. Install the missing tools and then run the suite
2. Install the missing tools without running the suite
3. Skip installation and only run with whatever tools are already installed

If the user chooses to install, follow the install mode instructions in
`.claude/code-quality/scripts/install-static-analysis-tools.md`.

## Run instructions

If `$ARGUMENTS` is empty, ask the user what they want to run on:
- A specific file path
- A specific folder path
- All Python files in the repository

If the user chooses (or `$ARGUMENTS` is) `all`, run on every `.py` file in the
repository, excluding files inside `sandbox/` and files excluded by `.gitignore`.
To collect the file list, run:

```bash
git ls-files '*.py'
```

Then filter out any paths that start with `sandbox/`. Process each file one at a
time, running the full workflow on each before moving to the next.

If the folder `tmp/python_static_analysis_suite` does not exist, create it.

Let timestamp = the current date and time in format YYYYMMDD_hhmmss.
Let raw_output_path = tmp/python_static_analysis_suite/<filename>_<timestamp>.raw.log.
Let jsonl_path = tmp/python_static_analysis_suite/<filename>_<timestamp>.jsonl.
Let output_path = tmp/python_static_analysis_suite/<filename>_<timestamp>.log.

### Step 1: Run the tools

Run `python_static_analysis_suite.py` with two parameters: `$ARGUMENTS` and raw_output_path.

### Step 2: Parse the raw output

Run `python_static_analysis_parse_log.py` with two parameters: raw_output_path and jsonl_path.

This produces a JSON Lines file where each line is one finding with these fields:

- `file`: source file path
- `line`, `col`: location
- `tool`: which tool (ruff, pylint, pyright, bandit, radon, fixit)
- `rule`: tool-specific rule code
- `severity`: error / warning / suggestion
- `description`: human-readable message
- `rule_name`: (pylint only) the rule's kebab-case name
- `ruff_fixable`: (ruff only) true if ruff can auto-fix
- `fixit_autofix`: (fixit only) true if fixit can auto-fix

### Step 3: Filter ignored items

Read the JSONL file and discard findings that match ANY of these ignore rules:

- pylint R0903 (too-few-public-methods) — too many false positives
- pylint C0116 (missing-function-docstring) — too many false positives
- pylint R0902 (too-many-instance-attributes) — too many false positives
- pylint E0401 (import-error) — false positives from relative imports
- pyright reportMissingImports — false positives from relative imports
- pyright reportAttributeAccessIssue where description contains
  `Cannot access attribute "text"` — intentional behavior (raises on non-TextBlock)
- bandit B101 (assert_used) in test files — assert is standard in tests
- bandit B404 (blacklist) for subprocess import — too noisy, low value
- Any finding with rule "unparsed" — parser fallback, not actionable

### Step 4: Write the formatted log

Read the filtered findings and write to output_path in this format:

#### 1. Summary

- Total findings by severity: Error / Warning / Suggestion
- Total findings by category: (e.g. naming, formatting, security, complexity, imports, etc.)

#### 2. Findings (sorted by file, then by line number)

For each finding:
```
Line {N}: [{CATEGORY}] {SEVERITY} — {description}
  Tool: {tool}
  Rule: {rule}
  Auto-fixable: Yes/No
```

A finding is "Auto-fixable: Yes" if ANY of these apply:
- ruff_fixable is true
- fixit_autofix is true
- Rule is one of: C0301 (line-too-long), C0103 (invalid-name), C0411 (wrong-import-order),
  W0611 (unused-import), W0612 (unused-variable), W1309 (f-string-without-interpolation)

All other findings are "Auto-fixable: No".

#### 3. Auto-fixable changes

List only findings marked "Auto-fixable: Yes".

#### 4. Manual review changes

List all other findings.

## Do the fixes

1. Use AskUserQuestion to ask the user whether to apply the safe fixes (from section 3),
   and act accordingly.
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
