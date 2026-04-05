---
description: "Apply visual flow guidelines to improve code structure and readability"
argument-hint: "<file-or-folder (optional)>"
---

# Visual Flow

Apply the visual flow guidelines from @.claude/code-quality/guidelines/visual_flow.md on code files.

## Determine target files

- If `$ARGUMENTS` is not empty and points to a single file, apply the guidelines on that file.
- If `$ARGUMENTS` is not empty and points to a folder, apply the guidelines on all code files in that folder (recursively).
- If `$ARGUMENTS` is empty, apply the guidelines on all code files in the repository (recursively), excluding hidden directories (e.g. `.git`, `.claude`), `node_modules`, `venv`, `__pycache__`, and other common non-source directories.

"Code files" means files with extensions like `.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`, `.cpp`, `.c`, `.cs`, `.rb`, `.kt`, `.swift`, etc. Exclude config files, data files, documentation, and generated files.

## Read the guidelines

Read the file @.claude/code-quality/guidelines/visual_flow.md to load all the visual flow rules.

## Apply guidelines in parallel

Use the Agent tool to process files in parallel. For each target file, determine the log path as `/temp/<relative_filepath>.vf.jsonl` (e.g. for `scripts/foo.py` the log is `/temp/scripts/foo.py.vf.jsonl`). Spawn a separate agent with the following prompt (filling in `<filepath>` and `<log_path>`):

> Apply the visual flow guidelines on the file `<filepath>`.
>
> Read `.claude/code-quality/guidelines/visual_flow.md` to load the rules, then read the target file and fix any violations.
>
> **Logging:** After applying each fix, immediately append one JSON line to `<log_path>` (create parent directories if needed with `mkdir -p`).
> Each line must be a JSON object with these fields:
> - `"file"`: the relative path of the file (e.g. `"scripts/foo.py"`)
> - `"rule"`: the rule identifier, formatted as `"visual flow #N"` where N is the rule's position in the Table of Contents of `.claude/code-quality/guidelines/visual_flow.md` (1-indexed).
> - `"location"`: the name of the smallest enclosing scope around the change — a method, function, or class name (e.g. `"MyClass._process_item"` or `"load_config"`). If the change is at module/file level (not inside any function or class), use `"(module)"`.
> - `"description"`: a short (one-line) description of what was changed
>
> Use the Bash tool to append each line: `echo '<json>' >> <log_path>`.
>
> After applying fixes, report that a log of changes was written to `<log_path>`, 
> and do NOT output any summary (because the log is enough).
> If no violations were found, report that the file is already compliant (and write nothing to the log).

Send all Agent tool calls in a single message so they run in parallel. Once all agents complete, summarize the results to the user.
