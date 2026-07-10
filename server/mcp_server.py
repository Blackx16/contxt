"""Contxt MCP server — serves context to any AI client.

Tools
-----
  get_context(query, limit?)
      Return relevant context cards. SHARED cards are cloud-readable.
      PRIVATE cards are decrypted locally and served here only because this
      server runs on-device — their plaintext never leaves the machine.

  draft_reply(email, max_words?)
      Draft a context-aware reply using cloud Gemma + SHARED context cards.
      PRIVATE cards are never sent to the cloud model.

Store
-----
  Fixture JSON for v1 demo (schema/fixtures/cards.json).
  Swap _get_cards() for a real SQLite + vector store in prod.

Claude Desktop registration
---------------------------
  Add to ~/Library/Application Support/Claude/claude_desktop_config.json:

    "contxt": {
      "command": "python",
      "args": ["/path/to/contxt/server/mcp_server.py"],
      "env": { "FIREWORKS_API_KEY": "<your key>" }
    }

  Then restart Claude Desktop and call: get_context("what am I working on")
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

# Allow `python server/mcp_server.py` from the repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env if present (dev convenience)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass

try:
    from mcp.server.fastmcp import FastMCP
    _MCP_OK = True
except ImportError:
    FastMCP = None
    _MCP_OK = False

try:
    from schema.models import ContextCard, Tier, load_fixture_cards
    _SCHEMA_OK = True
except ImportError:
    _SCHEMA_OK = False

try:
    from gateway.distill import distill_draft as _cloud_draft
    _DISTILL_OK = True
except ImportError:
    _DISTILL_OK = False

app = FastMCP("contxt") if _MCP_OK else None

# ── In-memory card store (fixture-backed for demo) ────────────────────────────

_CARDS: list[ContextCard] | None = None


def _get_cards() -> list[ContextCard]:
    global _CARDS
    if _CARDS is None:
        if _SCHEMA_OK:
            _CARDS = load_fixture_cards()
        else:
            _CARDS = []
    return _CARDS


def _score_card(card: ContextCard, tokens: list[str]) -> float:
    """Word-boundary keyword score across all text fields of a card."""
    parts = [card.title]
    if card.summary:
        parts.append(card.summary)
    if card.body:
        parts.append(card.body)
    parts.extend(e.value for e in card.entities)
    haystack = " ".join(parts).lower()
    # Use word sets to prevent 'emi' matching inside 'reminder' etc.
    words = set(re.findall(r"\w+", haystack))
    hits = sum(1 for t in tokens if t in words)
    if hits == 0:
        return 0.0
    # SHARED cards get a small tiebreaker boost so they rank ahead of PRIVATE on ties
    boost = 0.05 if card.tier == Tier.SHARED else 0.0
    return hits + boost


def _search_cards(query: str, limit: int = 8) -> list[ContextCard]:
    """Keyword-rank cards, return up to `limit`.

    PRIVATE cards are included because this server runs locally — they are
    decrypted in-process and their plaintext is never forwarded to any cloud
    service.

    Fallback: when no keywords match (e.g. "what am I working on"), return
    the most recent SHARED cards so the query always returns useful context.
    """
    cards = _get_cards()
    tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]
    if not tokens:
        shared = [c for c in cards if c.tier == Tier.SHARED]
        return sorted(shared, key=lambda c: c.created_at, reverse=True)[:limit]

    scored = [(c, _score_card(c, tokens)) for c in cards]
    ranked = sorted(scored, key=lambda x: x[1], reverse=True)
    matched = [c for c, s in ranked if s > 0]

    if not matched:
        # No keyword hits — fall back to most recent SHARED cards for general context
        shared = [c for c in cards if c.tier == Tier.SHARED]
        return sorted(shared, key=lambda c: c.created_at, reverse=True)[:limit]

    return matched[:limit]


def _card_to_dict(card: ContextCard, *, strip_encryption: bool = True) -> dict:
    d = card.model_dump(mode="json")
    if strip_encryption:
        d.pop("encryption", None)
    return d


# ── MCP tools ─────────────────────────────────────────────────────────────────

if app:

    @app.tool()
    def get_context(query: str, limit: int = 8) -> dict:
        """Return context cards relevant to the query.

        SHARED cards are cloud-readable context about the user.
        PRIVATE cards are served only because this MCP server is local — they
        are decrypted in-process and never forwarded to a cloud model.
        """
        if not _SCHEMA_OK:
            return {"error": "pydantic not installed — run: pip install -r server/requirements.txt"}

        cards = _search_cards(query, min(max(limit, 1), 50))
        result = [_card_to_dict(c) for c in cards]

        return {
            "cards": result,
            "query": query,
            "total": len(result),
        }

    @app.tool()
    def draft_reply(email: str, max_words: int = 150) -> dict:
        """Draft a context-aware reply to an email.

        Uses SHARED context cards only — PRIVATE cards are intentionally
        excluded from cloud Gemma calls to protect user privacy.
        """
        if not _SCHEMA_OK:
            return {"error": "pydantic not installed — run: pip install -r server/requirements.txt"}

        all_cards = _search_cards(email, limit=6)
        # Privacy guard: only SHARED cards go to the cloud model
        shared = [c for c in all_cards if c.tier == Tier.SHARED]

        cards_ctx = json.dumps(
            [
                {
                    "title": c.title,
                    "summary": c.summary,
                    "body": c.body,
                    "entities": [e.model_dump() for e in c.entities],
                }
                for c in shared
            ],
            indent=2,
        )

        if _DISTILL_OK and os.getenv("FIREWORKS_API_KEY"):
            draft = _cloud_draft(email, cards_ctx, max_words=max_words)
        else:
            draft = (
                "[cloud Gemma not wired — set FIREWORKS_API_KEY in .env]\n\n"
                f"Relevant context ({len(shared)} SHARED card(s)):\n{cards_ctx}"
            )

        return {
            "draft": draft,
            "used_card_ids": [c.id for c in shared],
            "private_cards_excluded": len(all_cards) - len(shared),
        }


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _MCP_OK:
        print("Install deps first: pip install -r server/requirements.txt")
        sys.exit(1)
    if not _SCHEMA_OK:
        # NB: never write to stdout — it is the stdio JSON-RPC channel. Logs → stderr.
        print("Warning: pydantic not installed — schema validation disabled", file=sys.stderr)
    print("Starting Contxt MCP server…", file=sys.stderr)
    app.run()
