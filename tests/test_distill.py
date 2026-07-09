"""Tests for cloud Gemma distillation (CHA-18).

Proves the three "Done when" criteria:
  1. SHARED items become schema-valid context cards.
  2. PRIVATE items are provably never sent to the cloud model.
  3. Every cloud call emits the capturable `contxt:cloud_gemma` log line.

Runs with pytest, or standalone:  python3 -m tests.test_distill
The cloud HTTP call is stubbed — no network, no API key required.
"""
from __future__ import annotations

import json
import logging
import os

# Isolate tests from the on-disk cache.
os.environ["CONTXT_CACHE"] = "0"

from schema.models import ContextCard, Tier
from gateway import distill


# ── 1. SHARED item → schema-valid card ────────────────────────────────────────

def test_shared_item_becomes_schema_valid_card(monkeypatch):
    monkeypatch.setattr(
        distill, "_call_cloud_gemma",
        lambda system, user, **kw: json.dumps({
            "title": "Standup notes",
            "summary": "Daily standup at 10am with the platform team.",
            "body": None,
            "entities": [{"type": "person", "value": "Theerth"},
                         {"type": "date", "value": "2026-07-09"}],
            "sensitivity_score": 0.1,
            "meta": {"active_focus": "ship the gateway"},
        }),
    )
    card = distill.distill_item({"source": "calendar", "text": "standup 10am", "_tier": "shared"})
    # The boundary must hand back something the frozen schema accepts.
    parsed = ContextCard.model_validate(card)
    assert parsed.tier is Tier.SHARED
    assert parsed.source.value == "calendar"
    assert parsed.id.startswith("card_")
    assert 0.0 <= parsed.sensitivity_score <= 1.0
    assert parsed.encryption is None  # SHARED cards carry no at-rest encryption block


# ── 2. PRIVATE item → never reaches the cloud ─────────────────────────────────

def test_private_item_is_refused_before_any_cloud_call(monkeypatch):
    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("cloud Gemma was called with a PRIVATE item!")

    monkeypatch.setattr(distill, "_call_cloud_gemma", _boom)

    raised = False
    try:
        distill.distill_item({"source": "gmail", "text": "ICICI EMI due", "_tier": "private"})
    except ValueError:
        raised = True
    assert raised, "private item should raise ValueError"
    assert called["n"] == 0, "cloud model must not be invoked for private items"


def test_batch_skips_private_keeps_shared(monkeypatch):
    seen_texts = []

    def _fake(system, user, **kw):
        seen_texts.append(user)
        return json.dumps({"title": "t", "summary": "s", "body": None,
                           "entities": [], "sensitivity_score": 0.2, "meta": {}})

    monkeypatch.setattr(distill, "_call_cloud_gemma", _fake)
    cards = distill.distill_batch([
        {"source": "gmail", "text": "loan EMI due", "_tier": "private"},
        {"source": "notion", "text": "architecture notes", "_tier": "shared"},
        {"source": "calendar", "text": "standup", "_tier": "shared"},
    ])
    assert len(cards) == 2, "only the two SHARED items should distill"
    for c in cards:
        ContextCard.model_validate(c)
    # The private item's text must never have been sent to the model.
    assert all("loan EMI due" not in t for t in seen_texts)


# ── 3. Fuzzy model output is coerced, not trusted ─────────────────────────────

def test_out_of_range_and_bad_entities_are_coerced(monkeypatch):
    monkeypatch.setattr(
        distill, "_call_cloud_gemma",
        lambda system, user, **kw: json.dumps({
            "title": "x" * 500,               # too long → truncated
            "summary": "ok",
            "body": None,
            "entities": [
                {"type": "banana", "value": "weird"},   # unknown type → misc
                {"type": "person", "value": ""},         # empty → dropped
                {"type": "org", "value": "AMD"},
            ],
            "sensitivity_score": 9.9,          # out of range → clamped to 1.0
            "meta": {},
        }),
    )
    card = distill.distill_item({"source": "notion", "text": "note", "_tier": "shared"})
    parsed = ContextCard.model_validate(card)
    assert len(parsed.title) <= 200
    assert parsed.sensitivity_score == 1.0
    types = {e.type for e in parsed.entities}
    assert "banana" not in types and "misc" in types
    assert all(e.value for e in parsed.entities)  # no empty values survived


def test_malformed_json_falls_back_to_valid_card(monkeypatch):
    monkeypatch.setattr(distill, "_call_cloud_gemma", lambda system, user, **kw: "not json at all")
    card = distill.distill_item({"source": "gmail", "text": "hello world", "_tier": "shared"})
    ContextCard.model_validate(card)  # must still be valid


def test_unknown_source_is_rejected():
    raised = False
    try:
        distill.distill_item({"source": "slack", "text": "hi", "_tier": "shared"})
    except ValueError:
        raised = True
    assert raised, "source outside gmail/calendar/notion must raise"


# ── 4. Cloud call emits the AMD-prize log line (mock path) ─────────────────────

def test_cloud_call_emits_capturable_log_line(caplog):
    os.environ["CONTXT_MOCK_GEMMA"] = "1"
    try:
        with caplog.at_level(logging.INFO, logger="gateway.distill"):
            distill._call_cloud_gemma(distill._DISTILL_SYSTEM, "Source: notion\n\nItem:\nhi")
        assert any("contxt:cloud_gemma" in r.getMessage() for r in caplog.records)
    finally:
        os.environ.pop("CONTXT_MOCK_GEMMA", None)


# ── standalone runner (no pytest required) ────────────────────────────────────

if __name__ == "__main__":
    class _Monkey:
        """Minimal monkeypatch shim so tests run without pytest installed."""
        def __init__(self):
            self._undo = []
        def setattr(self, obj, name, value):
            self._undo.append((obj, name, getattr(obj, name)))
            setattr(obj, name, value)
        def undo(self):
            for obj, name, old in reversed(self._undo):
                setattr(obj, name, old)

    class _Caplog:
        def __init__(self):
            self.records = []
            self._handler = None
        def at_level(self, level, logger="gateway.distill"):
            caplog = self
            lg = logging.getLogger(logger)

            class _Ctx:
                def __enter__(self_):
                    class H(logging.Handler):
                        def emit(h_self, record):
                            caplog.records.append(record)
                    caplog._handler = H()
                    lg.addHandler(caplog._handler)
                    lg.setLevel(level)
                    return caplog
                def __exit__(self_, *a):
                    lg.removeHandler(caplog._handler)
            return _Ctx()

    import inspect
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in tests:
        params = inspect.signature(fn).parameters
        kwargs = {}
        mk = None
        if "monkeypatch" in params:
            mk = _Monkey()
            kwargs["monkeypatch"] = mk
        if "caplog" in params:
            kwargs["caplog"] = _Caplog()
        try:
            fn(**kwargs)
            print(f"  ✓ {fn.__name__}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ✗ {fn.__name__}: {exc}")
            raise
        finally:
            if mk:
                mk.undo()
    print(f"\n{passed}/{len(tests)} tests passed")
