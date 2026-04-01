"""Phase 2a — Senior Software Engineer: triage.

Ages skip_for_now → skipped_re_ask, then classifies new issues as
implement / no / needs_human_approval.

Usage:
    python senior_se_triage.py <source_path>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import anthropic

from common import decisions_path, issues_path, load_prompt, now_utc, strip_markdown_fence

_MODEL = "claude-opus-4-6"

_TRIAGE_TO_ACTION = {
    "implement": "implement",
    "no": "no",
}


def _triage_issues(
    issues: list[dict[str, Any]],
    client: anthropic.Anthropic,
) -> list[dict[str, Any]]:
    """Call Claude to triage all issues. Returns list of triage dicts keyed by id."""
    system_prompt = load_prompt("senior_se_triage_prompt.md")
    response = client.messages.create(
        model=_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(issues, indent=2)}],
    )
    return json.loads(strip_markdown_fence(response.content[0].text))


def _age_skip_decisions(decisions: list[dict[str, Any]], dp: Path) -> int:
    """Age skip_for_now → skipped_re_ask in place. Returns count of aged decisions."""
    aged = 0
    for d in decisions:
        if d["action"] == "skip_for_now":
            d["action"] = "skipped_re_ask"
            d["last_updated"] = now_utc()
            aged += 1
    if aged:
        dp.write_text(json.dumps(decisions, indent=2), encoding="utf-8")
    return aged


def _make_decision_record(issue: dict[str, Any], triage: dict[str, Any]) -> dict[str, Any]:
    action = _TRIAGE_TO_ACTION.get(triage["triage"], "needs_human_approval")
    return {
        "id": issue["id"],
        "action": action,
        "decision_by": "senior_se",
        "senior_se_reasoning": triage["senior_se_reasoning"],
        "status": "pending",
        "last_updated": now_utc(),
    }


def _process_triage_results(
    new_issues: list[dict[str, Any]],
    triage_by_id: dict[str, Any],
    decisions: list[dict[str, Any]],
    dp: Path,
) -> tuple[int, int, int]:
    """Append decision records and write after each. Returns (auto_implement, auto_no, needs_human)."""
    auto_implement = auto_no = needs_human = 0
    for issue in new_issues:
        record = _make_decision_record(issue, triage_by_id[issue["id"]])
        decisions.append(record)
        dp.write_text(json.dumps(decisions, indent=2), encoding="utf-8")
        if record["action"] == "implement":
            auto_implement += 1
        elif record["action"] == "no":
            auto_no += 1
        else:
            needs_human += 1
    return auto_implement, auto_no, needs_human


def _load_existing_decisions(dp: Path) -> list[dict[str, Any]]:
    return json.loads(dp.read_text(encoding="utf-8")) if dp.exists() else []


def _triage_and_record(
    new_issues: list[dict[str, Any]],
    existing_decisions: list[dict[str, Any]],
    dp: Path,
) -> None:
    print(f"Senior SE: triaging {len(new_issues)} new issue(s) ...")
    client = anthropic.Anthropic()
    triage_results = _triage_issues(new_issues, client)
    triage_by_id = {t["id"]: t for t in triage_results}
    print("Senior SE: triage complete.")
    decisions = list(existing_decisions)
    auto_implement, auto_no, needs_human = _process_triage_results(
        new_issues, triage_by_id, decisions, dp
    )
    print(
        f"Senior SE: {auto_implement} auto-approved, "
        f"{auto_no} auto-rejected, "
        f"{needs_human} need human review."
    )


def run(source_path: Path) -> None:
    """Age skip_for_now → skipped_re_ask, then triage all new issues."""
    ip = issues_path(source_path)
    dp = decisions_path(source_path)
    if not ip.exists():
        print(f"Senior SE: issues file not found: {ip}")
        return
    issues = json.loads(ip.read_text(encoding="utf-8"))
    existing_decisions = _load_existing_decisions(dp)
    aged = _age_skip_decisions(existing_decisions, dp)
    if aged:
        print(f"Senior SE: aged {aged} skip_for_now → skipped_re_ask.")
    decided_ids = {d["id"] for d in existing_decisions}
    new_issues = [issue for issue in issues if issue["id"] not in decided_ids]
    if not new_issues:
        print("Senior SE: no new issues to triage.")
        return
    _triage_and_record(new_issues, existing_decisions, dp)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    args = parser.parse_args()
    run(args.source_path)
