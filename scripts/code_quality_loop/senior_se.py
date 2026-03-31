"""Phase 2 — Senior Software Engineer.

Triages issues autonomously via LLM, then consults the human for
escalated (needs_human_approval) issues. Writes a decisions JSON that
contains only decision fields linked to issues by id.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import anthropic

from common import load_prompt, now_utc

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
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    return json.loads(text)


def _consult_human(
    issue: dict[str, Any],
    senior_se_reasoning: str,
    issue_index: int,
    total: int,
    client: anthropic.Anthropic,
    *,
    header_note: str = "⚠ Needs your input",
) -> dict[str, Any]:
    """Display the issue to the human and return a decision record (id + decision fields only)."""
    print(f"\n{'─' * 53}")
    print(f"Issue {issue_index}/{total}  [{issue['severity']}]  {header_note}")
    print(f"Location:    {issue['location']}")
    print(f"Fingerprint: {issue['fingerprint']}")
    print(f"\nDescription: {issue['description']}")
    print(f"\nFix: {issue['fix']}")
    print(f"\nSenior SE note: {senior_se_reasoning}")
    print(f"{'─' * 53}")
    print("  1) Do it")
    print("  2) Don't do it")
    print("  3) Skip for now")
    print("  4) Something else")

    while True:
        choice = input("> ").strip()
        if choice in ("1", "2", "3", "4"):
            break
        print("Please enter 1, 2, 3, or 4.")

    base = {
        "id": issue["id"],
        "decision_by": "human",
        "senior_se_reasoning": senior_se_reasoning,
        "status": "pending",
        "last_updated": now_utc(),
    }

    if choice == "1":
        return {**base, "action": "implement"}
    if choice == "2":
        return {**base, "action": "no"}
    if choice == "3":
        return {**base, "action": "skip_for_now"}

    user_input = input("Describe what you'd like instead:\n> ").strip()
    return _apply_custom_instruction(issue, user_input, base, client)


def _apply_custom_instruction(
    issue: dict[str, Any],
    user_input: str,
    base: dict[str, Any],
    client: anthropic.Anthropic,
) -> dict[str, Any]:
    """Send the issue + user free text to Claude and return a decision record."""
    system_prompt = load_prompt("senior_se_custom_prompt.md")
    payload = {"issue": issue, "user_input": user_input}
    response = client.messages.create(
        model=_MODEL,
        max_tokens=2048,
        system=system_prompt,
        messages=[{"role": "user", "content": json.dumps(payload, indent=2)}],
    )
    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    custom_fields = json.loads(text)
    custom_fields.pop("action", None)
    return {**base, "action": "custom", **custom_fields}


def run(issues_path: Path) -> Path:
    """Run the senior SE phase and return the path to the decisions JSON."""
    issues = json.loads(issues_path.read_text(encoding="utf-8"))
    decisions_path = issues_path.with_name(
        issues_path.name.replace(".issues.json", ".decisions.json")
    )

    existing_decisions: list[dict[str, Any]] = (
        json.loads(decisions_path.read_text(encoding="utf-8")) if decisions_path.exists() else []
    )
    issues_by_id = {issue["id"]: issue for issue in issues}
    decided_ids = {d["id"] for d in existing_decisions}
    pending = [d for d in existing_decisions if d["status"] == "pending"]
    new_issues = [issue for issue in issues if issue["id"] not in decided_ids]

    if not pending and not new_issues:
        print("Senior SE: all issues already have decisions.")
        return decisions_path

    client = anthropic.Anthropic()
    decisions = list(existing_decisions)
    total = len(pending) + len(new_issues)
    counter = 0

    # Re-present previously unresolved (pending) issues
    if pending:
        print(f"Senior SE: re-presenting {len(pending)} unresolved issue(s) from previous run ...")
        for decision in pending:
            issue = issues_by_id[decision["id"]]
            counter += 1
            header = (
                "⏭ Previously skipped — revisiting"
                if decision["action"] == "skip_for_now"
                else "⏸ Unresolved from previous run"
            )
            new_record = _consult_human(
                issue, decision["senior_se_reasoning"], counter, total, client,
                header_note=header,
            )
            idx = next(i for i, d in enumerate(decisions) if d["id"] == decision["id"])
            decisions[idx] = new_record
            decisions_path.write_text(json.dumps(decisions, indent=2), encoding="utf-8")

    # Triage and decide on new issues
    if new_issues:
        print(f"Senior SE: triaging {len(new_issues)} new issue(s) ...")
        triage_results = _triage_issues(new_issues, client)
        triage_by_id = {t["id"]: t for t in triage_results}
        print("Senior SE: triage complete.")

        for issue in new_issues:
            triage = triage_by_id[issue["id"]]
            triage_label = triage["triage"]
            reasoning = triage["senior_se_reasoning"]
            counter += 1

            if triage_label in _TRIAGE_TO_ACTION:
                record: dict[str, Any] = {
                    "id": issue["id"],
                    "action": _TRIAGE_TO_ACTION[triage_label],
                    "decision_by": "senior_se",
                    "senior_se_reasoning": reasoning,
                    "status": "pending",
                    "last_updated": now_utc(),
                }
            else:
                record = _consult_human(issue, reasoning, counter, total, client)

            decisions.append(record)
            decisions_path.write_text(json.dumps(decisions, indent=2), encoding="utf-8")

    return decisions_path
