"""Cloud distillation — SHARED-tier items → context cards.

Uses Llama 3.3 70B on Fireworks AI, which serves inference on AMD Instinct
MI300X GPUs (FireAttention V3, AMD's clean-sheet kernel). PRIVATE-tier items are
BLOCKED — they must never reach this function.

AMD compute: the Fireworks credits come from the AMD AI Developer Program and
Fireworks runs Llama on AMD Instinct. The `contxt:cloud_llm` INFO log lines
below capture that AMD-backed inference for the submission.

Boundary contract (CHA-15): the raw model output is *parsed* into the frozen
`schema.models.ContextCard` here — never trusted as-is. Illegal states (bad
entity types, out-of-range scores, extra keys, wrong casing) are coerced or
rejected at this single boundary, so everything downstream can assume a
schema-valid card. "Parse, don't validate."
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from schema.models import ContextCard, Entity, Source, Tier

logger = logging.getLogger(__name__)

_FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
_DEFAULT_MODEL = os.getenv(
    "CONTXT_CLOUD_MODEL", "accounts/fireworks/models/llama-v3p3-70b-instruct"
)
_AMD_ENDPOINT = os.getenv("AMD_CLOUD_ENDPOINT", "")

# Closed enums from the frozen schema — used to coerce fuzzy model output.
_VALID_SOURCES = {s.value for s in Source}
_VALID_ENTITY_TYPES = {
    "person", "org", "date", "money", "location", "email", "phone", "url", "misc",
}

_CACHE_DIR = Path(__file__).parent / ".cache"
_CACHE_FILE = _CACHE_DIR / "gemma_cache.json"

# ── Prompts ───────────────────────────────────────────────────────────────────

_DISTILL_SYSTEM = """\
You are a personal-context distiller. Given a raw personal data item (email,
calendar event, or note), extract a structured context card for the Contxt MCP
server. Output ONLY valid JSON — no markdown fences, no preamble.

Required schema:
{
  "title": "short descriptive title, max 80 chars",
  "summary": "1-2 sentence summary",
  "body": "optional longer detail, or null",
  "entities": [{"type": "person|org|date|money|location|email|phone|url|misc", "value": "string"}],
  "sensitivity_score": 0.0,
  "meta": {
    "identity": "who this is about",
    "current_projects": ["..."],
    "preferences": ["..."],
    "key_relationships": ["..."],
    "active_focus": "what needs immediate attention"
  }
}
sensitivity_score must be between 0.0 (public) and 1.0 (very sensitive).\
"""

_DRAFT_SYSTEM = """\
You are a helpful assistant that drafts concise email replies. You have access
to the user's context cards (summaries of their work, relationships, and
preferences). Use them to make the reply relevant and personal.

