---
description: "Apply visual flow guidelines to improve code structure and readability"
argument-hint: "<file-or-folder (optional)>"
---

# Visual Flow

Apply the visual flow guidelines from @guidelines/visual_flow.md on code files.

## Determine target files

- If `$ARGUMENTS` is not empty and points to a single file, apply the guidelines on that file.
- If `$ARGUMENTS` is not empty and points to a folder, apply the guidelines on all code files in that folder (recursively).
- If `$ARGUMENTS` is empty, apply the guidelines on all code files in the repository (recursively), excluding hidden directories (e.g. `.git`, `.claude`), `node_modules`, `venv`, `__pycache__`, and other common non-source directories.

"Code files" means files with extensions like `.py`, `.js`, `.ts`, `.java`, `.go`, `.rs`, `.cpp`, `.c`, `.cs`, `.rb`, `.kt`, `.swift`, etc. Exclude config files, data files, documentation, and generated files.

## Read the guidelines

Read the file @guidelines/visual_flow.md to load all the visual flow rules.

## Apply guidelines in parallel

Use the Agent tool to process files in parallel. For each target file, spawn a separate agent with the following prompt (filling in the file path):

> Apply the visual flow guidelines on the file `<filepath>`.
>
> Read `guidelines/visual_flow.md` to load the rules, then read the target file and fix any violations.
>
> After applying fixes, report what you changed (one line per fix). If no violations were found, report that the file is already compliant.

Send all Agent tool calls in a single message so they run in parallel. Once all agents complete, summarize the results to the user.
