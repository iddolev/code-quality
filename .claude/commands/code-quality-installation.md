---
author: Iddo Lev
last_updated: 2026-03-11
description: Install ruff for code quality linting and formatting
---

First, check if ruff is already installed by running:

```
ruff --version
```

- If ruff is found (the command succeeds), report the installed version to the user and tell them ruff is already installed. 
  Do NOT reinstall it.
- If ruff is not found (the command fails), install it using pip:

```
pip install ruff
```

Then verify the installation by running `ruff --version` and report the installed version to the user.
