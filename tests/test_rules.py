"""Unit tests for the deterministic guardrails (gateway/rules.py).

rule_hits is the can't-miss safety floor: it runs BEFORE any model and forces
crown jewels to PRIVATE, so a regression here is a silent privacy leak. These
tests pin every pattern, the private_keywords semantics (None vs [] vs [...]),
and the null/non-string edge cases the coercion guard must survive.

Runs with pytest, or standalone:  python3 -m tests.test_rules
"""
from __future__ import annotations

from gateway.rules import DEFAULT_PRIVATE_KEYWORDS, rule_hits


# ── Patterns fire (private_keywords=[] isolates patterns from keyword hits) ─────

def test_money_currency_symbol():
    assert "money" in rule_hits("Your ICICI loan EMI of Rs 45,000 is due", [])
    assert "money" in rule_hits("Invoice for $2.5M closed", [])
    assert "money" in rule_hits("paid 5000 dollars upfront", [])


def test_money_bare_magnitude_word():
    assert "money" in rule_hits("we lost millions in the pivot", [])
    assert "money" in rule_hits("2 crores in the bank", [])


def test_finance_keywords():
    assert "finance" in rule_hits("Q3 revenue beat plan", [])
    assert "finance" in rule_hits("annual payroll run", [])
    # Case-insensitive.
    assert "finance" in rule_hits("TURNOVER doubled", [])


def test_card_number():
    assert "card" in rule_hits("card 4111 1111 1111 1111 on file", [])


def test_account_number():
    assert "account" in rule_hits("Account number 12345678 credited", [])
    assert "account" in rule_hits("a/c 0098123 debited", [])


def test_indian_phone_number():
    assert "phone" in rule_hits("call me on 9876543210 today", [])
    assert "phone" in rule_hits("reach +919876543210 anytime", [])


def test_health_terms():
    hits = rule_hits("blood test report attached, prescription renewed", [])
    assert "health" in hits


def test_benign_text_has_no_hits():
    assert rule_hits("Team standup 10am", []) == []
    assert rule_hits("Contxt architecture notes", []) == []


# ── private_keywords semantics: None → defaults, [] → off, [...] → exact ────────

def test_none_uses_default_keywords():
    # "school" is a default keyword but matches no regex pattern — pure keyword hit.
    assert "school" in DEFAULT_PRIVATE_KEYWORDS
    assert rule_hits("school pickup at 3") == ["kw:school"]


def test_empty_list_disables_keyword_hits_but_not_patterns():
    # Toggles all off: keyword-only text is clean, but hard patterns still fire.
    assert rule_hits("school pickup at 3", []) == []
    assert rule_hits("Rs 45,000 due", []) == ["money"]


def test_explicit_keywords_are_used_verbatim():
    assert rule_hits("call the client back", ["client"]) == ["kw:client"]
    # A keyword not in the supplied list must not fire.
    assert rule_hits("school run", ["client"]) == []


def test_keyword_matching_is_case_insensitive():
    # Case-insensitive both ways: uppercase text with a lowercase keyword…
    assert "kw:client" in rule_hits("Emailed the CLIENT", ["client"])
    # …and a mixed-case keyword against lowercase text (keywords are normalized).
    assert rule_hits("emailed the client", ["Client"]) == ["kw:client"]
    assert rule_hits("SALARY review", ["Salary"]) == ["finance", "kw:salary"]


# ── Edge cases: null / empty / non-string input must never raise ────────────────

def test_none_text_returns_empty():
    assert rule_hits(None) == []
    assert rule_hits(None, []) == []


def test_empty_string_returns_empty():
    assert rule_hits("", []) == []


def test_non_string_text_does_not_crash():
    # A malformed ingest (number, list) must degrade to str, never crash the
    # regex engine. 45000 stringifies to "45000" — no currency/magnitude → clean.
    assert rule_hits(45000, []) == []
    assert isinstance(rule_hits(["loan", "emi"], []), list)  # no TypeError


if __name__ == "__main__":
    import sys

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\n{len(fns)} passed")
    sys.exit(0)
