"""Cloud Gemma distillation — SHARED-tier items → context cards.

Uses Fireworks AI (gemma-3-27b-it) or an AMD Dev Cloud endpoint.
PRIVATE-tier items are BLOCKED — they must never reach this function.

Prize target: AMD Dev Cloud → "Best AMD-Hosted Gemma Project" ($2k).
Log lines below capture the AMD-hosted inference for the submission.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_FIREWORKS_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
_DEFAULT_MODEL = os.getenv(
    "GEMMA_CLOUD_MODEL", "accounts/fireworks/models/gemma-3-27b-it"
)
_AMD_ENDPOINT = os.getenv("AMD_CLOUD_ENDPOINT", "")

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


# ── API call ──────────────────────────────────────────────────────────────────

def _api_key() -> str:
    key = os.getenv("FIREWORKS_API_KEY", "")
    if not key:
        raise RuntimeError(
            "FIREWORKS_API_KEY not set — add it to .env or export it before "
            "running the MCP server."
        )
    return key


def _call_cloud_gemma(
    system: str,
    user: str,
    *,
    model: str | None = None,
    max_tokens: int = 512,
) -> str:
    """POST to Fireworks (or AMD Dev Cloud) and return the assistant text.

    The INFO log line below captures model ID + usage tokens for the AMD prize
    submission screenshot.
    """
    endpoint = _AMD_ENDPOINT or _FIREWORKS_URL
    chosen_model = model or _DEFAULT_MODEL

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

    logger.info(
        "contxt:cloud_gemma endpoint=%s model=%s",
        endpoint,
        chosen_model,
    )
    resp = httpx.post(endpoint, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    logger.info(
        "contxt:cloud_gemma_ok id=%s usage=%s",
        data.get("id"),
        data.get("usage"),
    )
    return data["choices"][0]["message"]["content"].strip()


# ── Public API ────────────────────────────────────────────────────────────────

def distill_item(item: dict[str, Any]) -> dict[str, Any]:
    """Distill a SHARED-tier raw item into a context-card dict.

    Raises ValueError if the item carries _tier=private — caller must check
    before calling this function (belt-and-suspenders privacy guard).
    """
    if item.get("_tier", "shared").lower() == "private":
        raise ValueError(
            "distill_item called with a PRIVATE item — aborting to protect "
            "user privacy. Only call this on SHARED-tier items."
        )

    source = item.get("source", "unknown")
    text = item.get("text", "")
    user_prompt = f"Source: {source}\n\nItem:\n{text[:2000]}"

    raw = _call_cloud_gemma(_DISTILL_SYSTEM, user_prompt)

    # Strip markdown fences if the model wrapped anyway
    if "```" in raw:
        parts = raw.split("```")
        raw = parts[1].lstrip("json").strip() if len(parts) > 2 else parts[-1].strip()

    try:
        card_data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("contxt:distill_parse_error raw=%s", raw[:300])
        card_data = {
            "title": text[:80],
            "summary": text[:200] if text else None,
            "body": None,
            "entities": [],
            "sensitivity_score": 0.3,
            "meta": {},
        }

    # Stamp required schema fields
    card_data.update(
        {
            "id": f"card_{uuid.uuid4()}",
            "tier": "shared",
            "source": source,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "embedding_ref": None,
            "encryption": None,
        }
    )
    return card_data


def distill_draft(
    email: str,
    cards_context: str,
    *,
    max_words: int = 150,
) -> str:
    """Draft a context-aware email reply using cloud Gemma."""
    user_prompt = (
        f"Context cards (user's personal context):\n{cards_context}\n\n"
        f"Email to reply to:\n{email}"
    )
    system = _DRAFT_SYSTEM.format(max_words=max_words)
    return _call_cloud_gemma(system, user_prompt, max_tokens=400)
