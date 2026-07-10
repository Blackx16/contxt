"""Deterministic guardrails for the Crown-Jewels Gateway.

These run BEFORE the model. Anything matched here is forced to PRIVATE so a
model misjudgment can never leak a crown jewel (belt-and-suspenders).
"""
import re

_PATTERNS = {
    # Currency symbol/code + number, OR number + currency/magnitude word, OR a
    # bare magnitude word — catches "Rs 45,000", "$2.5M", "5000 dollars", and
    # "lost millions in sales".
    "money": re.compile(
        r"(₹|rs\.?|inr|usd|eur|gbp|\$|€|£)\s?\d[\d,.]*"
        r"|\b\d[\d,.]*\s?(k|m|bn|dollars?|rupees?|euros?|pounds?|lakhs?|crores?)\b"
        r"|\b(millions?|billions?|trillions?|lakhs?|crores?)\b",
        re.I,
    ),
    # Business crown jewels — err PRIVATE (safe default).
    "finance": re.compile(
        r"\b(revenue|sales|profit|turnover|salary|payroll|invoice|earnings"
        r"|valuation|funding|acquisition|net\s?worth)\b",
        re.I,
    ),
    "card": re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    "account": re.compile(r"\b(a/c|acct|account)\b.*\d{4,}", re.I),
    "phone": re.compile(r"\b(?:\+?91[- ]?)?[6-9]\d{9}\b"),
    "health": re.compile(r"\b(diagnos|prescription|medical|blood test|report)\b", re.I),
}

# Populated from the UI privacy toggles.
DEFAULT_PRIVATE_KEYWORDS = ["salary", "loan", "emi", "family", "school", "client"]


def rule_hits(text, private_keywords=None):
    """Return the list of rule categories that force this item PRIVATE.

    private_keywords semantics:
      None  -> use DEFAULT_PRIVATE_KEYWORDS (no UI policy supplied).
      []    -> no keyword overrides (every toggle is off); patterns still apply.
      [...] -> exactly this policy, from the UI privacy toggles.
    """
    if private_keywords is None:
        private_keywords = DEFAULT_PRIVATE_KEYWORDS
    text = text or ""
    hits = [name for name, pat in _PATTERNS.items() if pat.search(text)]
    lowered = text.lower()
    hits += [f"kw:{kw}" for kw in private_keywords if kw in lowered]
    return hits
