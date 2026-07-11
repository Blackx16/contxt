"""Contxt ingest (CHA-16) — Gmail + Calendar + Notion → normalized IngestItem[].

The first stage of the pipeline:

    Ingest -> Gateway -> Distill -> Store -> Serve (MCP) -> any AI

`ingest_all()` pulls a volume-capped, normalized `IngestItem[]` from all three
sources. Each item's `.to_gateway_input()` feeds `gateway.classify()` (and then
`gateway.distill.distill_item()`) with no reshaping.

    from ingest import ingest_all
    from gateway.gateway import classify
    items = ingest_all(limit_per_source=10)          # auto: live if creds, else samples
    decisions = [classify(i.to_gateway_input()) for i in items]

Live vs. offline is per-source and auto-falls-back to the on-disk sample dump on
any credential/API failure (see base.SourceAdapter and .env.example). Read-only:
no adapter writes back to any source.
"""
from __future__ import annotations

from typing import Optional

from .base import SourceAdapter
from .calendar import CalendarAdapter
from .gmail import GmailAdapter
from .models import IngestItem
from .notion import NotionAdapter

# One instance per source. Add a source by appending its adapter here.
ADAPTERS: list[SourceAdapter] = [GmailAdapter(), CalendarAdapter(), NotionAdapter()]


def ingest_all(limit_per_source: int = 10, live: Optional[bool] = None) -> list[IngestItem]:
    """Pull from all sources, normalized and capped at `limit_per_source` each.

    live: None = auto (live per-source if credentials configured, else samples),
    True = force live (falls back to samples on error), False = samples only.
    Returns a single `IngestItem[]` ready to feed the Crown-Jewels Gateway.
    """
    items: list[IngestItem] = []
    for adapter in ADAPTERS:
        items.extend(adapter.fetch(limit_per_source, live=live))
    return items


__all__ = [
    "IngestItem",
    "SourceAdapter",
    "GmailAdapter",
    "CalendarAdapter",
    "NotionAdapter",
    "ADAPTERS",
    "ingest_all",
]
