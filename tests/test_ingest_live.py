"""Tests for the LIVE ingest path (CHA-16) — no network.

Proves:
  * Real Gmail / Calendar API payloads and Notion blocks normalize into the
    same IngestItem shape as the sample dump (so the Gateway sees no difference).
  * Live control resolves correctly and a live failure falls back to samples,
    so the demo never crashes on a missing/expired credential.

All API calls are stubbed — no accounts, tokens, or network required. pytest.
"""
from __future__ import annotations

import base64

from schema.models import Source
from ingest import ADAPTERS, ingest_all
from ingest.calendar import CalendarAdapter, _event_to_raw
from ingest.gmail import GmailAdapter, _extract_body, _message_to_raw
from ingest.notion import NotionAdapter
from ingest.providers.errors import LiveAuthUnavailable
from ingest.providers.notion_api import NotionAPI, blocks_to_text, page_title

_ALL = {Source.GMAIL, Source.CALENDAR, Source.NOTION}


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


# ── Gmail live payload → IngestItem ───────────────────────────────────────────

def test_gmail_message_payload_normalizes_like_a_sample():
    msg = {
        "id": "abc123",
        "threadId": "t1",
        "labelIds": ["INBOX", "UNREAD"],
        "snippet": "snippet fallback",
        "payload": {
            "mimeType": "multipart/alternative",
            "headers": [
                {"name": "From", "value": "Alex <alex@example.com>"},
                {"name": "To", "value": "me@example.com"},
                {"name": "Subject", "value": "Hello live"},
                {"name": "Date", "value": "Fri, 10 Jul 2026 11:04:08 +0000"},
            ],
            "parts": [
                {"mimeType": "text/html", "body": {"data": _b64("<p>ignore me</p>")}},
                {"mimeType": "text/plain", "body": {"data": _b64("Live body text here.")}},
            ],
        },
    }
    item = GmailAdapter()._normalize(_message_to_raw(msg))
    assert item.id == "gmail:abc123"
    assert item.source is Source.GMAIL
    assert item.title == "Hello live"
    assert "Hello live" in item.text and "Live body text here." in item.text
    assert item.meta["from"] == "Alex <alex@example.com>"
    assert item.timestamp is not None and item.timestamp.utcoffset().total_seconds() == 0


def test_gmail_extract_body_walks_nested_multipart():
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "multipart/alternative", "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("deep text")}},
            ]},
        ],
    }
    assert _extract_body(payload) == "deep text"


# ── Calendar live payload → IngestItem ────────────────────────────────────────

def test_calendar_event_normalizes_like_a_sample():
    ev = {
        "id": "e1",
        "summary": "Contxt sync",
        "location": "https://meet.example/xyz",
        "start": {"dateTime": "2026-07-09T23:30:00+05:30"},
        "end": {"dateTime": "2026-07-10T00:30:00+05:30"},
        "attendees": [{"email": "me@example.com"}, {"email": "theerth@example.com"}, {}],
        "description": "walk the demo",
    }
    item = CalendarAdapter()._normalize(_event_to_raw(ev))
    assert item.id == "calendar:e1"
    assert item.title == "Contxt sync"
    assert "Attendees: me@example.com, theerth@example.com" in item.text
    assert item.meta["location"].startswith("https://meet")
    assert item.timestamp is not None  # 23:30 IST -> 18:00Z


def test_calendar_all_day_event_uses_date():
    ev = {"id": "d1", "summary": "Holiday", "start": {"date": "2026-07-15"}, "end": {"date": "2026-07-16"}}
    raw = _event_to_raw(ev)
    assert raw["start"] == "2026-07-15"
    assert CalendarAdapter()._normalize(raw).timestamp is not None


# ── Notion live payload → text/title ──────────────────────────────────────────

def test_notion_blocks_flatten_to_text_skipping_non_text():
    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title H"}]}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Para one."}]}},
        {"type": "image", "image": {}},  # non-text → skipped
        {"type": "to_do", "to_do": {"rich_text": [{"plain_text": "task"}]}},
    ]
    assert blocks_to_text(blocks) == "Title H\nPara one.\ntask"


def test_notion_page_title_from_properties():
    page = {"properties": {"Name": {"type": "title", "title": [{"plain_text": "My Page"}]}}}
    assert page_title(page) == "My Page"


# ── live control + fallback ───────────────────────────────────────────────────

def test_force_samples_never_calls_live(monkeypatch):
    def boom(limit):
        raise AssertionError("live pull attempted in samples mode")

    for a in ADAPTERS:
        monkeypatch.setattr(a, "_fetch_raw_live", boom)
    items = ingest_all(live=False)
    assert {i.source for i in items} == _ALL


def test_live_failure_falls_back_to_samples(monkeypatch):
    def boom(limit):
        raise RuntimeError("api down / token expired")

    for a in ADAPTERS:
        monkeypatch.setattr(a, "_fetch_raw_live", boom)
    items = ingest_all(live=True)  # forced live, but every source errors
    assert items, "fallback to samples produced nothing"
    assert {i.source for i in items} == _ALL


def test_env_flag_zero_forces_samples(monkeypatch):
    monkeypatch.setenv("CONTXT_INGEST_LIVE", "0")
    for a in ADAPTERS:
        monkeypatch.setattr(a, "_fetch_raw_live",
                            lambda limit: (_ for _ in ()).throw(AssertionError("live called")))
    assert {i.source for i in ingest_all()} == _ALL


# ── providers refuse to run unconfigured (no accidental anonymous calls) ──────

def test_notion_api_requires_token(monkeypatch):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    try:
        NotionAPI()
        assert False, "expected LiveAuthUnavailable"
    except LiveAuthUnavailable:
        pass


def test_google_credentials_unconfigured_raises(monkeypatch):
    monkeypatch.delenv("GOOGLE_TOKEN", raising=False)
    monkeypatch.delenv("GOOGLE_OAUTH_CLIENT", raising=False)
    from ingest.providers.google_client import get_credentials

    try:
        get_credentials()
        assert False, "expected LiveAuthUnavailable"
    except LiveAuthUnavailable:
        pass
