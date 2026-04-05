---
description: "Apply visual flow guidelines to improve code structure and readability"
argument-hint: "<file-or-folder (optional)>"
---

- If `$ARGUMENTS` is empty, consider it as if it was '.'
- If `$ARGUMENTS` contains `--full`, add `--full` to the script invocation and remove it from the target path.
- If the target is a single file, run the script on it directly:

```bash
python .claude/code-quality/scripts/visual_flow/visual_flow_applier.py guidelines/visual_flow.md <file> [--full]
```

- If the target is a folder, first list all code files in it, then run the script on **each file separately** so you can
  report progress between files. Use `find` or glob to collect files with code extensions (.py, .js, .ts, .tsx, .jsx,
  .java, .kt, .go, .rs, .rb, .c, .cpp, .h, .hpp, .cs, .swift, .scala, .sh, .bash).

- **Before** running the script on each file, tell the user which file is being processed.
- **After** each file completes, show the user the output file path and log file path from the script's stdout.
