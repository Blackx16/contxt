"""Gmail adapter — recent messages → IngestItem. Read-only.

Raw record shape (produced by both the sample dump and the live pull, so
`_normalize()` is source-agnostic):
  {id, threadId, from, to, subject, date, labels[], body}
"""
from __future__ import annotations

import base64
import binascii
from typing import Any, Optional

from schema.models import Source

from .base import SourceAdapter, parse_timestamp
from .models import IngestItem

_META_KEYS = ("from", "to", "labels", "threadId")

# Recent, low-noise window for the live pull; keeps the demo fast.
_LIVE_QUERY = "newer_than:30d -category:promotions"


class GmailAdapter(SourceAdapter):
    source = Source.GMAIL
    sample_file = "gmail.json"

    # ── normalize (shared by live + samples) ──────────────────────────────────

    def _normalize(self, raw: dict[str, Any]) -> IngestItem:
        subject = (raw.get("subject") or "").strip()
        body = (raw.get("body") or "").strip()
        text = f"{subject}\n\n{body}".strip() if body else subject
        return IngestItem(
            id=f"gmail:{raw.get('id', '')}",
            source=Source.GMAIL,
            text=text or subject or "(no content)",
            title=subject or "(no subject)",
            timestamp=parse_timestamp(raw.get("date")),
            meta={k: raw[k] for k in _META_KEYS if raw.get(k) is not None},
        )

    # ── live pull ──────────────────────────────────────────────────────────────

    def _live_configured(self) -> bool:
        from .providers.google_client import google_configured

        return google_configured()

    def _fetch_raw_live(self, limit: int) -> list[dict[str, Any]]:
        from .providers.google_client import build_service

        svc = build_service("gmail", "v1")
        n = limit or 10
        listing = (
            svc.users().messages()
            .list(userId="me", maxResults=n, q=_LIVE_QUERY)
            .execute()
        )
        out: list[dict[str, Any]] = []
        for meta in listing.get("messages", [])[:n]:
            msg = (
                svc.users().messages()
                .get(userId="me", id=meta["id"], format="full")
                .execute()
            )
            out.append(_message_to_raw(msg))
        return out


# ── Gmail API payload → raw record (pure, unit-tested) ─────────────────────────

def _header(headers: list[dict[str, str]], name: str) -> str:
    for h in headers or []:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract_body(payload: dict[str, Any]) -> str:
    """Prefer a text/plain part anywhere in the tree; fall back to any body.

    The two-pass order matters: a multipart/alternative lists text/html and
    text/plain siblings, and we want the plain text — never the HTML — so we
    search the whole tree for text/plain first, then accept anything.
    """
    return _find_part(payload, "text/plain") or _find_part(payload, None)


def _find_part(payload: dict[str, Any], want_mime: Optional[str]) -> str:
    """DFS for a decodable body; `want_mime=None` matches any mime type."""
    if not payload:
        return ""
    data = (payload.get("body") or {}).get("data")
    if data and (want_mime is None or payload.get("mimeType") == want_mime):
        return _decode(data)
    for part in payload.get("parts", []) or []:
        text = _find_part(part, want_mime)
        if text:
            return text
    return ""


def _decode(data: str) -> str:
    try:
        return base64.urlsafe_b64decode(data.encode()).decode("utf-8", "replace").strip()
    except (binascii.Error, ValueError):
        return ""


def _message_to_raw(msg: dict[str, Any]) -> dict[str, Any]:
    payload = msg.get("payload", {}) or {}
    headers = payload.get("headers", [])
    body = _extract_body(payload) or (msg.get("snippet", "") or "")
    return {
        "id": msg.get("id", ""),
        "threadId": msg.get("threadId", ""),
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "subject": _header(headers, "Subject"),
        "date": _header(headers, "Date"),
        "labels": msg.get("labelIds", []),
        "body": body,
    }
