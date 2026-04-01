---
author: Iddo Lev
last_updated: 2026-03-11
description: Install ruff and pylint for code quality linting and formatting
---

For each <program> of: ruff, pylint, pyright, vulture, radon, bandit, deptry, pip-audit: 
check if <program> is already installed by running:

```
<program> --version
```

- If <program> is found (the command succeeds), 
  report the installed version to the user and tell them <program> is already installed. 
  Do NOT reinstall it.
- If <program> is not found (the command fails), install it using pip:

```
pip install <program> --break-system-packages
```

Then verify the installation by running `<program> --version` and report the installed version to the user.
