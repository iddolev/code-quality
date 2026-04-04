Before any source code is modified, ensure the test suite covers the issues that
are about to be fixed. This follows test-driven development: failing tests come
before code changes.

### Locate the test file

The test file lives at `tests/<package>/<test_file>.py`, mirroring the source path.
For example, `scripts/format_markdown/wrap_long_lines.py` →
`tests/format_markdown/test_wrap_long_lines.py`.

If the test file does not exist yet, create it with comprehensive baseline tests
for the source file's current public behaviour (i.e. tests that pass right now).

### Add tests for approved issues

For every decision with `action: implement` or `action: custom` (i.e. the issues
that Phase 5 will fix), add one or more test cases that **expose the bug or
missing behaviour described by the issue**. These tests should:

- Target the specific edge case, correctness problem, or missing coverage the
  issue describes.
- Fail (or be marked `@pytest.mark.xfail(reason="issue #<id>: <fingerprint>")`)
  against the current source code, since the fix has not been applied yet.
- Pass once the fix is applied in Phase 5.

Use `xfail` rather than letting the suite go red, so that the rest of the loop
can continue without a broken test run.

### Run the tests

```bash
python -m pytest <test_file> -v
```

All existing tests must still pass and the new tests must be recognised (shown as
`XFAIL`). If anything unexpected fails, diagnose and fix the test before
proceeding.

Report to the user: how many new test cases were added and confirm the suite is
green (with expected xfails). Then proceed to Phase 5.
