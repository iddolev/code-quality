"""Parse raw static-analysis log into structured JSON Lines.

Usage:
    python python_static_analysis_parse_log.py <raw_log_path> <output_jsonl_path>

Input:  the XML-like raw log produced by python_static_analysis_suite.py
Output: one JSON object per line (JSON Lines), each representing a single finding:

    {"file": "...", "line": 42, "col": 0, "tool": "pylint", "rule": "C0301",
     "severity": "warning", "description": "Line too long (101/100)"}

Tool sections that produce no parseable findings (clean runs, install errors,
boilerplate) are silently skipped.  Unknown or malformed lines within a tool
section are collected into a single "unparsed" finding so the caller can
decide what to do with them.
"""

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Regex patterns — one group of patterns per tool
# ---------------------------------------------------------------------------

# pylint:  file:line:col: CODE: message (rule-name)
_PYLINT_RE = re.compile(
    r"^.*?:(\d+):(\d+): ([A-Z]\d{4}): (.+?) \(([a-z][\w-]*)\)\s*$"
)

# pyright single-line: file:line:col - severity: message (ruleCode)
_PYRIGHT_RE = re.compile(
    r"^.*?:(\d+):(\d+) - (error|warning|information): (.+?) \((\w+)\)\s*$"
)
# pyright multi-line: first line has no (ruleCode), continuation line has it
# Anchored to file-path pattern (drive letter or relative path with backslash/slash)
_PYRIGHT_NOPAREN_RE = re.compile(
    r"^(?:[a-zA-Z]:|\.)?[\\/].*?:(\d+):(\d+) - (error|warning|information): (.+?)\s*$"
)
# Continuation line ending with (ruleCode) — e.g. '  Attribute "text" is unknown (reportFoo)'
_PYRIGHT_RULE_ONLY_RE = re.compile(
    r"^.*\((\w+)\)\s*$"
)

# ruff first line:  CODE [*] message       (* means auto-fixable by ruff)
_RUFF_HEADER_RE = re.compile(
    r"^\s*([A-Z]+\d+)\s+(\[\*\]\s+)?(.+)$"
)
# ruff location:  --> file:line:col
_RUFF_LOCATION_RE = re.compile(
    r"^\s*-->\s+.*?:(\d+):(\d+)"
)

# bandit issue start:  >> Issue: [CODE:name] message
_BANDIT_ISSUE_RE = re.compile(
    r"^>> Issue: \[([A-Z]\d+:\w+)\] (.+)$"
)
# bandit severity:  Severity: Low   Confidence: High
_BANDIT_SEVERITY_RE = re.compile(
    r"^\s*Severity:\s+(\w+)\s+Confidence:\s+(\w+)"
)
# bandit location:  Location: file:line:col
_BANDIT_LOCATION_RE = re.compile(
    r"^\s*Location:\s+.*?:(\d+):(\d+)"
)

# radon:  X line:col function_name - grade (score)
_RADON_RE = re.compile(
    r"^\s*[FMCA]\s+(\d+):(\d+)\s+(\S+)\s+-\s+([A-F])\s+\((\d+)\)"
)

# fixit:  file@line:col RuleName: description (has autofix)?
# In raw log, stderr lines are prefixed with [stderr]
_FIXIT_RE = re.compile(
    r"^(?:\[stderr\]\s+)?.*?@(\d+):(\d+)\s+(\w+):\s+(.+?)(?:\s+\(has autofix\))?\s*$"
)

# ---------------------------------------------------------------------------
# Severity mapping helpers
# ---------------------------------------------------------------------------

_PYLINT_SEVERITY = {
    "C": "suggestion",  # Convention
    "R": "suggestion",  # Refactor
    "W": "warning",
    "E": "error",
    "F": "error",       # Fatal
    "I": "suggestion",  # Informational
}

_PYRIGHT_SEVERITY = {
    "error": "error",
    "warning": "warning",
    "information": "suggestion",
}

