"""Crown-Jewels Gateway — the on-device router.

Decides whether an ingested item is PRIVATE (crown jewels: stays local + E2E
encrypted) or SHARED (safe for the cloud, any AI can use). Runs client-side:
it is the trust boundary, so nothing leaves the device before this decision.

Two passes:
  1. Deterministic rules (cheap, can't-miss) -> force PRIVATE.
  2. Gemma classification (nuance)           -> tier + reason + categories.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .policy import keywords_for
from .rules import rule_hits


class Tier(str, Enum):
    # Values ARE the wire contract (schema/context_card.schema.json). Parse once here,
    # serialize with no transform anywhere downstream — "parse, don't validate".
    PRIVATE = "private"
    SHARED = "shared"

    @classmethod
    def _missing_(cls, value):
        # Boundary parser: tolerate model/legacy casing ("PRIVATE", "Shared")
        # but canonicalize to the single lowercase representation.
        if isinstance(value, str):
            return cls(value.lower()) if value.lower() != value else None
        return None


@dataclass
class Decision:
    tier: Tier
    sensitivity: float
    categories: list = field(default_factory=list)
    reason: str = ""


# The prompt the local/cloud Gemma is given for nuanced classification.
GEMMA_SYSTEM_PROMPT = (
    "You are a privacy gateway. Classify this personal data item. "
    "Output JSON: {tier: private|shared, sensitivity: 0-1, categories: [], reason: ''}. "
    "The user marks these categories as always-private: {policy}."
)


def classify(item, private_keywords=None, policy=None, gemma=None) -> Decision:
    """Classify a single ingested item.

    item:   {"text": str, "source": "gmail|calendar|notion", ...}
    policy: optional list of active UI privacy-toggle ids (see policy.py). When
            given, its category keywords become the private_keywords override —
            this is how the UI toggles feed the Gateway as hard overrides.
    gemma:  optional callable(text) -> {"tier","sensitivity","categories","reason"}
            (cloud Gemma on Fireworks/AMD, or local Gemma via the extension).
    """
    # Coerce text to str so both passes (rules + the gemma callable) get a clean
    # string. None → "" (not the literal "None"); other non-strings are stringified.
    raw = item.get("text", "")
    text = raw if isinstance(raw, str) else ("" if raw is None else str(raw))

    # UI privacy toggles → private_keywords (hard overrides). An explicit
    # private_keywords list still wins if a caller passes one directly.
    if policy is not None and private_keywords is None:
        private_keywords = keywords_for(policy)

    # Pass 1 — deterministic guardrails.
    hits = rule_hits(text, private_keywords)
    if hits:
        return Decision(Tier.PRIVATE, 1.0, hits, "matched deterministic rule(s)")

    # Pass 2 — model nuance. Fall back to SHARED if no model wired yet.
    if gemma is None:
        return Decision(Tier.SHARED, 0.0, [], "no rule hit; model not wired (stub)")

    out = gemma(text)

    # LLM output is untrusted: a 270M (or even a cloud) model can hallucinate a
    # malformed shape or an unknown tier. Parse defensively. The tier IS the
    # decision, so an unparseable/unknown tier fails SAFE to PRIVATE — a privacy
    # gateway must never SHARE something it couldn't classify. Secondary fields
    # (sensitivity/categories/reason) are tolerated field-by-field.
    try:
        if not isinstance(out, dict):
            raise ValueError("model did not return a dict")
        tier = Tier(out.get("tier", "shared"))
    except (ValueError, AttributeError):
        return Decision(
            Tier.PRIVATE,
            1.0,
            ["unparseable-model-output"],
            "model output malformed — defaulted PRIVATE (fail-safe)",
        )

    try:
        sensitivity = max(0.0, min(1.0, float(out.get("sensitivity", 0.0))))
    except (TypeError, ValueError):
        sensitivity = 1.0 if tier is Tier.PRIVATE else 0.0

    categories = out.get("categories") or []
    if not isinstance(categories, list):
        categories = [str(categories)]

    return Decision(tier, sensitivity, categories, str(out.get("reason", "") or ""))


if __name__ == "__main__":
    samples = [
        {"text": "Your ICICI loan EMI of Rs 45,000 is due", "source": "gmail"},
        {"text": "Team standup 10am", "source": "calendar"},
        {"text": "Contxt architecture notes", "source": "notion"},
    ]
    for s in samples:
        d = classify(s)
        print(f"{d.tier.value:8} {d.categories}  <-  {s['text']!r}")
