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

Store (CHA-19)
--------------
  SQLite two-tier store at data/contxt.db (created automatically).

    private_cards(id, ciphertext, nonce, created_at)   ← AES-256-GCM encrypted
    shared_cards (id, data JSON,  created_at)           ← cloud-readable

  The server decrypts PRIVATE cards in-process using CONTXT_PRIVATE_KEY.
  Anyone who opens the SQLite file without the key sees opaque ciphertext.

Claude Desktop registration
---------------------------
  Add to ~/Library/Application Support/Claude/claude_desktop_config.json:

    "contxt": {
      "command": "python",
      "args": ["/path/to/contxt/server/mcp_server.py"],
      "env": {
        "FIREWORKS_API_KEY": "<your key>",
        "CONTXT_PRIVATE_KEY": "<base64url 256-bit key from .env>"
      }
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

try:
    from server.crypto_utils import ensure_key, encrypt, decrypt
    from server.store import TwoTierStore
    _STORE_OK = True
except ImportError:
    try:
        from crypto_utils import ensure_key, encrypt, decrypt
        from store import TwoTierStore
        _STORE_OK = True
    except ImportError:
        _STORE_OK = False

app = FastMCP("contxt") if _MCP_OK else None

# ── SQLite store + key (CHA-19) ───────────────────────────────────────────────

_store: TwoTierStore | None = None
_private_key: bytes | None = None

_cards_cache: list[ContextCard] | None = None
_cards_cache_mtime: float = 0.0


def _get_store() -> TwoTierStore:
    global _store, _private_key
    if _store is None:
        if not _STORE_OK:
            raise RuntimeError(
                "Store/crypto not available — run: pip install -r server/requirements.txt"
            )
        db_path = os.getenv("CONTXT_DB", "data/contxt.db")
        _store = TwoTierStore(db_path)
        _private_key = ensure_key()
        if _store.is_empty() and _SCHEMA_OK:
            _seed_store(_store, _private_key)
            counts = _store.counts()
            print(
                f"[contxt] Seeded SQLite store — "
                f"{counts['shared']} shared, {counts['private']} private (encrypted).",
                file=sys.stderr,
            )
    return _store


def _seed_store(store: TwoTierStore, key: bytes) -> None:
    """Populate an empty store from the fixture JSON.

    SHARED cards are inserted as plaintext JSON.
    PRIVATE cards have their content encrypted before storage — only the id
    and created_at are kept in the clear as index columns.
    """
    fixture_cards = load_fixture_cards()
    for card in fixture_cards:
        ca = card.created_at.isoformat()
        if card.tier == Tier.SHARED:
            store.put_shared(
                id=card.id,
                data=card.model_dump(mode="json"),
                created_at=ca,
            )
        else:
            # Encrypt the full card JSON (all fields except id / created_at).
            payload = card.model_dump(mode="json")
            payload.pop("id", None)
            payload.pop("created_at", None)
            ct, nonce = encrypt(json.dumps(payload, ensure_ascii=False), key)
            store.put_private(id=card.id, ciphertext=ct, nonce=nonce, created_at=ca)


# ── card loading ──────────────────────────────────────────────────────────────

def _get_cards() -> list[ContextCard]:
    """Load all cards from SQLite.

    PRIVATE rows are decrypted in-process using the local key — their plaintext
    never leaves this process. Callers that forward cards to cloud models must
    filter to SHARED only (see draft_reply).
    """
    global _cards_cache, _cards_cache_mtime
    if not _SCHEMA_OK:
        return []

    store = _get_store()
    try:
        mtime = store.db_path.stat().st_mtime
    except Exception:
        mtime = 0.0

    if _cards_cache is not None and mtime == _cards_cache_mtime:
        return _cards_cache

    cards: list[ContextCard] = []

    # SHARED — plaintext, cloud-readable
    for data in store.get_all_shared():
        try:
            cards.append(ContextCard.model_validate(data))
        except Exception:
            pass  # skip malformed rows; don't crash the server

    # PRIVATE — decrypt in-process with the local key
    if _private_key:
        for row in store.get_all_private_raw():
            try:
                plaintext = decrypt(row["ciphertext"], row["nonce"], _private_key)
                payload = json.loads(plaintext)
                payload["id"] = row["id"]
                payload["created_at"] = row["created_at"]
                # Decrypted card: clear any lingering encryption block
                payload["encryption"] = None
                cards.append(ContextCard.model_validate(payload))
            except Exception:
                pass  # tampered / wrong key — skip silently

    _cards_cache = cards
    _cards_cache_mtime = mtime
    return cards


def _score_card(card: ContextCard, tokens: list[str]) -> float:
    """Word-boundary keyword score across all text fields of a card."""
    parts = [card.title]
    if card.summary:
        parts.append(card.summary)
    if card.body:
        parts.append(card.body)
    parts.extend(e.value for e in card.entities)
    haystack = " ".join(parts).lower()
    words = set(re.findall(r"\w+", haystack))
    hits = sum(1 for t in tokens if t in words)
    if hits == 0:
        return 0.0
    boost = 0.05 if card.tier == Tier.SHARED else 0.0
    return hits + boost


def _search_cards(query: str, limit: int = 8) -> list[ContextCard]:
    """Keyword-rank cards, return up to `limit`.

    PRIVATE cards are included because this server runs locally — they are
    decrypted in-process and their plaintext is never forwarded to any cloud
    service.

    Fallback: when no keywords match, return the most recent SHARED cards.
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
        shared = [c for c in cards if c.tier == Tier.SHARED]
        return sorted(shared, key=lambda c: c.created_at, reverse=True)[:limit]

    return matched[:limit]


def _card_to_dict(card: ContextCard, *, strip_encryption: bool = True) -> dict:
    d = card.model_dump(mode="json")
    if strip_encryption:
        d.pop("encryption", None)
    return d


# ── Tool cores (importable — shared by the MCP tools AND the HTTP bridge) ──────
#
# The MCP server speaks stdio (Claude Desktop). Browsers can't speak stdio, so
# the browser extension talks to server/http_bridge.py instead — which calls the
# SAME functions below. One source of truth, two transports.


def context_payload(query: str, limit: int = 8, *, include_private: bool = True) -> dict:
    """Return context cards relevant to `query`.

    include_private=True  → serve PRIVATE cards too. Safe for the MCP tool
                            because that path is on-device / local-model.
    include_private=False → SHARED cards only, plus a `private_withheld` count.
                            The HTTP bridge uses this: PRIVATE plaintext never
                            crosses into a cloud-facing surface (the browser
                            injecting context into Claude / ChatGPT / Gemini).
    """
    if not _SCHEMA_OK:
        return {"error": "pydantic not installed — run: pip install -r server/requirements.txt"}

    limit = min(max(limit, 1), 50)

    if include_private:
        cards = _search_cards(query, limit)
        result = [_card_to_dict(c) for c in cards]
        return {"cards": result, "query": query, "total": len(result)}

    # Browser path: rank a generous candidate set, filter to SHARED, and only
    # THEN apply the limit. Filtering before limiting matters — otherwise a query
    # with several matching PRIVATE cards ranked ahead of the SHARED ones would
    # starve the injectable set (the top-`limit` slice could be all private,
    # leaving too few — or zero — shared cards to serve).
    ranked = _search_cards(query, 50)
    shared = [c for c in ranked if c.tier == Tier.SHARED]
    withheld = len(ranked) - len(shared)  # PRIVATE cards that matched THIS query
    shared = shared[:limit]

    payload = {
        "cards": [_card_to_dict(c) for c in shared],
        "query": query,
        "total": len(shared),
        "private_withheld": withheld,
    }
    # Always-on trust signal: how many crown jewels live on-device in total,
    # independent of whether they matched the query. The badge shows this.
    try:
        payload["private_total"] = _get_store().counts()["private"]
    except Exception:
        pass
    return payload


def draft_reply_payload(email: str, max_words: int = 150) -> dict:
    """Draft a context-aware reply using SHARED cards only.

    PRIVATE cards are retrieved locally for the `private_cards_excluded` audit
    count but their content is NEVER forwarded to the cloud drafting model.
    """
    if not _SCHEMA_OK:
        return {"error": "pydantic not installed — run: pip install -r server/requirements.txt"}
    if not _DISTILL_OK:
        return {"error": "gateway.distill not available — run: pip install -r server/requirements.txt"}

    all_cards = _search_cards(email, limit=6)
    shared = [c for c in all_cards if c.tier == Tier.SHARED]
    private_excluded = len(all_cards) - len(shared)

    # Only SHARED fields go into the prompt — private content is never serialized here.
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

    draft = _cloud_draft(email, cards_ctx, max_words=max_words)

    return {
        "draft": draft,
        "used_card_ids": [c.id for c in shared],
        "private_cards_excluded": private_excluded,
    }


# ── MCP tools ─────────────────────────────────────────────────────────────────

if app:

    @app.tool()
    def get_context(query: str, limit: int = 8) -> dict:
        """Return context cards relevant to the query.

        SHARED cards are cloud-readable context about the user.
        PRIVATE cards are served only because this MCP server is local — they
        are decrypted in-process and never forwarded to a cloud model.
        """
        return context_payload(query, limit, include_private=True)

    @app.tool()
    def draft_reply(email: str, max_words: int = 150) -> dict:
        """Draft a context-aware reply to an email or message thread.

        Uses SHARED context cards only — PRIVATE cards are retrieved locally
        for the `private_cards_excluded` audit count but their content is
        NEVER forwarded to the cloud drafting model. This is the privacy
        guarantee: the drafting AI sees only what the user consented to share.

        Set CONTXT_MOCK_GEMMA=1 to draft offline without a cloud API key.
        """
        return draft_reply_payload(email, max_words)


# ── Entrypoint ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if not _MCP_OK:
        print("Install deps first: pip install -r server/requirements.txt")
        sys.exit(1)
    if not _SCHEMA_OK:
        print("Warning: pydantic not installed — schema validation disabled", file=sys.stderr)
    # Eagerly initialize so seeding messages appear before the server silences stderr.
    try:
        _get_store()
        counts = _get_store().counts()
        print(
            f"[contxt] Store ready — {counts['shared']} shared, "
            f"{counts['private']} private (encrypted). "
            f"DB: {_store.db_path}",
            file=sys.stderr,
        )
    except Exception as exc:
        print(f"[contxt] Store init failed: {exc}", file=sys.stderr)
    print("Starting Contxt MCP server…", file=sys.stderr)
    app.run()
