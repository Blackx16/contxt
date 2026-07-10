"""Shared errors for ingest providers."""
from __future__ import annotations


class LiveAuthUnavailable(RuntimeError):
    """Raised when a live source pull can't authenticate (missing/invalid creds).

    Adapters catch this and fall back to the on-disk sample dump so the demo
    never crashes on a missing token.
    """
