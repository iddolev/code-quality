"""Install code quality tools: ruff, pylint, pyright, vulture, radon, bandit, deptry, pip-audit."""

import subprocess
import sys

TOOLS = ["ruff", "pylint", "pyright", "vulture", "radon", "bandit", "deptry", "pip-audit"]


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def get_version(tool: str) -> str | None:
    result = run([tool, "--version"])
    if result.returncode == 0:
        return result.stdout.strip() or result.stderr.strip()
    return None


def install(tool: str) -> None:
    print(f"  Installing {tool}...")
    result = run([sys.executable, "-m", "pip", "install", tool, "--break-system-packages"])
    if result.returncode != 0:
        print(f"  FAILED to install {tool}: {result.stderr.strip()}")
        return
    version = get_version(tool)
    if version:
        print(f"  Installed: {version}")
    else:
        print(f"  Installed {tool} but could not verify version.")


def main() -> None:
    for tool in TOOLS:
        print(f"[{tool}]")
        version = get_version(tool)
        if version:
            print(f"  Already installed: {version}")
        else:
            install(tool)
        print()


if __name__ == "__main__":
    main()