Keep the reply under {max_words} words. Output ONLY the reply body — no
subject line, no "Dear X", no signature unless explicitly asked.\
"""


# ── Offline / mock mode ───────────────────────────────────────────────────────

def _mock_enabled() -> bool:
    """Mock the cloud call when explicitly asked, or when no endpoint is wired.

    `CONTXT_MOCK_GEMMA=1` forces mock (used by tests + offline demo).
    `CONTXT_MOCK_GEMMA=0` forces the real call even with no key (will error).
    Default: mock only when there is neither a Fireworks key nor an AMD endpoint,
    so the pipeline degrades gracefully offline instead of crashing the demo.
    """
    flag = os.getenv("CONTXT_MOCK_GEMMA")
    if flag == "1":
        return True
    if flag == "0":
        return False
    return not (os.getenv("FIREWORKS_API_KEY") or _AMD_ENDPOINT)


def _mock_response(system: str, user: str) -> str:
    """Deterministic canned response so offline runs still exercise the pipeline."""
    if "distiller" in system:
        # First non-empty line of the item as a cheap title.
        item_line = ""
        for line in user.splitlines():
            line = line.strip()
            if line and not line.lower().startswith(("source:", "item:")):
                item_line = line
                break
        return json.dumps(
            {
                "title": (item_line or "Context item")[:80],
                "summary": item_line[:200] or None,
                "body": None,
                "entities": [],
                "sensitivity_score": 0.2,
                "meta": {"mock": True},
            }
        )
    return "[mock draft] Thanks for your note — I'll follow up shortly."


# ── Response cache (avoid live rate limits during the demo) ────────────────────

_cache: Optional[dict[str, str]] = None


def _cache_enabled() -> bool:
    return os.getenv("CONTXT_CACHE") != "0"


def _load_cache() -> dict[str, str]:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(_CACHE_FILE.read_text()) if _CACHE_FILE.exists() else {}
        except (json.JSONDecodeError, OSError):
            _cache = {}
    return _cache


def _cache_key(system: str, user: str, model: str, max_tokens: int) -> str:
    h = hashlib.sha256()
    h.update(f"{model}\x00{max_tokens}\x00{system}\x00{user}".encode())
    return h.hexdigest()


def _cache_get(key: str) -> Optional[str]:
    if not _cache_enabled():
        return None
    return _load_cache().get(key)


def _cache_put(key: str, value: str) -> None:
    if not _cache_enabled():
        return
    cache = _load_cache()
    cache[key] = value
    try:
        _CACHE_DIR.mkdir(exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(cache, indent=2))
    except OSError:
        logger.warning("contxt:cache_write_failed path=%s", _CACHE_FILE)


# ── API call ──────────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = os.getenv("FIREWORKS_API_KEY", "")
    if not key:
        raise RuntimeError(
            "FIREWORKS_API_KEY not set — add it to .env, export it, or set "
            "CONTXT_MOCK_GEMMA=1 to run the pipeline offline."
        )
    return key


def _call_cloud_llm(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 512,
) -> str:
    """POST to Fireworks (or AMD Dev Cloud) and return the assistant text.

    Cache-first, then mock (offline), then the real HTTP call. The INFO log
    line captures model ID + usage tokens for the AMD prize submission.
    """
    endpoint = _AMD_ENDPOINT or _FIREWORKS_URL
    chosen_model = model or _DEFAULT_MODEL
    key = _cache_key(system, user, chosen_model, max_tokens)

    cached = _cache_get(key)
    if cached is not None:
        logger.info("contxt:cloud_llm_cache_hit key=%s", key[:12])
        return cached

    if _mock_enabled():
        logger.info("contxt:cloud_llm endpoint=mock model=%s mock=1", chosen_model)
        text = _mock_response(system, user)
        _cache_put(key, text)
        return text

    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": chosen_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }

    logger.info("contxt:cloud_llm endpoint=%s model=%s", endpoint, chosen_model)
    resp = httpx.post(endpoint, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info(
        "contxt:cloud_llm_ok id=%s usage=%s",
        data.get("id"),
        data.get("usage"),
    )
    text = data["choices"][0]["message"]["content"].strip()
    _cache_put(key, text)
    return text


# ── Parsing the model output into the frozen schema ───────────────────────────

def _parse_model_json(raw: str, fallback_text: str) -> dict[str, Any]:
    """Extract the JSON object the model was asked to emit, tolerating fences."""
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 2 else parts[-1].strip()
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        logger.warning("contxt:distill_parse_error raw=%s", raw[:300])
    # Fallback: a minimal card built from the raw item text.
    return {
        "title": fallback_text[:80],
        "summary": fallback_text[:200] if fallback_text else None,
        "body": None,
        "entities": [],
        "sensitivity_score": 0.3,
        "meta": {},
    }


def _coerce_entities(raw: Any) -> list[Entity]:
    """Keep only well-formed entities; unknown types collapse to 'misc'."""
    out: list[Entity] = []
    if not isinstance(raw, list):
        return out
    for e in raw:
        if not isinstance(e, dict):
            continue
        value = e.get("value")
        if not isinstance(value, str) or not value.strip():
            continue
        etype = e.get("type", "misc")
        if etype not in _VALID_ENTITY_TYPES:
            etype = "misc"
        out.append(Entity(type=etype, value=value.strip()))
    return out


def _clamp_score(value: Any, default: float = 0.3) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _to_context_card(card_data: dict[str, Any], source: str, text: str) -> dict[str, Any]:
    """Parse fuzzy model output into a schema-valid ContextCard dict.

    This is the boundary: the returned dict is guaranteed to satisfy
    context_card.schema.json because it round-trips through the pydantic model.
    """
    title = (card_data.get("title") or text[:80] or "Untitled").strip()[:200] or "Untitled"
    summary = card_data.get("summary")
    body = card_data.get("body")
    meta = card_data.get("meta") if isinstance(card_data.get("meta"), dict) else None

    card = ContextCard(
        id=f"card_{uuid.uuid4()}",
        tier=Tier.SHARED,
        source=Source(source),
        title=title,
        summary=summary if isinstance(summary, str) else None,
        body=body if isinstance(body, str) else None,
        entities=_coerce_entities(card_data.get("entities")),
        sensitivity_score=_clamp_score(card_data.get("sensitivity_score")),
        created_at=datetime.now(timezone.utc),
        embedding_ref=None,
        encryption=None,
        meta=meta,
    )
    return card.model_dump(mode="json")


# ── Public API ────────────────────────────────────────────────────────────────

def distill_item(item: dict[str, Any]) -> dict[str, Any]:
    """Distill a SHARED-tier raw item into a schema-valid context-card dict.

    Raises ValueError if the item carries `_tier=private` (belt-and-suspenders
    privacy guard) or if `source` is not one of gmail/calendar/notion.
    """
    if str(item.get("_tier", "shared")).lower() == "private":
        raise ValueError(
            "distill_item called with a PRIVATE item — aborting to protect "
            "user privacy. Only call this on SHARED-tier items."
        )

    source = item.get("source", "")
    if source not in _VALID_SOURCES:
        raise ValueError(
            f"distill_item: unknown source {source!r}; expected one of "
            f"{sorted(_VALID_SOURCES)}."
        )

    text = item.get("text", "")
    user_prompt = f"Source: {source}\n\nItem:\n{text[:2000]}"
    raw = _call_cloud_llm(_DISTILL_SYSTEM, user_prompt)
    card_data = _parse_model_json(raw, text)
    return _to_context_card(card_data, source, text)


def distill_batch(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Distill many SHARED items. PRIVATE items are skipped (never sent to cloud).

    Returns the list of schema-valid cards. Cache-backed, so re-running the same
    batch for the demo does not re-hit the cloud endpoint.
    """
    cards: list[dict[str, Any]] = []
    for item in items:
        if str(item.get("_tier", "shared")).lower() == "private":
            logger.info("contxt:distill_skip_private source=%s", item.get("source"))
            continue
        try:
            cards.append(distill_item(item))
        except ValueError as exc:
            logger.warning("contxt:distill_skip item=%s err=%s", item.get("source"), exc)
    return cards


