---
author: Iddo Lev
last_updated: 2026-03-10
description: Improve code quality according to code quality guidelines
---

Read all markdown files under the `instructions/` folder. These contain code quality guidelines.

Then, for each Python file under the `scripts/` folder, review it against all the guidelines from the instruction files. 
For each guideline violation found, fix the code to comply with the guideline,
but do so very cautiously,without changing the code's operation and meaning.
After fixing, show a summary of what was changed and which guidelines were applied.

CRITICAL: The guidelines instruct about cosmetic/structural changes only! 
You must preserve the exact semantic behavior of the original code. 
If applying a guideline would require changing logic, control flow, return values, side effects, 
error handling behavior, or API contracts - suggest the improvement instead of actually doing it. 
When in doubt, leave the code unchanged, and ask the user.
