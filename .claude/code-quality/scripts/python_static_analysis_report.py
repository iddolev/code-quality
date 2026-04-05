"""Filter and format parsed static-analysis findings into a readable report.

Usage:
    python python_static_analysis_report.py <jsonl_path> <output_log_path>

Input:  JSON Lines file produced by python_static_analysis_parse_log.py
Output: human-readable report with four sections:
        1. Summary  2. All findings  3. Auto-fixable  4. Manual review

Rule configuration (ignore / auto_fixable / category) is loaded from
python_static_analysis_report.yaml in the same directory as this script.
"""

import json
import sys
from collections import Counter
from pathlib import Path

import yaml

_SCRIPT_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _SCRIPT_DIR / "python_static_analysis_report.yaml"

# ---------------------------------------------------------------------------
# Load rule configuration from YAML
# ---------------------------------------------------------------------------


def _load_config() -> dict[str, dict]:
    """Load rule config from YAML. Returns {rule_code: {category, ignore, auto_fixable}}."""
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # YAML is nested: rules -> tool_name -> rule_code -> props
    # Flatten to: {rule_code: props}
    rules: dict[str, dict] = {}
    for tool_rules in (data.get("rules") or {}).values():
        if not isinstance(tool_rules, dict):
            continue
        for rule_code, props in tool_rules.items():
            if props is None:
                props = {}
            props.setdefault("category", None)
            props.setdefault("ignore", False)
            props.setdefault("auto_fixable", False)
            rules[rule_code] = props
    return rules


_RULES = _load_config()

# ---------------------------------------------------------------------------
# Ignore logic
# ---------------------------------------------------------------------------


def _should_ignore(finding: dict) -> bool:
    """Return True if the finding should be filtered out."""
    rule = finding.get("rule", "")
    tool = finding.get("tool", "")
    desc = finding.get("description", "")
    file_path = finding.get("file", "")

    # YAML-configured ignores
    if rule in _RULES and _RULES[rule].get("ignore"):
        return True

    # Special patterns not in YAML (context-dependent)

    # pyright .text on non-TextBlock — intentional behavior
    if (tool == "pyright"
            and rule == "reportAttributeAccessIssue"
            and 'Cannot access attribute "text"' in desc):
        return True

    # bandit B101 (assert_used) in test files
    if rule.startswith("B101") and ("test" in file_path.lower()):
        return True

    # bandit B404 (subprocess import) — too noisy
    if rule.startswith("B404"):
        return True

    return False


# ---------------------------------------------------------------------------
# Auto-fixable classification
# ---------------------------------------------------------------------------


def _is_auto_fixable(finding: dict) -> bool:
    """Return True if the finding can be safely auto-fixed."""
    if finding.get("ruff_fixable"):
        return True
    if finding.get("fixit_autofix"):
        return True
    rule = finding.get("rule", "")
    if rule in _RULES:
        return _RULES[rule].get("auto_fixable", False)
    return False


# ---------------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------------

# Fallback categories by tool (when rule is not in YAML)
_TOOL_FALLBACK_CATEGORY = {
    "bandit": "security",
    "radon": "complexity",
    "pyright": "type-safety",
}

# Fallback categories by pylint code prefix
_PYLINT_PREFIX_CATEGORY = {
    "C": "convention",
    "W": "warning",
    "E": "error",
    "F": "error",
    "R": "design",
}


def _categorize(finding: dict) -> str:
    """Return a human-readable category for a finding."""
    rule = finding.get("rule", "")

    if rule in _RULES:
        cat = _RULES[rule].get("category")
        if cat:
            return cat

    # Fallback by tool
    tool = finding.get("tool", "")
    if tool in _TOOL_FALLBACK_CATEGORY:
        return _TOOL_FALLBACK_CATEGORY[tool]

    # Fallback by pylint code prefix
    if rule and rule[0] in _PYLINT_PREFIX_CATEGORY:
        return _PYLINT_PREFIX_CATEGORY[rule[0]]

    return "uncategorized"


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def _format_finding(finding: dict, auto_fixable: bool) -> str:
    """Format a single finding as a multi-line string."""
    category = _categorize(finding)
    severity = finding.get("severity", "warning").upper()
    lines = [
        f"Line {finding['line']}: [{category}] {severity}"
        f" \u2014 {finding['description']}",
        f"  Tool: {finding['tool']}",
        f"  Rule: {finding['rule']}",
        f"  Auto-fixable: {'Yes' if auto_fixable else 'No'}",
    ]
    return "\n".join(lines)


