---
author: Iddo Lev
last_updated: 2026-03-10
description: Improve code quality according to code quality guidelines
---

The files under the `instructions/code_quality_guidelines/` folder contain code quality guidelines.
Follow the instructions below in order to 

Do the following: 

- for each python file <filename> under the `scripts/` folder 
  create an empty file `tmp/quality_review/<filename>.log` with yaml frontmatter containing "source: " + filepath, and
- for each instruction file in `instructions/code_quality_guidelines/`:
- for each rule in the instruction file:
- apply the rule on the python file (<filename>), and
- for each violation found, fix the code to comply with the rule
  and immediately report what you did by appending text to tmp/quality_review/<filename>.log 
  but do the fix very cautiously, without changing the code's operation and meaning,
 
CRITICAL: The guidelines instruct about cosmetic/structural changes only! 
You must preserve the exact semantic behavior of the original code. 
If applying a guideline would require changing logic, control flow, return values, side effects, 
error handling behavior, or API contracts - suggest the improvement (in the `tmp/quality_review/` log file) 
instead of actually doing it. 
When in doubt, leave the code unchanged, and just suggest.
