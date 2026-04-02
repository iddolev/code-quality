# Visual Flow Guidelines

## Purpose

This file contains basic guidelines for how to correctly structure a code file.
Although examples are shown in Python, the principles apply to any programming language.

## Critical Instructions:

<CRITICAL> 
The guidelines instruct about cosmetic/structural changes only! 
You must preserve the exact semantic behavior of the original code:
the output for a given input should remain the same.
If applying a guideline would require changing control flow, return values, side effects, 
or error handling behavior - do so very carefully.
</CRITICAL>

---

## Table of Contents


TBD

5. Error printing - should be to stderr or a log, not to stdout
6. regex
   - sometimes string instead of compiling
   - sometimes re.compile done inside a function instead of once at module level