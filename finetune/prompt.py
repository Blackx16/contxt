"""Canonical prompt + label contract for the Crown-Jewels Gateway fine-tune.

This is the SINGLE SOURCE OF TRUTH shared by every stage:
  - the Kimi data-gen prompt (finetune/KIMI_PROMPT.md mirrors these strings),
  - the rules-oracle seed generator (generate_seed.py),
  - the dataset validator (validate.py),
  - the evaluator (eval.py),
  - and the deployed extension (extension/offscreen.js must send the SAME
    instruction + a user-only chat turn so training == inference).

If you change INSTRUCTION or the label shape here, you MUST regenerate data and
re-point offscreen.js. Parity between train-time and infer-time formatting is the
whole ballgame for a 270M fine-tune — a drifted prompt silently tanks accuracy.
"""
from __future__ import annotations

import json

# ── The instruction the model is trained and served with ───────────────────────
# Kept deliberately stable. It lives in the USER turn (Gemma has no system role;
# its chat template merges any system content into the first user turn anyway).
INSTRUCTION = (
    "You are a privacy classifier for personal data in the Contxt Crown-Jewels "
    "Gateway. Decide the tier of ONE item.\n"
    "- PRIVATE = crown jewels that must stay on the user's device: money amounts, "
    "finances (salary, revenue, invoices, valuations, funding), card or account "
    "numbers, phone numbers, health, family matters, client-confidential or deal "
    "details, credentials/passwords/OTPs, or anything the user would not want a "
    "third-party AI to read.\n"
    "- SHARED = safe for an AI assistant to use: general work, public information, "
    "routine scheduling, non-sensitive logistics.\n"
    "When unsure, prefer PRIVATE (a wrong SHARED leaks a secret; a wrong PRIVATE "
    "only over-protects).\n"
    'Return ONLY a JSON object, no markdown, no commentary: '
    '{"tier":"PRIVATE"|"SHARED","sensitivity":<float 0.0-1.0>,'
    '"categories":[<zero or more strings>],"reason":"<max 12 words>"}'
)

# ── Closed category vocabulary (what may appear in `categories`) ────────────────
# The first six mirror the deterministic rule names in gateway/rules.py so the
# model's output reads consistently next to Pass-1. The rest are semantic buckets
# for the nuanced cases the regexes miss (which is the model's actual job).
CATEGORIES = {
    "money", "finance", "card", "account", "phone", "health",   # rule-aligned
    "family", "clients", "credentials", "legal",                # sensitive semantic
    "work", "scheduling", "travel", "personal", "location", "misc",  # usually shared
}

# ── Sensitivity banding (guidance, enforced softly by validate.py) ──────────────
#   0.90–1.00  hard financial amounts, card/account numbers, credentials, explicit
#              health diagnosis
#   0.70–0.89  salary/loan/EMI, client-confidential/deal, family or personal health,
#              legal matters
#   0.50–0.69  implied / borderline sensitive  → still PRIVATE (safety asymmetry)
#   0.25–0.49  mildly personal but shareable, or genuinely ambiguous → SHARED
#   0.00–0.24  clearly public / work / routine scheduling
# Rule of thumb: PRIVATE items sit >= 0.50, SHARED items sit <= 0.35.

VALID_TIERS = {"PRIVATE", "SHARED"}


def build_user_content(text: str) -> str:
    """The exact user-turn string for an item (train-time and infer-time)."""
    return f'{INSTRUCTION}\n\nItem: "{text}"'


def build_messages(text: str, label: dict | None = None) -> list[dict]:
    """User-only prompt, plus the assistant target when `label` is given.

    Inference: build_messages(text)            -> [user]
    Training:  build_messages(text, label)     -> [user, assistant]
    """
    msgs = [{"role": "user", "content": build_user_content(text)}]
    if label is not None:
        msgs.append({"role": "assistant", "content": dumps_label(label)})
    return msgs


def dumps_label(d: dict) -> str:
    """Canonical, compact JSON serialization of a label (fixed key order)."""
    return json.dumps(
        {
            "tier": d["tier"],
            "sensitivity": round(float(d["sensitivity"]), 2),
            "categories": list(d.get("categories", [])),
            "reason": str(d.get("reason", ""))[:120],
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


# Regex to recover the raw item text from a stored user-turn (used by validate/eval).
ITEM_RE = None
def extract_item(user_content: str) -> str | None:
    """Pull the raw item text back out of a user-turn string."""
    import re
    global ITEM_RE
    if ITEM_RE is None:
        ITEM_RE = re.compile(r'Item:\s*"(.*)"\s*$', re.DOTALL)
    m = ITEM_RE.search(user_content)
    return m.group(1) if m else None
