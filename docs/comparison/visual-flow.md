# Comparison of Visual Flow Guidelines to Alternatives

Comparison of `.claude/code-quality/guidelines/visual_flow.md` to alternatives. 

Below is information obtained from claude.ai about alternatives.

## Summary

Existing tools can *detect* some of these issues but cannot *fix* most of them. Several guidelines are essentially
unaddressed by current tooling and are well-suited for an LLM-based refactoring tool rather than a traditional
linter/formatter.

| # | Guideline | Existing Tool? |
|---|-----------|---------------|
| 1 | Line splits (logical places) | ⚠️ Partial (`black`, `flake8`) — style differs |
| 2 | Orphan parens only when necessary | ❌ No — `black` enforces the opposite |
| 3 | Break long blocks into helpers | ⚠️ Detection only (`flake8-functions`, `pylint`) |
| 4 | Avoid deep nesting | ⚠️ Detection only (`pylint`, `flake8-cognitive-complexity`) |
| 5 | Keep `try`/`except` close | ❌ Not meaningfully covered |
| 6 | Use class members vs. passing values | ❌ No (weak hint: `pylint` R0913) |
| 7 | Class helpers as `@staticmethod` | ⚠️ Partial (`pylint` R0201, but not the move-into-class part) |

---

## 1. Line Splits (max 100 chars, split at logical places)

**⚠️ Partially covered.**

Tools like **`black`** and **`autopep8`** enforce line length limits and will wrap long lines. However, they use their own
opinionated style (e.g., `black` always uses orphan parentheses), which may conflict with guideline 2. **`flake8`** can *detect*
lines over a limit (`E501`) but won't fix them. No tool handles the comprehension-splitting style described in this
guideline the way it prescribes.

---

## 2. Use Orphan Parentheses Only When Necessary

**❌ Not covered.**

**`black`** actively uses orphan parentheses, which is the *opposite* of what this guideline wants for short function names.
There is no mainstream tool that implements this nuanced rule (align to opening paren for short names; use orphan parens
only for long names > 30 characters).

---

## 3. Break Long/Complex Sections Into Smaller Blocks (≤15 lines per block)

**⚠️ Detection only.**

**`flake8`** with the `flake8-functions` plugin can flag functions exceeding a line count. **`pylint`** has `too-many-statements`. But no tool *automatically
refactors* long blocks into helper functions — that requires semantic understanding of the code.

---

## 4. Avoid Deep Nesting (max 5 levels)

**⚠️ Detection only.**

**`flake8`** with `flake8-cognitive-complexity` or **`pylint`** (`too-many-nested-blocks`) can detect excessive nesting. No tool automatically refactors it using the early-`continue`
or helper-function extraction patterns described in this guideline.

---

## 5. Keep `try` and `except` Close Together

**❌ Not meaningfully covered.**

**`pylint`** has `W0703` (broad-except) and some related warnings, but there is no tool that specifically flags or fixes a large
`try` block. This guideline is largely unaddressed by existing tooling.

---

## 6. Use Class Members Instead of Passing Values Around

**❌ Not covered.**

This is a higher-level design/architecture refactoring that no linter or formatter addresses. It requires understanding
data flow across functions, which is beyond static analysis tools. **`pylint`** can flag `too-many-arguments` (R0913) as a weak hint in this
direction, but it cannot suggest or apply the class-encapsulation pattern.

---

## 7. Class Helpers Should Use In-Class `@staticmethod` Instead of Module-Level Functions

**⚠️ Partially covered.**

**`pylint`** has `R0201` / `no-self-use`, which suggests a method could be a `@staticmethod`. However, the specific pattern here — detecting that a
*module-level* function is only called from within one class and should be moved inside it — is not handled by any
existing tool.
