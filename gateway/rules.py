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
    # Coerce to str: this is the can't-miss guardrail, so a non-string item
    # (int, list, None from a malformed ingest) must degrade to "no text",
    # never crash the regex engine on `.search()` / `.lower()`.
    text = "" if text is None else str(text)
    hits = [name for name, pat in _PATTERNS.items() if pat.search(text)]
    # Keyword hits are case-insensitive WORD-boundary matches, not substrings, so
    # "emi" fires on the loan term but not inside "reminder"/"premium". Still
    # catches the whole keyword anywhere in the text; mixed-case toggles work too.

    # Fast-path check: avoid regex overhead if keyword doesn't appear as a substring
    text_lower = text.lower()
    for kw in private_keywords:
        k = str(kw).lower()
        if k in text_lower and re.search(r"\b" + re.escape(k) + r"\b", text, re.I):
            hits.append(f"kw:{k}")
    return hits
