"""Tests for the Crown-Jewels Gateway privacy-toggle overrides (CHA-24).

Proves the wiring the ticket asks for:
  1. Always-on guardrails force PRIVATE regardless of toggles (safety floor).
  2. A base-SHARED item flips to PRIVATE when its category toggle is ON,
     and stays SHARED when every toggle is off — a two-way, demonstrable change.
  3. policy.keywords_for() flattens active categories into the private_keywords
     list rules.py consumes.

Runs with pytest, or standalone:  python3 -m tests.test_gateway
"""
from __future__ import annotations

from gateway import policy
from gateway.gateway import Tier, classify

CLIENT_ITEM = {
    "text": "Kickoff call with our new client Acme Retail to walk through the onboarding plan.",
    "source": "calendar",
}
FAMILY_ITEM = {
    "text": "Pick up the kids from school, then family dinner at home on Sunday.",
    "source": "gmail",
}
LOAN_ITEM = {"text": "Your ICICI loan EMI of Rs 45,000 is due", "source": "gmail"}


# ── 1. Guardrails are independent of toggles ──────────────────────────────────

def test_guardrail_forces_private_even_with_all_toggles_off():
    # policy=[] means every UI toggle is off; the money/account patterns still fire.
    d = classify(LOAN_ITEM, policy=[])
    assert d.tier is Tier.PRIVATE
    assert "money" in d.categories


# ── 2. Toggle overrides are a two-way, demonstrable tier change ────────────────

def test_client_item_is_shared_with_no_toggles():
    d = classify(CLIENT_ITEM, policy=[])
    assert d.tier is Tier.SHARED


def test_clients_toggle_forces_client_item_private():
    d = classify(CLIENT_ITEM, policy=["clients"])
    assert d.tier is Tier.PRIVATE
    assert "kw:client" in d.categories


def test_family_toggle_only_affects_family_items():
    assert classify(FAMILY_ITEM, policy=[]).tier is Tier.SHARED
    assert classify(FAMILY_ITEM, policy=["family"]).tier is Tier.PRIVATE
    # A family toggle must NOT sweep in an unrelated client item.
    assert classify(CLIENT_ITEM, policy=["family"]).tier is Tier.SHARED


# ── 3. policy → private_keywords ──────────────────────────────────────────────

def test_keywords_for_flattens_and_dedupes():
    kws = policy.keywords_for(["financials", "clients"])
    assert "loan" in kws and "client" in kws
    assert len(kws) == len(set(kws))  # no duplicates
    assert policy.keywords_for([]) == []
    assert policy.keywords_for(None) == []


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
    sys.exit(0)
