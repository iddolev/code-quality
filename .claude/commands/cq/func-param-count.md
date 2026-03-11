---
description: "Check that functions have ≤3 parameters"
argument-hint: <python-filepath>
---

Run Pylint's too-many-arguments check, configured for max 3.

## Steps

1. Run:
   ```
   pylint --disable=all --enable=R0913 --max-args=3 $ARGUMENTS
   ```
2. If pylint is not installed, install it: `pip install pylint --break-system-packages`
3. Report each function that exceeds the limit, its parameter count, and
   parameter names.
4. For each, suggest which parameters could be grouped into a dataclass,
   but do NOT apply the change.