_BANDIT_SEVERITY = {
    "low": "suggestion",
    "medium": "warning",
    "high": "error",
}

# Radon grades: A/B are fine (filtered by -n C flag), C+ means complex
_RADON_SEVERITY = {
    "C": "warning",
    "D": "warning",
    "E": "error",
    "F": "error",
}

# ---------------------------------------------------------------------------
# Noise filters — lines to skip inside tool sections
# ---------------------------------------------------------------------------

_NOISE_PREFIXES = (
    "Exit code:",
    "****",            # pylint module header
    "---",             # pylint/bandit separators
    "Your code has been rated",
    "Found ",          # ruff "Found N error(s)."
    "[*] ",            # ruff "N fixable with --fix"
    "[stderr]",
    "Run started:",
    "Code scanned:",
    "Total lines",
    "Total potential",
    "Run metrics:",
    "Total issues",
    "Undefined:",
    "Low:",
    "Medium:",
    "High:",
    "Files skipped",
    "Test results:",
    "CWE:",
    "More Info:",
    "ERROR:",          # tool not installed
    "No issues found",
    "No issues identified",
    "help:",           # ruff help line
    "\U0001f9fc",      # fixit clean: 🧼
    "\U0001f6e0",      # fixit errors: 🛠️
)

_NOISE_EXACT = {
    "All checks passed!",
    "|",
}


def _is_noise(line: str) -> bool:
    """Return True if the line is boilerplate / not a finding."""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped in _NOISE_EXACT:
        return True
    return any(stripped.startswith(p) for p in _NOISE_PREFIXES)


# ---------------------------------------------------------------------------
# Per-tool parsers
# ---------------------------------------------------------------------------

def _parse_pylint(lines: list[str], file_id: str) -> list[dict]:
    findings = []
    for line in lines:
        m = _PYLINT_RE.match(line.strip())
        if m:
            code = m.group(3)
            findings.append({
                "file": file_id,
                "line": int(m.group(1)),
                "col": int(m.group(2)),
                "tool": "pylint",
                "rule": code,
                "rule_name": m.group(5),
                "severity": _PYLINT_SEVERITY.get(code[0], "warning"),
                "description": m.group(4),
            })
    return findings


def _parse_pyright(lines: list[str], file_id: str) -> list[dict]:
    findings = []
    pending = None  # partial finding awaiting rule from continuation line

    for line in lines:
        stripped = line.strip()

        # Try single-line match first (message ends with (ruleCode))
        m = _PYRIGHT_RE.match(stripped)
        if m:
            if pending:
                # Flush previous pending without a rule
                pending["rule"] = "unknown"
                findings.append(pending)
                pending = None
            findings.append({
                "file": file_id,
                "line": int(m.group(1)),
                "col": int(m.group(2)),
                "tool": "pyright",
                "rule": m.group(5),
                "severity": _PYRIGHT_SEVERITY.get(m.group(3), "error"),
                "description": m.group(4),
            })
            continue

        # Try multi-line: first line without (ruleCode)
        m2 = _PYRIGHT_NOPAREN_RE.match(stripped)
        if m2:
            if pending:
                pending["rule"] = "unknown"
                findings.append(pending)
            pending = {
                "file": file_id,
                "line": int(m2.group(1)),
                "col": int(m2.group(2)),
                "tool": "pyright",
                "rule": None,
                "severity": _PYRIGHT_SEVERITY.get(m2.group(3), "error"),
                "description": m2.group(4),
            }
            continue

        # Continuation line with (ruleCode)
        if pending:
            rule_m = _PYRIGHT_RULE_ONLY_RE.match(stripped)
            if rule_m:
                pending["rule"] = rule_m.group(1)
                findings.append(pending)
                pending = None
            # Other continuation lines (extra context) are ignored

    if pending:
        pending["rule"] = "unknown"
        findings.append(pending)

    return findings


