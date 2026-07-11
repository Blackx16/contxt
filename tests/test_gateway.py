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


# ── 4. Core routing: rules → stub → model, and Tier canonicalization ───────────

NEUTRAL_ITEM = {"text": "Contxt architecture notes", "source": "notion"}


def _recording_gemma(out):
    """Stand-in for the cloud/on-device Gemma callable that records its calls."""

    def gemma(text):
        gemma.calls.append(text)
        return out

    gemma.calls = []
    return gemma


def test_rule_hit_routes_private_with_metadata():
    d = classify(LOAN_ITEM, private_keywords=[])
    assert d.tier is Tier.PRIVATE
    assert d.sensitivity == 1.0
    assert "money" in d.categories
    assert d.reason == "matched deterministic rule(s)"


def test_no_rule_hit_without_model_is_shared_stub():
    d = classify(NEUTRAL_ITEM, private_keywords=[])
    assert d.tier is Tier.SHARED
    assert d.sensitivity == 0.0
    assert "stub" in d.reason


def test_model_runs_only_when_no_rule_hit():
    gemma = _recording_gemma({"tier": "shared", "sensitivity": 0.1})
    # A rule hit short-circuits — the (costly) model must NOT be consulted.
    classify(LOAN_ITEM, private_keywords=[], gemma=gemma)
    assert gemma.calls == []
    # No rule hit — the model IS consulted, with the item text.
    classify(NEUTRAL_ITEM, private_keywords=[], gemma=gemma)
    assert gemma.calls == [NEUTRAL_ITEM["text"]]


def test_model_output_is_parsed_through():
    gemma = _recording_gemma(
        {"tier": "private", "sensitivity": 0.9, "categories": ["nuance"], "reason": "model said"}
    )
    d = classify(NEUTRAL_ITEM, private_keywords=[], gemma=gemma)
    assert d.tier is Tier.PRIVATE  # the model can escalate a no-rule-hit item
    assert d.sensitivity == 0.9
    assert d.categories == ["nuance"]
    assert d.reason == "model said"


def test_model_uppercase_tier_is_canonicalized():
    # Models emit "PRIVATE"/"SHARED"; Tier._missing_ must fold them to lowercase.
    up = classify(NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma({"tier": "PRIVATE"}))
    assert up.tier is Tier.PRIVATE
    down = classify(NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma({"tier": "SHARED"}))
    assert down.tier is Tier.SHARED


# ── 5. Untrusted model output: malformed → fail SAFE to PRIVATE ────────────────

def test_hallucinated_tier_fails_safe_to_private():
    d = classify(NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma({"tier": "maybe?"}))
    assert d.tier is Tier.PRIVATE
    assert "fail-safe" in d.reason


def test_non_dict_model_output_fails_safe_to_private():
    # A model that returns a bare string (not the {tier,...} contract) is malformed.
    d = classify(NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma("SHARED"))
    assert d.tier is Tier.PRIVATE


def test_missing_tier_key_defaults_shared_not_failsafe():
    # An empty-but-valid dict = "model gave no tier" → stays consistent with the
    # no-rule-hit baseline (shareable); only *corrupt* output flips to PRIVATE.
    d = classify(NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma({}))
    assert d.tier is Tier.SHARED


def test_non_numeric_sensitivity_is_tolerated():
    d = classify(
        NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma({"tier": "shared", "sensitivity": "high"})
    )
    assert d.tier is Tier.SHARED
    assert d.sensitivity == 0.0  # unparseable sensitivity → baseline, not a crash


def test_out_of_range_sensitivity_is_clamped():
    d = classify(
        NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma({"tier": "private", "sensitivity": 5})
    )
    assert d.sensitivity == 1.0


def test_non_list_categories_are_coerced():
    d = classify(
        NEUTRAL_ITEM, private_keywords=[], gemma=_recording_gemma({"tier": "shared", "categories": "finance"})
    )
    assert d.categories == ["finance"]


# ── 6. Non-string / missing text must not crash the router (type hardening) ─────

def test_non_string_text_does_not_crash():
    assert classify({"text": 45000}, private_keywords=[]).tier is Tier.SHARED
    assert classify({"text": None}, private_keywords=[]).tier is Tier.SHARED
    assert classify({"source": "gmail"}, private_keywords=[]).tier is Tier.SHARED  # no "text"


def test_non_string_text_still_reaches_guardrails():
    # Coercion runs before the rules, so a stringified crown jewel is still caught.
    d = classify({"text": ["call the client"]}, policy=["clients"])
    assert d.tier is Tier.PRIVATE


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
    sys.exit(0)
