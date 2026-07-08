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

from .rules import rule_hits


class Tier(str, Enum):
    PRIVATE = "PRIVATE"
    SHARED = "SHARED"


@dataclass
class Decision:
    tier: Tier
    sensitivity: float
    categories: list = field(default_factory=list)
    reason: str = ""


# The prompt the local/cloud Gemma is given for nuanced classification.
GEMMA_SYSTEM_PROMPT = (
    "You are a privacy gateway. Classify this personal data item. "
    "Output JSON: {tier: PRIVATE|SHARED, sensitivity: 0-1, categories: [], reason: ''}. "
    "The user marks these categories as always-private: {policy}."
)


def classify(item, private_keywords=None, gemma=None) -> Decision:
    """Classify a single ingested item.

    item:  {"text": str, "source": "gmail|calendar|notion", ...}
    gemma: optional callable(text) -> {"tier","sensitivity","categories","reason"}
           (cloud Gemma on Fireworks/AMD, or local Gemma via the extension).
    """
    text = item.get("text", "")

    # Pass 1 — deterministic guardrails.
    hits = rule_hits(text, private_keywords)
    if hits:
        return Decision(Tier.PRIVATE, 1.0, hits, "matched deterministic rule(s)")

    # Pass 2 — model nuance. Fall back to SHARED if no model wired yet.
    if gemma is None:
        return Decision(Tier.SHARED, 0.0, [], "no rule hit; model not wired (stub)")

    out = gemma(text)
    return Decision(
        Tier(out.get("tier", "SHARED")),
        float(out.get("sensitivity", 0.0)),
        out.get("categories", []),
        out.get("reason", ""),
    )


if __name__ == "__main__":
    samples = [
        {"text": "Your ICICI loan EMI of Rs 45,000 is due", "source": "gmail"},
        {"text": "Team standup 10am", "source": "calendar"},
        {"text": "Contxt architecture notes", "source": "notion"},
    ]
    for s in samples:
        d = classify(s)
        print(f"{d.tier.value:8} {d.categories}  <-  {s['text']!r}")