def _parse_ruff(lines: list[str], file_id: str) -> list[dict]:
    findings = []
    current_rule = None
    current_desc = None
    current_fixable = False

    for line in lines:
        stripped = line.strip()

        header = _RUFF_HEADER_RE.match(stripped)
        if header:
            current_rule = header.group(1)
            current_fixable = header.group(2) is not None
            current_desc = header.group(3)
            continue

        loc = _RUFF_LOCATION_RE.match(stripped)
        if loc and current_rule:
            findings.append({
                "file": file_id,
                "line": int(loc.group(1)),
                "col": int(loc.group(2)),
                "tool": "ruff",
                "rule": current_rule,
                "severity": "warning",
                "description": current_desc,
                "ruff_fixable": current_fixable,
            })
            current_rule = None
            current_desc = None
            current_fixable = False

    return findings


def _parse_bandit(lines: list[str], file_id: str) -> list[dict]:
    findings = []
    current_rule = None
    current_desc = None
    current_severity = "warning"

    for line in lines:
        stripped = line.strip()

        issue = _BANDIT_ISSUE_RE.match(stripped)
        if issue:
            current_rule = issue.group(1)
            current_desc = issue.group(2)
            current_severity = "warning"
            continue

        sev = _BANDIT_SEVERITY_RE.match(stripped)
        if sev and current_rule:
            current_severity = _BANDIT_SEVERITY.get(sev.group(1).lower(), "warning")
            continue

        loc = _BANDIT_LOCATION_RE.match(stripped)
        if loc and current_rule:
            findings.append({
                "file": file_id,
                "line": int(loc.group(1)),
                "col": int(loc.group(2)),
                "tool": "bandit",
                "rule": current_rule,
                "severity": current_severity,
                "description": current_desc,
            })
            current_rule = None
            current_desc = None

    return findings


def _parse_radon(lines: list[str], file_id: str) -> list[dict]:
    findings = []
    for line in lines:
        m = _RADON_RE.match(line.strip())
        if m:
            grade = m.group(4)
            findings.append({
                "file": file_id,
                "line": int(m.group(1)),
                "col": int(m.group(2)),
                "tool": "radon",
                "rule": f"CC-{grade}",
                "severity": _RADON_SEVERITY.get(grade, "warning"),
                "description": (
                    f"{m.group(3)} has cyclomatic complexity grade "
                    f"{grade} ({m.group(5)})"
                ),
            })
    return findings


def _parse_fixit(lines: list[str], file_id: str) -> list[dict]:
    findings = []
    for line in lines:
        m = _FIXIT_RE.match(line.strip())
        if m:
            has_autofix = "(has autofix)" in line
            findings.append({
                "file": file_id,
                "line": int(m.group(1)),
                "col": int(m.group(2)),
                "tool": "fixit",
                "rule": m.group(3),
                "severity": "warning",
                "description": m.group(4),
                "fixit_autofix": has_autofix,
            })
    return findings


_TOOL_PARSERS = {
    "pylint": _parse_pylint,
    "pyright": _parse_pyright,
    "ruff": _parse_ruff,
    "bandit": _parse_bandit,
    "radon": _parse_radon,
    "fixit": _parse_fixit,
}

# ---------------------------------------------------------------------------
# XML-like structure splitting
# ---------------------------------------------------------------------------

# Real tags sit at column 0 (<file>) or indented exactly 4 spaces (<tool>).
# Tool output may contain these strings (e.g. test assertions), so we anchor
# the split/match patterns to reject deeply-indented or mid-line occurrences.
_FILE_OPEN_RE = re.compile(r'^<file\s+id="([^"]+)">', re.MULTILINE)
_FILE_CLOSE_RE = re.compile(r'^</file>', re.MULTILINE)
_TOOL_OPEN_RE = re.compile(r'^\s{4}<tool\s+id="([^"]+)">', re.MULTILINE)
_TOOL_CLOSE_RE = re.compile(r'^\s{4}</tool>', re.MULTILINE)


