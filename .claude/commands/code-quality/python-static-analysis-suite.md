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

If the user chooses (or `$ARGUMENTS` is) `all`, use `.` (the repo root) as the
target path. The suite script handles folder traversal internally, excluding
`sandbox/`, `venv/`, `tmp/`, `__pycache__/`, and `.git/`.

If the folder `tmp/python_static_analysis_suite` does not exist, create it.

Let timestamp = the current date and time in format YYYYMMDD_hhmmss.
Let target_name = the basename of the target (filename without extension, or
folder name; use `all` when the target is `.`).
Let raw_output_path = tmp/python_static_analysis_suite/<target_name>_<timestamp>.raw.log.
Let jsonl_path = tmp/python_static_analysis_suite/<target_name>_<timestamp>.jsonl.
Let output_path = tmp/python_static_analysis_suite/<target_name>_<timestamp>.log.

### Step 1: Run the tools

Run `python_static_analysis_suite.py` with two parameters: the target path and
raw_output_path. The script accepts a single file or a folder — invoke it once.

### Step 2: Parse the raw output

Run `python_static_analysis_parse_log.py` with two parameters: raw_output_path and jsonl_path.

### Step 3: Filter and format the report

Run `python_static_analysis_report.py` with two parameters: jsonl_path and output_path.

This filters out ignored findings and writes a formatted report with these sections:

1. Summary (counts by severity and category)
2. All findings (sorted by file, then line)
3. Auto-fixable changes
4. Manual review changes
5. Unparsed tool output (if any — check the raw log for details)
6. Uncategorized rules (if any — see below)

Rule configuration (ignore, auto_fixable, category) is in
`.claude/code-quality/scripts/python_static_analysis/python_static_analysis_report.yaml`.

### Step 4: Handle uncategorized rules

If the report contains section 6 (uncategorized rules), for each listed rule:

1. Read the rule's description from the report
2. Decide the appropriate category, and whether it should be ignored or auto-fixable
3. Add it to `python_static_analysis_report.yaml`
4. Re-run step 3 to regenerate the report with updated categories

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