def distill_draft(
    email: str,
    cards_context: str,
    *,
    max_words: int = 150,
) -> str:
    """Draft a context-aware email reply using cloud Gemma (SHARED context only)."""
    user_prompt = (
        f"Context cards (user's personal context):\n{cards_context}\n\n"
        f"Email to reply to:\n{email}"
    )
    system = _DRAFT_SYSTEM.format(max_words=max_words)
    return _call_cloud_llm(system, user_prompt, max_tokens=400)


# ── Smoke test / prize-capture helper ─────────────────────────────────────────

if __name__ == "__main__":
    # Run offline (mock) unless a key/endpoint is configured. Prints the card and
    # the capturable cloud-gemma log line. For the AMD prize, run with a real
    # AMD_CLOUD_ENDPOINT + FIREWORKS_API_KEY and screenshot the log (see
    # docs/AMD_PRIZE.md).
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    shared = {
        "source": "notion",
        "text": "Contxt architecture: two-tier context, Crown-Jewels Gateway routes "
        "private vs shared. Cloud Gemma distills shared items.",
        "_tier": "shared",
    }
    private = {
        "source": "gmail",
        "text": "Your ICICI loan EMI of Rs 45,000 is due on 2026-07-15.",
        "_tier": "private",
    }

    print("\n== SHARED item → cloud Gemma distillation ==")
    card = distill_item(shared)
    print(json.dumps(card, indent=2))

    # Prove it parses back as a schema-valid ContextCard.
    ContextCard.model_validate(card)
    print("✓ card is schema-valid (round-tripped through ContextCard)")

    print("\n== PRIVATE item → must be refused ==")
    try:
        distill_item(private)
        print("✗ PRIVACY BUG: private item was distilled!")
    except ValueError as exc:
        print(f"✓ refused: {exc}")
