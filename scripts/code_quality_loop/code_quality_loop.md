# Code Quality Loop — Claude Workflow

This file is the orchestration guide for the code quality loop. Claude reads it and
follows these instructions when the user runs the workflow on a source file.

## Invocation

The user triggers this workflow with an input argument which is a source file path, e.g.:

```
/code-quality path/to/file.py
```

All four phases operate on sibling JSON files next to the source code file:
- `<file>.issues.json` — critic output
- `<file>.decisions.json` — triage + human decisions

---

## Phase 1 — Critic

Run the critic script to detect new issues:

```bash
python scripts/code_quality_loop/critic.py <source_path>
```

The script reads the source file, calls Claude, and appends any new issues to
`<file>.issues.json`. It skips issues already tracked (by fingerprint).

Report to the user: how many new issues were found and how many were already known.

---

## Phase 2 — Senior SE Triage

Run the triage script:

```bash
python scripts/code_quality_loop/senior_se.py <source_path>
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

Read the relevant `.decisions.json` file and collect all records with
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

Then invite the user to respond. Do **not** present a numbered menu. Keep it
conversational.

### Handling responses

If the record has `action: skipped_re_ask`, note to the user that this issue was
previously deferred.

Stay in the conversation for the current issue until the user reaches a clear
decision, or decides to skip the issue for now.
The user may want to ask questions, explore alternatives, or look at related
code — engage with all of that before asking for a final call.

Once a decision is reached, record it immediately in `decisions.json`:

| User intent | `action` to record |
|---|---|
| Yes / do it / approve | `implement` |
| No / don't do it / reject | `no` |
| Skip / later / not now | `skip_for_now` |
| Do something different | `custom` — capture the instruction in `custom_fix` |

After recording, move to the next issue.

When all issues have been discussed, report a summary: how many were approved,
rejected, deferred, or given a custom instruction. Then proceed to Phase 4.

---

## Phase 4 — Rewriter

Apply fixes one at a time using a loop. Each iteration asks Senior SE for the next
relevant issue, then immediately applies it before checking the next — because each
fix changes the source file, which affects the relevance of subsequent issues.

### Loop

Call Senior SE to get the next issue to apply:

```bash
python scripts/code_quality_loop/senior_se.py --next <source_path>
```

The script finds the next pending `implement` or `custom` decision, runs a
relevance check against the current source file, and writes one of:

- `NEXT <json>` — the next issue to apply (possibly with updated description/location)
- `DONE <n>` — no more issues; `n` is the count of `skip_for_now` decisions still pending

The relevance check has four possible verdicts. The script handles them internally:

| Verdict | What the script does |
|---|---|
| `applicable` | Returns `NEXT` with the original issue unchanged |
| `needs_update` | Appends `{description, location, timestamp}` to a `history` list on the issue record in `issues.json` (preserving the old values), then overwrites description and location with the updated values, and returns `NEXT` with the refreshed issue |
| `no_longer_relevant` | Marks the decision as `no_longer_relevant` in `decisions.json`, moves to the next decision |
| `impossible` | Marks the decision as `impossible` in `decisions.json`, moves to the next decision |

If the response is `NEXT <json>`, run the rewriter for that issue:

```bash
python scripts/code_quality_loop/rewriter.py <source_path> --id <issue_id>
```

Then repeat the loop from the top.

### End of loop

When Senior SE responds with `DONE`, report to the user:

- How many fixes were applied
- How many were skipped as no longer relevant
- How many `skip_for_now` decisions remain for a future run

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
- If `issues.json` is missing after Phase 1, or `decisions.json` is missing after
  Phase 2, report the problem and stop.
- If the source file does not exist, report this immediately before running anything.
