"""Contxt shared contract — Python (pydantic v2) models for the MCP server + gateway.

Canonical source of truth is ./context_card.schema.json. Keep this file in sync with it
and with ./types.ts. Frozen contract: change all three together, or not at all.

Usage:
    from schema.models import ContextCard, load_fixture_cards
    cards = load_fixture_cards()            # parses schema/fixtures/cards.json
"""
from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class Tier(str, Enum):
    PRIVATE = "private"
    SHARED = "shared"


class Source(str, Enum):
    GMAIL = "gmail"
    CALENDAR = "calendar"
    NOTION = "notion"


EntityType = Literal[
    "person", "org", "date", "money", "location", "email", "phone", "url", "misc"
]


class Entity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: EntityType
    value: str = Field(min_length=1)


class Encryption(BaseModel):
    """Present only on PRIVATE cards at rest in the cloud blind relay."""

    model_config = ConfigDict(extra="forbid")
    alg: Literal["AES-256-GCM"] = "AES-256-GCM"
    iv: str
    ciphertext: str
    key_ref: Optional[str] = None


class ContextCard(BaseModel):
    """One distilled unit of context. See context_card.schema.json for field docs."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^card_[0-9a-fA-F-]{8,}$")
    tier: Tier
    source: Source
    title: str = Field(min_length=1, max_length=200)
    summary: Optional[str]
    body: Optional[str]
    entities: list[Entity]
    sensitivity_score: float = Field(ge=0.0, le=1.0)
    created_at: datetime
    embedding_ref: Optional[str]
    encryption: Optional[Encryption] = None
    meta: Optional[dict[str, Any]] = None


class TierDecision(BaseModel):
    """What the Crown-Jewels Gateway emits per ingested item (maps to gateway.Decision)."""

    model_config = ConfigDict(extra="forbid")
    tier: Tier
    sensitivity_score: float = Field(ge=0.0, le=1.0)
    categories: list[str] = Field(default_factory=list)
    reason: str = ""
    source_ref: Optional[str] = None


# ---- MCP tool I/O ----


class GetContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=50)


class GetContextResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cards: list[ContextCard] = Field(default_factory=list)


class DraftReplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=1)
    max_words: int = Field(default=150, ge=1, le=1000)


class DraftReplyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    draft: str
    used_card_ids: list[str] = Field(default_factory=list)


# ---- fixture helpers ----

_FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture_cards() -> list[ContextCard]:
    """Parse schema/fixtures/cards.json into validated ContextCard objects."""
    raw = json.loads((_FIXTURES / "cards.json").read_text())
    return [ContextCard.model_validate(c) for c in raw]


if __name__ == "__main__":
    cards = load_fixture_cards()
    print(f"OK — parsed {len(cards)} fixture cards:")
    for c in cards:
        enc = " [encrypted]" if c.encryption else ""
        print(f"  {c.tier.value:8} {c.source.value:9} {c.title}{enc}")
