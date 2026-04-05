"""Add .claude/code-quality/scripts/format_markdown to sys.path for test imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "code-quality" / "scripts" / "format_markdown"))
