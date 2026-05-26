# Known Bugs

Bugs discovered but not yet fixed. Each entry: symptom, root cause, and fix sketch.

## 1. static_analysis_suite tests are stale (28 failures) — API drift vs. implementation

**Discovered:** 2026-05-26

**Symptom:** Running the test suite gives `28 failed, 188 passed, 9 xfailed`. All 28
failures are in `tests/static_analysis_suite/test_python_static_analysis_suite.py`,
and most show:

```
AttributeError: 'NoneType' object has no attribute 'write'
  at python_static_analysis_suite.py:100  (self._log_file.write(...))
```

These failures are unrelated to the `format_markdown` work and to the pip/venv setup
issues — they pre-date both and live in a different module.

**Root cause:** `StaticAnalysisToolsRunner` was refactored to a **path-based** API, but
the tests still use the **old buffer-based** API.

The implementation (`.claude/code-quality/scripts/python_static_analysis/python_static_analysis_suite.py`):

```python
def __init__(self, log_path: Path):
    ...
    self._log_path = log_path
    self._log_file = None          # stays None until run() opens the file

def run(self, path):
    with open(self._log_path, "w", encoding="utf-8") as log_file:
        self._log_file = log_file   # only set for the duration of run()
        ...
```

The test helper (`test_python_static_analysis_suite.py:26`):

```python
def _make_runner():
    buf = StringIO()
    return StaticAnalysisToolsRunner(buf), buf   # passes a buffer where a path is expected
```

So the tests pass a `StringIO` expecting it to become `self._log_file`, but the new
constructor stores it as `self._log_path` and leaves `self._log_file = None`. Every test
that writes to the log then fails.

Two failure modes:

- **Tests calling internal methods directly** (`_write_result`, `_run_tool`,
  `_write_missing_tools_summary`, `_write_stats`): `_log_file` is `None` →
  `'NoneType' object has no attribute 'write'`.
- **Tests calling `runner.run(...)`** (lines ~110, 162, 190, 235, 382): `run()` does
  `open(self._log_path, ...)`, but `_log_path` is a `StringIO`, not a path → also fails.

The production path (`main()` → `StaticAnalysisToolsRunner(log_path).run(path)`) is
self-consistent and works. **Only the test file is out of date.**

**Fix sketch:** Migrate the tests to the path-based API.

- **Unit tests** that poke internal methods: build with a dummy path, then inject the
  buffer — `runner = StaticAnalysisToolsRunner(Path("x.log")); runner._log_file = buf`.
- **`run()` end-to-end tests**: pass a real temp file (`tmp_path / "report.log"`), then
  read it back to assert on contents, instead of `buf.getvalue()`.

All 28 failures share this single cause, so the fix is a self-contained test refactor.
Run the suite green afterward to confirm.
