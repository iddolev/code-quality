---
description: "Apply visual flow guidelines to improve code structure and readability"
argument-hint: "<file-or-folder (optional)> or 'all' for all code files"
---

- If `$ARGUMENTS` is empty, ask the user what they want to run on:
  - A specific file path
  - A specific folder path
  - All code files in the repository

- If the user chooses (or `$ARGUMENTS` is) `all`, run on every code file in the
  repository, excluding files inside `sandbox/` and files excluded by `.gitignore`.
  To collect the file list, run:

  ```bash
  git ls-files
  ```

  Then filter to code extensions (.py, .js, .ts, .tsx, .jsx, .java, .kt, .go,
  .rs, .rb, .c, .cpp, .h, .hpp, .cs, .swift, .scala, .sh, .bash) and filter out
  any paths that start with `sandbox/`. Process each file one at a time.
- If `$ARGUMENTS` contains `--full`, add `--full` to the script invocation and remove it from the target path.
- If the target is a single file, run the script on it directly:

```bash
python .claude/code-quality/scripts/visual_flow/visual_flow_applier.py .claude/code-quality/guidelines/visual_flow.md <file> [--full]
```

- If the target is a folder, first list all code files in it, then run the script on **each file separately** so you can
  report progress between files. Use `find` or glob to collect files with code extensions (.py, .js, .ts, .tsx, .jsx,
  .java, .kt, .go, .rs, .rb, .c, .cpp, .h, .hpp, .cs, .swift, .scala, .sh, .bash).

- **Before** running the script on each file, tell the user which file is being processed.
- **After** each file completes, show the user the output file path and log file path from the script's stdout.
