# Issue Types

Every issue must be classified with exactly one of the following types.

## edge-case

Missing or incorrect treatment of edge cases. The code works for typical
inputs but fails on boundary values, empty collections, nested structures,
unusual but valid inputs, or other non-mainstream scenarios.

## correctness

Correctness bugs *other than edge cases*. Wrong logic, wrong ordering of
operations, incorrect algorithm, wrong return value, or any defect that
produces incorrect results on normal, expected inputs.

## error-handling

Missing or incorrect error handling. Unhandled exceptions on fallible
operations (file I/O, network, parsing), swallowed errors, generic
catch-all handlers that hide root causes, or error paths that leave the
system in an inconsistent state.

## documentation

Missing or misleading documentation. Public functions or classes without
docstrings, outdated comments that contradict the code, or missing
explanation of non-obvious behavior.

## performance

Inefficient code that wastes time or memory. E.g. O(n^2) loops where O(n) is
possible, repeated compilation of regexes, redundant re-reads of files,
unnecessary copies of large data structures, or hot paths with avoidable
allocations.

## security

Security vulnerabilities. Injection (SQL, command, path traversal), XSS,
unsafe deserialization, secrets in source code, overly permissive file
or network access, or other OWASP-style risks.

## concurrency

Race conditions, deadlocks, or unsafe concurrent access. Shared mutable
state without synchronization, time-of-check-to-time-of-use (TOCTOU)
bugs, or thread-safety assumptions violated by parallel execution.

## api-contract

API contract violations. A function returns inconsistent types, mutates
its input unexpectedly, silently ignores parameters, or otherwise violates
the contract its callers reasonably expect.

## dead-code

Dead or unreachable code. Branches that can never execute, unused
parameters that suggest an incomplete refactor, vestigial imports, or
conditions that are always true or always false.

## resource-leak

Resource leaks. Unclosed file handles, database connections, sockets,
or subprocesses; unbounded memory growth on large inputs; or missing
cleanup in error paths.

## maintainability

Maintainability and complexity problems. Deeply nested logic, overly long
functions, duplicated code that should be a shared helper, or tangled
control flow that makes the code hard to reason about and modify.

## hardcoding

Hardcoded values that should be configurable. Magic numbers, hardcoded
file paths, embedded credentials or environment-specific values, or
thresholds and limits with no named constant or configuration option.

## observability

Logging and observability gaps. Missing logging on error paths, unhelpful
error messages that omit context, excessive or noisy logging that drowns
out useful signals, or missing metrics on critical operations.

## type-safety

Type-safety issues. Implicit None returns used as valid values, unchecked
Optional access, wrong type assumptions, isinstance checks that miss
subtypes, or dynamic attribute access without guards.

## other

Issues that do not fit neatly into any of the above categories. Use this
sparingly and only when no other type is a reasonable match.
