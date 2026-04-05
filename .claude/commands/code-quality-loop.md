---
description: "Apply a feedback loop that asks LLM to find issues"
argument-hint: "<file-or-folder (optional)> or all for all python files"
---

# Code Quality Loop — Claude Workflow

This file is the orchestration guide for the code quality loop. Claude reads it and
follows these instructions when the user runs the workflow on a source file.

## Invocation

The user triggers this workflow with an input argument which is a source file path, e.g.:

```
/code-quality path/to/file.py
```

### Multi-file mode

If no argument is given, ask the user on what file or folder they want to run.

If the argument is `all` run the workflow on **every
`.py` file in the repository**, excluding:

- Files inside `sandbox/`
- Files excluded by `.gitignore` (e.g. `venv/`, `tmp/`, `__pycache__/`, etc.)

To collect the file list, run:

```bash
git ls-files '*.py'
```

This respects `.gitignore` automatically. Then filter out any paths that start with
`sandbox/`. Process the resulting files **one at a time**, running the full workflow
(Phases 1-5 + the optional re-loop) on each file before moving to the next. Report
which file is being processed as you go.

---

All four phases operate on sibling files next to the source code file:

- `<file>.issues.json` — critic output
- `<file>.decisions.json` — triage + human decisions
- `<file>.log.jsonl` — append-only structured log of relevance checks and issue updates

---

## Phase 1 — Critic

Run the critic script to detect new issues:

```bash
python scripts/code_quality_loop/critic.py <source_path>
```

The script reads the source file and passes it to Claude along with any currently
open issues (so the LLM does not re-report them). New issues are appended to
`<file>.issues.json` with sequential ids.

Report to the user: how many new issues were found and how many were already known.

---

## Phase 2 — Senior SE Triage

Run the triage script:

```bash
python scripts/code_quality_loop/senior_se_triage.py <source_path>
```

The script does two things in order:

1. **Age skipped decisions** — converts every existing `skip_for_now` record in
   `decisions.json` to `skipped_re_ask`. This marks issues that were deferred in a
   previous run so that they will be re-presented to the human in Phase 3.

2. **Triage new issues** — for every issue in `issues.json` that has no decision
   record yet, writes a new decision record with one of three actions:
   - `implement` — safe to apply automatically
   - `no` — should not be applied
   - `needs_human_approval` — requires human judgement

   Each record also contains the reason why the senior SE made this decision.

No human input is involved in this phase.

Report to the user: how many issues were auto-approved, auto-rejected, flagged for
human review, and how many previously-skipped issues will be re-asked.

---

## Phase 3 — Human Review

Read both `.decisions.json` and `.issues.json` for the source file. Join them by
`id` to assemble the full picture for each issue. Collect all decision records with
`action: needs_human_approval` or `action: skipped_re_ask`.
If there are none, skip this phase entirely.

Otherwise, tell the user how many issues need their input, then present them
**one by one**.

### Per-issue presentation

For each issue show:

- Severity and fingerprint (as a heading)
- Location
- Description — what is wrong and why it matters
- Proposed fix
- Senior SE reasoning — why it was escalated

Then use the `AskUserQuestion` tool to ask for the user's decision. If the
proposed fix contains a single clear action, use these four options:

- **Approve** — apply the fix as proposed
- **Reject** — don't apply this fix
- **Skip** — defer it to a future run
- **Custom** — provide a different fix instruction

If the proposed fix presents multiple alternatives (e.g., "do A or B",
"either X, or at minimum Y"), list each alternative as its own option instead
of a single "Approve". Always include **Reject** and **Skip** as well. When the
user picks one of the alternatives, record it as `action: "custom"` with
`custom_fix` set to the chosen alternative's description.

If the record has `action: skipped_re_ask`, note in the question that this issue
was previously deferred.

The user may choose "Other" to ask questions, explore alternatives, or look at
related code — engage with all of that before asking for a final decision.

Once a decision is reached, update the existing record in `decisions.json` by finding
it by `id` and applying these fields:

| User intent | `action` | notes |
|---|---|---|
| Yes / do it / approve | `implement` | |
| No / don't do it / reject | `no` | |
| Skip / later / not now | `skip_for_now` | |
| Do something different | `custom` | also set `custom_fix` to the instruction |

In all cases also set:

- `decision_by: "human"`
- `last_updated: <current UTC timestamp>`
- keep `status: "pending"` (the rewriter will mark it `done`)

After recording, move to the next issue.

When all issues have been discussed, report a summary: how many were approved,
rejected, deferred, or given a custom instruction. Then proceed to Phase 4.

---

## Phase 4 — Test Driven Development

Before any source code is modified, ensure the test suite covers the issues that
are about to be fixed by reading and following the instructions in `scripts/code_quality_loop/phase4-tdd.md`.

---

## Phase 5 — Rewriter

Apply fixes one at a time using a loop. Each iteration asks Senior SE for the next
relevant issue, then immediately applies it before checking the next issue — each
fix changes the source file, so this may affect the relevance of subsequent issues.

### Loop

Call Senior SE to get the next issue that should be applied:

```bash
python scripts/code_quality_loop/senior_se_next_issue.py <source_path>
```

The script finds the next pending `implement` or `custom` decision, runs a
relevance check against the current source file, and writes one of:

- `NEXT <json>` — the next issue to apply (possibly with updated description/location)
- `DONE <n>` — no more issues; `n` is the count of deferred (`skip_for_now` or `skipped_re_ask`) decisions still pending

The relevance check has four possible verdicts. The script handles them internally:

- `applicable` - Returns `NEXT` with the original issue unchanged
- `needs_update` - Appends `{description, location, timestamp}` to a `history` list on the issue record in `issues.json` (preserving the old values), then overwrites description
  and location with the updated values, and returns `NEXT` with the refreshed issue
- `no_longer_relevant` - Marks the decision as `no_longer_relevant` in `decisions.json`, moves to the next decision
- `impossible` - Marks the decision as `impossible` in `decisions.json`, moves to the next decision |

If the response is `NEXT <json>`, run the rewriter for that issue:

```bash
python scripts/code_quality_loop/rewriter.py <source_path> --id <issue_id>
```

The rewriter sets the decision status to `to_test` (not `done`) after applying the
fix.

### Verify the fix

After each rewrite, immediately verify it by:

1. Remove the `@pytest.mark.xfail` marker from the test(s) for this issue (the
   ones added in Phase 4 with `reason="issue #<id>: ..."`).
2. Run the full test suite:

   ```bash
   python -m pytest <test_file> -v
   ```

3. If all tests pass (including the formerly-xfail test), update the decision
   status from `to_test` to `done`.
4. If the new test still fails, or if other tests broke, report the failure to
   the user and stop the loop — do not continue to the next issue.

Then repeat the loop from the top (call Senior SE for the next issue).

### End of loop

When Senior SE responds with `DONE`, report to the user:

- How many fixes were applied and verified
- How many were skipped as no longer relevant
- How many deferred decisions remain for a future run (the `n` from `DONE <n>`)

If there are no `implement` or `custom` decisions at all, skip this phase.

---

## Loop behaviour

After the final rewriter pass, ask the user whether to run another critic pass on
the updated file. If yes, restart from Phase 1. This catches any issues introduced
by the fixes just applied, as well as any further issues that the critic did not raise
during the previous rounds.

---

## Error handling

- If any script exits with a non-zero code, show the error output and stop.
- If `issues.json` is missing after Phase 1, report the problem and stop.
- If `decisions.json` is missing after Phase 2, there are no issues to action —
  skip Phases 3 and 4 and offer to run another critic pass.
- If the source file does not exist, report this immediately before running anything.
