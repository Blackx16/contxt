"""Tests for the ingest adapters (CHA-16).

Proves the three "Done when" criteria:
  1. ingest_all() produces a normalized IngestItem[] from all 3 sources.
  2. At least one item from each source (gmail, calendar, notion).
  3. Output feeds the Gateway with no reshaping:
        classify(item.to_gateway_input())  — and on into the distiller.

Runs fully offline against the on-disk sample dump — no network, no accounts.
Run with pytest, or standalone:  python3 -m tests.test_ingest
"""
from __future__ import annotations

import os
from datetime import timezone

# Isolate any distiller calls from the on-disk cache.
os.environ.setdefault("CONTXT_CACHE", "0")

from schema.models import ContextCard, Source
from ingest import (
    ADAPTERS,
    CalendarAdapter,
    GmailAdapter,
    IngestItem,
    NotionAdapter,
    ingest_all,
)
from gateway import distill
from gateway.gateway import Decision, Tier, classify

_ALL_SOURCES = {Source.GMAIL, Source.CALENDAR, Source.NOTION}


# ── 1. Normalized IngestItem[] from all three sources ─────────────────────────

def test_ingest_all_returns_ingest_items_from_all_three_sources():
    items = ingest_all()
    assert items, "ingest produced nothing"
    assert all(isinstance(i, IngestItem) for i in items)
    assert {i.source for i in items} == _ALL_SOURCES


def test_at_least_one_item_per_source():
    items = ingest_all()
    for src in _ALL_SOURCES:
        assert sum(1 for i in items if i.source is src) >= 1, f"no items from {src}"


def test_items_are_well_formed():
    for it in ingest_all():
        assert it.id and ":" in it.id      # source-prefixed, e.g. "gmail:…"
        assert it.title and it.text        # never empty
        assert it.id.split(":", 1)[0] == it.source.value


# ── 2. Feeds the Gateway with no reshaping ────────────────────────────────────

def test_gateway_input_keeps_the_exact_keys_the_gateway_reads():
    gi = ingest_all(limit_per_source=1)[0].to_gateway_input()
    # gateway.classify reads item["text"]; the distiller reads item["source"].
    assert "text" in gi and "source" in gi
    assert isinstance(gi["source"], str)          # lowercase wire value, not an enum
    assert gi["source"] in {s.value for s in Source}


def test_every_item_feeds_gateway_and_returns_a_decision():
    for it in ingest_all():
        decision = classify(it.to_gateway_input())     # no reshaping
        assert isinstance(decision, Decision)
        assert decision.tier in (Tier.PRIVATE, Tier.SHARED)


def test_finance_item_is_routed_private_by_the_gateway():
    # The real Vi telecom bill carries a ₹ amount and must trip the money rule.
    finance = [i for i in ingest_all() if i.source is Source.GMAIL and "₹" in i.text]
    assert finance, "expected a ₹-amount gmail item in the sample dump"
    for it in finance:
        assert classify(it.to_gateway_input()).tier is Tier.PRIVATE


# ── 3. End-to-end: a SHARED item distills into a schema-valid card ────────────

def test_shared_item_flows_into_the_distiller(monkeypatch):
    monkeypatch.setattr(
        distill, "_call_cloud_llm",
        lambda system, user, **kw: '{"title":"t","summary":"s","body":null,'
                                   '"entities":[],"sensitivity_score":0.2,"meta":{}}',
    )
    shared_input = None
    for it in ingest_all():
        gi = it.to_gateway_input()
        if classify(gi).tier is Tier.SHARED:
            shared_input = gi
            break
    assert shared_input is not None, "expected at least one SHARED item"
    card = distill.distill_item(shared_input)   # fed directly, unchanged
    ContextCard.model_validate(card)            # must be schema-valid


# ── Volume cap + timestamps ───────────────────────────────────────────────────

def test_volume_cap_is_respected():
    items = ingest_all(limit_per_source=1)
    for src in _ALL_SOURCES:
        assert sum(1 for i in items if i.source is src) <= 1


def test_timestamps_are_utc_aware_or_none():
    for it in ingest_all():
        if it.timestamp is not None:
            assert it.timestamp.tzinfo is not None
            assert it.timestamp.utcoffset() == timezone.utc.utcoffset(None)


def test_adapters_are_read_only_offline():
    # Each adapter yields items without any network/account — offline-safe demo.
    for adapter in ADAPTERS:
        assert adapter.fetch(limit=5)  # sample dump populated for every source


# ── standalone runner (no pytest required) — mirrors tests/test_distill.py ─────

if __name__ == "__main__":
    import inspect

    class _Monkey:
        def __init__(self):
            self._undo = []

        def setattr(self, obj, name, value):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)

        def undo(self):
            for obj, name, old in reversed(self._undo):
                setattr(obj, name, old)

    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in tests:
        mk = _Monkey() if "monkeypatch" in inspect.signature(fn).parameters else None
        try:
            fn(mk) if mk else fn()
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {fn.__name__}: {exc}")
            raise
        finally:
            if mk:
                mk.undo()
    print(f"\n{passed}/{len(tests)} tests passed")
