"""Put .claude/code-quality/scripts (and its code_quality_loop/ subdir) at the
front of sys.path so test imports resolve to the real modules rather than the
tests/code_quality_loop/ directory, which also happens to be a package."""
import sys
from pathlib import Path

_SCRIPTS_DIR = (Path(__file__).resolve().parents[2]
                / ".claude" / "code-quality" / "scripts")

# code_quality_loop subdir first, so `import critic` etc. still work.
sys.path.insert(0, str(_SCRIPTS_DIR / "code_quality_loop"))
# scripts/ ahead of tests/ so `code_quality_loop` resolves to the real package.
sys.path.insert(0, str(_SCRIPTS_DIR))