def _split_sections(content: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """Split raw log into [(file_id, [(tool_id, tool_body), ...]), ...]."""
    files = []

    file_opens = list(_FILE_OPEN_RE.finditer(content))
    file_closes = list(_FILE_CLOSE_RE.finditer(content))

    for _i, fo in enumerate(file_opens):
        file_id = fo.group(1)
        block_start = fo.end()
        # Find the matching </file> (the next one after this open)
        block_end = len(content)
        for fc in file_closes:
            if fc.start() > block_start:
                block_end = fc.start()
                break
        file_body = content[block_start:block_end]

        tools = []
        tool_opens = list(_TOOL_OPEN_RE.finditer(file_body))
        tool_closes = list(_TOOL_CLOSE_RE.finditer(file_body))

        for _j, to in enumerate(tool_opens):
            tool_id = to.group(1)
            body_start = to.end()
            # Find matching </tool>
            body_end = len(file_body)
            for tc in tool_closes:
                if tc.start() > body_start:
                    body_end = tc.start()
                    break
            tools.append((tool_id, file_body[body_start:body_end]))

        files.append((file_id, tools))
    return files


def _collect_unparsed(lines: list[str], file_id: str, tool_id: str) -> list[dict]:
    """Collect non-noise lines that no parser matched as a single unparsed finding."""
    remaining = [ln.strip() for ln in lines if not _is_noise(ln)]
    # Also filter pyright summary lines like "8 errors, 0 warnings..."
    remaining = [ln for ln in remaining
                 if not re.match(r"^\d+ errors?, \d+ warnings?, \d+ informations?$", ln)]
    # Filter pyright file-path-only lines (header before findings)
    remaining = [ln for ln in remaining if not re.match(r"^[a-zA-Z]:\\", ln) or " - " in ln]
    # Filter pyright continuation lines (indented extra context for multi-line errors)
    remaining = [ln for ln in remaining
                 if not re.match(r'^(Attribute |Type "|")', ln)]
    # Filter ruff context lines (line numbers with |)
    remaining = [ln for ln in remaining if not re.match(r"^\d+\s*\|", ln)]
    # Filter ruff pointer lines (just | and ^)
    remaining = [ln for ln in remaining if not re.match(r"^[|\s^]+$", ln)]
    # Filter bandit source code context lines (line_num\tcode)
    remaining = [ln for ln in remaining if not re.match(r"^\d+\t", ln)]

    if remaining:
        return [{
            "file": file_id,
            "line": 0,
            "col": 0,
            "tool": tool_id,
            "rule": "unparsed",
            "severity": "warning",
            "description": " | ".join(remaining),
        }]
    return []


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_raw_log(raw_log_path: Path) -> list[dict]:
    """Parse a raw static-analysis log and return a list of finding dicts."""
    content = raw_log_path.read_text(encoding="utf-8")
    file_sections = _split_sections(content)

    all_findings = []
    for file_id, tool_sections in file_sections:
        for tool_id, body in tool_sections:
            lines = body.splitlines()
            parser = _TOOL_PARSERS.get(tool_id)
            if parser:
                findings = parser(lines, file_id)
                all_findings.extend(findings)
                # Check for unparsed leftovers only if there are non-noise
                # lines that the parser didn't capture
                parsed_lines_set = set()
                for f in findings:
                    parsed_lines_set.add(f["line"])
                unparsed = _collect_unparsed(lines, file_id, tool_id)
                if unparsed and not findings:
                    all_findings.extend(unparsed)
            # Skip unknown tools (fixit not installed, etc.)

    return all_findings


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python python_static_analysis_parse_log.py "
              "<raw_log_path> <output_jsonl_path>")
        sys.exit(1)

    raw_log_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not raw_log_path.exists():
        print(f"Error: {raw_log_path} does not exist.")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    findings = parse_raw_log(raw_log_path)

    with open(output_path, "w", encoding="utf-8") as f:
        for finding in findings:
            f.write(json.dumps(finding) + "\n")

    print(f"Parsed {len(findings)} findings -> {output_path}")


if __name__ == "__main__":
    main()
