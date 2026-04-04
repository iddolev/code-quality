# Other Issue Types

Examples of issues that don't fit the main categories but may still
warrant reporting under the "other" type.

## Compatibility / Portability

- Uses `os.path` with hardcoded `/` separator — breaks on Windows
- Calls API deprecated in Python 3.12, removed in 3.14
- Relies on dict insertion ordering but targets Python 3.6 where it's implementation detail
- Uses `asyncio.get_event_loop()` which warns in 3.10+
- Platform-specific syscall with no guard or fallback

## Dependency management

- Circular import between two modules
- Import at module level that's only needed in one rarely-called function (slows startup)
- Pinned to an abandoned library with known CVE
- Two libraries doing the same thing (e.g., `requests` and `httpx` both imported)

## Internationalization / Encoding

- `open()` without explicit encoding — platform-dependent behavior
- User-facing strings hardcoded in English with no i18n hook
- Assumes ASCII in string processing (`ord(c) < 128`)
- Datetime naive where timezone-aware is needed (e.g., storing UTC but comparing to local time)

## Compliance / Legal

- License header missing on file that ships to customers
- GPL-licensed dependency used in proprietary codebase
- PII logged without redaction

## Build / Packaging

- `__init__.py` missing, package won't import correctly
- Entry point in `setup.cfg` points to renamed function
- Data files not included in `package_data`, missing at runtime

## Graceful lifecycle

- No signal handler for SIGTERM — container kill loses in-flight work
- `atexit` cleanup registered but not idempotent, crashes on double-call
- Background thread not marked daemon, prevents clean process exit

## Determinism / Reproducibility

- Set iteration used for output ordering — non-deterministic
- `random` calls without seed in code that should be reproducible
- Floating-point equality comparison (`==`) instead of tolerance check
- Hash-based sharding produces different results across Python restarts (hash randomization)
