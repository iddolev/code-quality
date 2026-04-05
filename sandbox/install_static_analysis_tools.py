"""Install code quality tools: ruff, pylint, pyright, vulture, radon, bandit, deptry, pip-audit."""

import argparse
import subprocess
import sys

TOOLS = ["ruff", "pylint", "pyright", "vulture", "radon", "bandit", "deptry", "pip-audit"]


def run(cmd: list[str]) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True)
    except OSError:
        return None


def get_version(tool: str) -> str | None:
    result = run([tool, "--version"])
    if result and result.returncode == 0:
        return result.stdout.strip() or result.stderr.strip()
    return None


def install(tool: str) -> None:
    print(f"  Installing {tool}...")
    result = run([sys.executable, "-m", "pip", "install", tool, "--break-system-packages"])
    if not result or result.returncode != 0:
        stderr = result.stderr.strip() if result else "command failed to run"
        print(f"  FAILED to install {tool}: {stderr}")
        return

    version = get_version(tool)
    if version:
        print(f"  Installed: {version}")
    else:
        print(f"  Installed {tool} but could not verify version.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Install code quality tools.")
    parser.add_argument("--missing", action="store_true", help="Print missing tools and exit.")
    args = parser.parse_args()

    if args.missing:
        missing = [tool for tool in TOOLS if not get_version(tool)]
        if missing:
            print("need installation: " + ", ".join(missing))
        else:
            print("all installed")
        return

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