def _format_report(findings: list[dict],
                   unparsed: list[dict] | None = None,
                   uncategorized_rules: list[tuple[str, str]] | None = None,
                   ) -> str:
    """Build the full report string from filtered findings."""
    # Classify each finding
    classified = []
    for f in findings:
        af = _is_auto_fixable(f)
        classified.append((f, af))

    # Sort by file, then line
    classified.sort(key=lambda x: (x[0].get("file", ""), x[0].get("line", 0)))

    # --- Section 1: Summary ---
    severity_counts = Counter(f.get("severity", "warning") for f, _ in classified)
    category_counts = Counter(_categorize(f) for f, _ in classified)

    summary_lines = ["## 1. Summary", ""]
    summary_lines.append(
        f"Total findings: {len(classified)}  "
        f"(Error: {severity_counts.get('error', 0)}, "
        f"Warning: {severity_counts.get('warning', 0)}, "
        f"Suggestion: {severity_counts.get('suggestion', 0)})"
    )
    summary_lines.append("")
    summary_lines.append("By category:")
    for cat, count in category_counts.most_common():
        summary_lines.append(f"  {cat}: {count}")

    # --- Section 2: All findings ---
    section2_lines = ["", "## 2. Findings (sorted by file, then line)", ""]
    current_file = None
    for f, af in classified:
        file_path = f.get("file", "")
        if file_path != current_file:
            current_file = file_path
            section2_lines.append(f"### {file_path}")
            section2_lines.append("")
        section2_lines.append(_format_finding(f, af))
        section2_lines.append("")

    # --- Section 3: Auto-fixable ---
    auto_fixable = [(f, af) for f, af in classified if af]
    section3_lines = ["## 3. Auto-fixable changes", ""]
    if auto_fixable:
        for f, af in auto_fixable:
            section3_lines.append(_format_finding(f, af))
            section3_lines.append("")
    else:
        section3_lines.append("No auto-fixable changes found.")
        section3_lines.append("")

    # --- Section 4: Manual review ---
    manual = [(f, af) for f, af in classified if not af]
    section4_lines = ["## 4. Manual review changes", ""]
    if manual:
        for f, af in manual:
            section4_lines.append(_format_finding(f, af))
            section4_lines.append("")
    else:
        section4_lines.append("No manual review changes.")
        section4_lines.append("")

    # --- Section 5: Unparsed notices ---
    section5_lines = []
    if unparsed:
        section5_lines.append("## 5. Unparsed tool output")
        section5_lines.append("")
        section5_lines.append(
            f"{len(unparsed)} finding(s) could not be parsed into "
            "structured form. Check the raw log for details:"
        )
        section5_lines.append("")
        for u in unparsed:
            tool = u.get("tool", "unknown")
            file_path = u.get("file", "unknown")
            desc = u.get("description", "")
            if len(desc) > 120:
                desc = desc[:120] + "..."
            section5_lines.append(f"  - [{tool}] {file_path}: {desc}")
        section5_lines.append("")

    # --- Section 6: Uncategorized rules ---
    section6_lines = []
    if uncategorized_rules:
        section6_lines.append("## 6. Uncategorized rules")
        section6_lines.append("")
        section6_lines.append(
            "The following rules are not yet in "
            "python_static_analysis_report.yaml. "
            "Add them with a category, or mark as ignore/auto_fixable:"
        )
        section6_lines.append("")
        for rule, desc in uncategorized_rules:
            section6_lines.append(f"  - {rule}: {desc}")
        section6_lines.append("")

    return "\n".join(
        summary_lines + section2_lines + section3_lines
        + section4_lines + section5_lines + section6_lines
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python python_static_analysis_report.py "
              "<jsonl_path> <output_log_path>")
        sys.exit(1)

    jsonl_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not jsonl_path.exists():
        print(f"Error: {jsonl_path} does not exist.")
        sys.exit(1)

    # Read and filter
    findings = []
    unparsed = []
    ignored_count = 0
    seen_rules = {}  # rule -> first description seen
    with open(jsonl_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            finding = json.loads(line)
            rule = finding.get("rule", "")
            if rule == "unparsed":
                unparsed.append(finding)
            elif _should_ignore(finding):
                ignored_count += 1
            else:
                findings.append(finding)
                if rule not in seen_rules:
                    seen_rules[rule] = finding.get("description", "")

    # Detect uncategorized rules (not in YAML at all)
    uncategorized = [
        (rule, desc) for rule, desc in sorted(seen_rules.items())
        if rule not in _RULES
    ]

    # Format and write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report = _format_report(findings, unparsed=unparsed,
                            uncategorized_rules=uncategorized)
    output_path.write_text(report, encoding="utf-8")

    print(f"Filtered {ignored_count} ignored findings, "
          f"{len(findings)} remaining, "
          f"{len(unparsed)} unparsed, "
          f"{len(uncategorized)} uncategorized rules "
          f"-> {output_path}")


if __name__ == "__main__":
    main()
