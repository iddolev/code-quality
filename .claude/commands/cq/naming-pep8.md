---
description: "Check PEP 8 naming conventions (snake_case, PascalCase, etc.)"
argument-hint: <python-filepath>
---

Run Ruff's pep8-naming rules on the file and report violations.

## Steps

1. Run:
   ```
   ruff check --select N --output-format concise $ARGUMENTS
   ```
2. If ruff is not installed, install it: `pip install ruff --break-system-packages`
3. Report each violation with the line number and what the correct name should be.
4. Do NOT auto-fix. Only report findings.
