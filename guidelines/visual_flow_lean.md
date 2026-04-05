---
description: A lean version of .claude/code-quality/guidelines/visual_flow.md, for including in coding prompts.
---

# Visual Flow Guidelines (Lean)

These are structural/cosmetic code quality rules. Apply them only when they don't change semantics.

1. **Line Length** — Lines must be no longer than 100 characters; a line should be split at logical boundaries.
2. **Orphan Parentheses** — Parameters should be aligned to the opening parenthesis rather than using a dedented
   parenthesis on its own line, unless the callable name itself is longer than ~30 characters.
3. **Break Long Blocks** — Function bodies and loop bodies should be under ~15 lines; this can be achieved using helper
   functions.
4. **Avoid Deep Nesting** — Code should not have more than 5 indentation levels; this can be achieved using early
   returns/continues or helper functions.
5. **Keep try/except Close** — The try block should contain only the operation that can raise; everythin else should be
   outside.
6. **Class Members Over Parameter Passing** — When several functions share many values, they should be encapsulated as
   methods on a class with shared state in `self`.
7. **In-Class @staticmethod** — Helper functions called only from one class should be `@staticmethod` methods inside that class, not
   module-level functions.
