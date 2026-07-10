"""User privacy policy for the Crown-Jewels Gateway (CHA-24).

The plain-language toggle categories exposed in the UI, mapped to the keyword
lists rules.py already consumes as ``private_keywords``. Turning a category ON is
a HARD OVERRIDE: any item whose text matches its keywords is forced PRIVATE,
regardless of what Gemma would have decided.

Kept in sync with ``web/src/lib/gateway.ts`` (PRIVACY_CATEGORIES). The keyword
union is a superset of ``rules.DEFAULT_PRIVATE_KEYWORDS``.
"""
from __future__ import annotations

# category id -> {label, keywords}
PRIVACY_CATEGORIES: dict[str, dict] = {
    "financials": {
        "label": "Money & finances",
        "keywords": [
            "salary", "loan", "emi", "invoice", "budget", "expense", "bank",
            "mortgage", "payroll", "revenue", "net worth", "bonus",
        ],
    },
    "family": {
        "label": "Family & home",
        "keywords": [
            "family", "kids", "child", "children", "school", "spouse", "wife",
            "husband", "daughter", "parents", "home", "anniversary",
        ],
    },
    "clients": {
        "label": "Clients & deals",
        "keywords": [
            "client", "customer", "deal", "contract", "proposal", "onboarding", "vendor",
        ],
    },
    "health": {
        "label": "Health",
        "keywords": ["doctor", "clinic", "appointment", "therapy", "pharmacy", "vaccine"],
    },
}


def keywords_for(active_ids) -> list[str]:
    """Flatten the active categories' keywords into a ``private_keywords`` list.

    ``active_ids`` is the list of toggle ids the user has turned on. Order is
    preserved and duplicates removed. Unknown ids are ignored.
    """
    out: list[str] = []
    for cid in active_ids or []:
        cat = PRIVACY_CATEGORIES.get(cid)
        if cat:
            out.extend(cat["keywords"])
    seen: set[str] = set()
    return [k for k in out if not (k in seen or seen.add(k))]
