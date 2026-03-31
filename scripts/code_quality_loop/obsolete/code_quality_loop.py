"""Code Quality Loop — Orchestrator.

Usage:
    python scripts/code_quality_loop/code_quality_loop.py <path/to/file.py>
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

import critic
import senior_se
import rewriter


def main(source_path: Path) -> None:
    issues_path = critic.run(source_path)
    decisions_path = senior_se.run(issues_path)
    rewriter.run(source_path, decisions_path)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python code_quality_loop.py <path/to/file.py>")
        sys.exit(1)
    main(Path(sys.argv[1]))
