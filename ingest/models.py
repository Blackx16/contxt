"""Contxt ingest — the normalized `IngestItem` shape (CHA-16).

Every source adapter (Gmail, Calendar, Notion) emits this ONE shape, so the
Crown-Jewels Gateway and the distiller consume ingest output with no reshaping.

The contract with the Gateway is implicit and already frozen:
  * gateway.gateway.classify()   reads item["text"] and item["source"].
  * gateway.distill.distill_item() reads item["source"] (must be
    gmail/calendar/notion), item["text"], and optional item["_tier"].

`IngestItem.to_gateway_input()` serializes to exactly that dict — same field
names, no renaming, no nesting — so `classify(item.to_gateway_input())` and
`distill_item(item.to_gateway_input())` just work. `source` reuses the frozen
`schema.models.Source` enum so there is a single source-of-truth for the three
connector names.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from schema.models import Source


class IngestItem(BaseModel):
    """One raw item pulled from a source, normalized for the Gateway.

    This is the pipeline's *pre-classification* unit (before a tier decision and
    before distillation into a ContextCard). It is intentionally lossless-ish:
    `text` carries what the Gateway classifies on, and `meta` preserves the
    source-specific fields (sender, attendees, url…) for later distillation.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)  # stable, source-prefixed, e.g. "gmail:19f4bbf7…"
    source: Source  # gmail | calendar | notion (frozen wire enum)
    text: str  # the text the Gateway classifies (subject+body / title+notes / page)
    title: str = Field(min_length=1, max_length=300)  # short human label
    timestamp: Optional[datetime] = None  # when the item occurred / was created (UTC)
    meta: dict[str, Any] = Field(default_factory=dict)  # source extras: from, attendees, url…

    def to_gateway_input(self) -> dict[str, Any]:
        """The exact dict `gateway.classify()` / `distill.distill_item()` consume.

        No reshaping: `text` and `source` keep their names; the extra keys
        (`id`, `title`, `timestamp`, `meta`) are simply ignored by the Gateway's
        `item.get(...)` access. `source` serializes to its lowercase wire value
        ("gmail" / "calendar" / "notion"), which is what the distiller's
        source allow-list checks against.
        """
        return self.model_dump(mode="json")
