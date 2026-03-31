"""Shared utilities for the code quality loop modules."""
from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
