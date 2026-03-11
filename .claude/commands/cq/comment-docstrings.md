---
description: "Check docstring presence and format (PEP 257 / Google style)"
argument-hint: <python-filepath>
---

Run Ruff's pydocstyle rules and report missing or malformed docstrings.

## Steps

1. Run:
   ```
   ruff check --ignore D401 --select D --output-format concise $ARGUMENTS
   ```
2. If ruff is not installed, install it: `pip install ruff --break-system-packages`
3. Summarize: which functions/classes/modules are missing docstrings,
   and which have formatting issues.
4. Ignore a comment PEP 257 / D103 on the main() function.
5. Do NOT auto-generate docstrings. Only report what's missing.
