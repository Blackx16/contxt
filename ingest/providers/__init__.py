"""Live source providers for ingest adapters (Google APIs, Notion REST).

Kept separate from the adapters so the normalize logic stays pure and testable,
and so a missing credential degrades to the offline sample dump instead of
crashing the pipeline.
"""
from __future__ import annotations

from .errors import LiveAuthUnavailable

__all__ = ["LiveAuthUnavailable"]
