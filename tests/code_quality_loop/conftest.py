"""Add .claude/code-quality/scripts/code_quality_loop to sys.path for test imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "code-quality" / "scripts" / "code_quality_loop"))
