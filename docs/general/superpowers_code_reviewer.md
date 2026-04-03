# superpowers:code-reviewer Agent

## Source

**File:** `C:\Users\Iddo\.claude\plugins\cache\claude-plugins-official\superpowers\5.0.6\agents\code-reviewer.md`

**Type:** Agent (not a skill) — invoked via the `Agent` tool with `subagent_type: "superpowers:code-reviewer"`

---

## Overview

A **Senior Code Reviewer** agent triggered after a major project step is completed. It runs as a subagent (inheriting the parent model) and performs a structured review across 6 areas.

---

## What It Does

### 1. Plan Alignment (lines 12–16)
- Compares implementation against the original planning document or step description
- Identifies deviations from the planned approach, architecture, or requirements
- Assesses whether deviations are justified improvements or problematic departures
- Verifies that all planned functionality has been implemented

### 2. Code Quality Assessment (lines 18–23)
- Reviews code for adherence to established patterns and conventions
- Checks for proper error handling, type safety, and defensive programming
- Evaluates code organization, naming conventions, and maintainability
- Assesses test coverage and quality of test implementations
- Looks for potential security vulnerabilities or performance issues

### 3. Architecture and Design Review (lines 25–29)
- Ensures implementation follows SOLID principles and established architectural patterns
- Checks for proper separation of concerns and loose coupling
- Verifies that the code integrates well with existing systems
- Assesses scalability and extensibility considerations

### 4. Documentation and Standards (lines 31–34)
- Verifies that code includes appropriate comments and documentation
- Checks file headers, function documentation, and inline comments
- Ensures adherence to project-specific coding standards and conventions

### 5. Issue Identification and Recommendations (lines 36–41)
Categorizes findings as:
- **Critical** — must fix
- **Important** — should fix
- **Suggestions** — nice to have

For each issue: provides specific examples, actionable recommendations, and code examples when helpful.

### 6. Communication Protocol (lines 43–47)
- If significant plan deviations found: asks the coding agent to review and confirm
- If the plan itself has issues: recommends plan updates
- For implementation problems: provides clear guidance on fixes needed
- Always acknowledges what was done well before highlighting issues

---

## When It's Invoked

Automatically by the main Claude agent after completing a major numbered step in an implementation plan (e.g., "step 3 of our plan is done"). The `superpowers:requesting-code-review` skill drives when/how it gets called.

---

## Q&A from Conversation

**Q: Is superpowers:code-reviewer defined as an agent or a skill?**
A: It is defined as an **agent**, not a skill. It appears in the Agent tool's available agent types list.

**Q: Where exactly are the "Code Quality" instructions?**
A: `C:\Users\Iddo\.claude\plugins\cache\claude-plugins-official\superpowers\5.0.6\agents\code-reviewer.md`, lines 18–23.

---

## My opinion

Its scope is way too broad, does too many things, and probably not high quality.
E.g. the SOLID part requires a separate agent/skill or even more than one.
