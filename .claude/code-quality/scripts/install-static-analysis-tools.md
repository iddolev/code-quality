# Install Static Analysis Tools

Install the following code quality tools: ruff, pylint, pyright, vulture, radon, bandit, deptry, pip-audit.

## Check mode (`--missing`)

If invoked with `--missing`, only check which tools are missing and report:

For each tool, run:

```bash
<tool> --version
```

If the command fails or the tool is not found, it is missing.

- If all tools are installed, print: `all installed`
- If some are missing, print: `need installation: <comma-separated list of missing tools>`

Then stop — do not install anything.

## Install mode

For each tool in the list above:

1. Run `<tool> --version` to check if it is already installed.
2. If installed, tell the user: `[<tool>] Already installed: <version>`
3. If not installed, tell the user: `[<tool>] Installing <tool>...` and run:

```bash
pip install <tool> --break-system-packages
```

4. After installation, run `<tool> --version` again to verify.
   - If verification succeeds, tell the user: `Installed: <version>`
   - If verification fails, tell the user: `FAILED to install <tool>: <error>`
