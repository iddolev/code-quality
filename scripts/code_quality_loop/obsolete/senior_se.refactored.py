"""Phase 2 — Senior Software Engineer.

Two modes:

  default  — ages skip_for_now → skipped_re_ask, then triages new issues
  --next   — finds the next pending implement/custom decision, checks
             relevance, and prints either:
               NEXT <json>   the issue to pass to the rewriter
               DONE <n>      no more issues; n = deferred (skip_for_now/skipped_re_ask) count

Usage:
    python senior_se.py <source_path>
    python senior_se.py <source_path> --next
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import anthropic

from common import decisions_path, issues_path, load_prompt, log_append, now_utc, strip_markdown_fence

_MODEL = "claude-opus-4-6"

_TRIAGE_TO_ACTION = {
    "implement": "implement",
    "no": "no",
}


# ---------------------------------------------------------------------------
# Relevance check
# ---------------------------------------------------------------------------

def _check_relevance(
    source_code: str,
    issue: dict[str, Any],
    client: anthropic.Anthropic,
) -> tuple[str, str]:
    """Return (verdict, extra). verdict is one of:
      applicable         — issue still exists, fix can be applied as-is
      needs_update       — issue still exists but description/location have shifted;
                           extra contains the updated fields as a raw string
      impossible         — fix cannot be applied (location/structure gone)
      no_longer_relevant — issue already resolved by a prior fix
    """
    system_prompt = load_prompt("relevance_check_prompt.md")
    user_content = f"{source_code}\n\n---ISSUE---\n{json.dumps(issue, indent=2)}"
    response = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    raw = response.content[0].text.strip()
    first_line = raw.splitlines()[0].strip().lower()
    extra = "\n".join(raw.splitlines()[1:]).strip()
    return first_line, extra


# ---------------------------------------------------------------------------
# Triage
# ---------------------------------------------------------------------------

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
    triage_label = triage["triage"]
    action = _TRIAGE_TO_ACTION.get(triage_label, "needs_human_approval")
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


# ---------------------------------------------------------------------------
# Mode: default — age skips + triage new issues
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Mode: --next — relevance check + emit next issue for rewriter
# ---------------------------------------------------------------------------

def _parse_needs_update(extra: str) -> dict[str, str]:
    """Parse 'description: ...' and 'location: ...' lines from needs_update extra."""
    result: dict[str, str] = {}
    for line in extra.splitlines():
        if line.startswith("description:"):
            result["description"] = line[len("description:"):].strip()
        elif line.startswith("location:"):
            result["location"] = line[len("location:"):].strip()
    return result


def _save_updated_issue(
    issue: dict[str, Any],
    history_entry: dict[str, Any],
    updates: dict[str, str],
    source_path: Path,
    ip: Path,
    issues: list[dict[str, Any]],
) -> None:
    issue.setdefault("history", []).append(history_entry)
    issue.update(updates)
    issue["last_updated"] = now_utc()
    ip.write_text(json.dumps(issues, indent=2), encoding="utf-8")
    log_append(source_path, {
        "event": "issue_updated",
        "fingerprint": issue["fingerprint"],
        "old": history_entry,
        "new": updates,
    })


def _apply_needs_update(
    issue: dict[str, Any],
    extra: str,
    source_path: Path,
    ip: Path,
    issues: list[dict[str, Any]],
) -> None:
    """Update issue in place if LLM provided valid description/location updates."""
    updates = _parse_needs_update(extra)
    if not updates.get("description") or not updates.get("location"):
        return
    history_entry = {
        "description": issue["description"],
        "location": issue["location"],
        "timestamp": now_utc(),
    }
    _save_updated_issue(issue, history_entry, updates, source_path, ip, issues)


def _mark_skipped_decision(
    decision: dict[str, Any],
    verdict: str,
    decisions: list[dict[str, Any]],
    dp: Path,
    source_path: Path,
    issue: dict[str, Any],
) -> None:
    decision["status"] = verdict
    decision["last_updated"] = now_utc()
    dp.write_text(json.dumps(decisions, indent=2), encoding="utf-8")
    log_append(source_path, {
        "event": "relevance_skipped",
        "fingerprint": issue["fingerprint"],
        "verdict": verdict,
    })


def _process_actionable_decision(
    decision: dict[str, Any],
    issue: dict[str, Any],
    source_code: str,
    client: anthropic.Anthropic,
    source_path: Path,
    ip: Path,
    issues: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    dp: Path,
) -> bool:
    """Check relevance and emit NEXT if applicable. Returns True if NEXT was emitted."""
    log_append(source_path, {"event": "relevance_check", "fingerprint": issue["fingerprint"]})
    verdict, extra = _check_relevance(source_code, issue, client)
    if verdict == "applicable":
        print(f"NEXT {json.dumps(issue)}")
        return True
    if verdict == "needs_update":
        _apply_needs_update(issue, extra, source_path, ip, issues)
        print(f"NEXT {json.dumps(issue)}")
        return True
    if verdict not in ("impossible", "no_longer_relevant"):
        # Unexpected verdict from LLM — treat as applicable
        print(f"NEXT {json.dumps(issue)}")
        return True
    _mark_skipped_decision(decision, verdict, decisions, dp, source_path, issue)
    return False


def _load_run_next_data(
    source_path: Path,
    ip: Path,
    dp: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], str]:
    issues = json.loads(ip.read_text(encoding="utf-8"))
    decisions = json.loads(dp.read_text(encoding="utf-8"))
    issues_by_id = {issue["id"]: issue for issue in issues}
    source_code = source_path.read_text(encoding="utf-8")
    return issues, decisions, issues_by_id, source_code


def _count_deferred(decisions: list[dict[str, Any]]) -> int:
    return sum(
        1 for d in decisions
        if d["action"] in ("skip_for_now", "skipped_re_ask") and d["status"] == "pending"
    )


def run_next(source_path: Path) -> None:
    """Find the next pending implement/custom decision, check relevance, and print result."""
    ip, dp = issues_path(source_path), decisions_path(source_path)
    issues, decisions, issues_by_id, source_code = _load_run_next_data(source_path, ip, dp)
    client = anthropic.Anthropic()
    actionable = [
        d for d in decisions
        if d["action"] in ("implement", "custom") and d["status"] == "pending"
    ]
    for decision in actionable:
        issue = issues_by_id[decision["id"]]
        done = _process_actionable_decision(
            decision, issue, source_code, client, source_path, ip, issues, decisions, dp
        )
        if done:
            return
    print(f"DONE {_count_deferred(decisions)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    parser.add_argument("--next", dest="next_mode", action="store_true")
    args = parser.parse_args()

    if args.next_mode:
        run_next(args.source_path)
    else:
        run(args.source_path)
