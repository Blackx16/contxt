"""Google Calendar adapter — recent/upcoming events → IngestItem. Read-only.

Raw record shape (sample dump + live pull):
  {id, summary, start, end, attendees[], location, calendar, description}
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from schema.models import Source

from .base import SourceAdapter, parse_timestamp
from .models import IngestItem

_META_KEYS = ("start", "end", "attendees", "location", "calendar")


class CalendarAdapter(SourceAdapter):
    source = Source.CALENDAR
    sample_file = "calendar.json"

    # ── normalize (shared by live + samples) ──────────────────────────────────

    def _normalize(self, raw: dict[str, Any]) -> IngestItem:
        summary = (raw.get("summary") or "").strip()
        description = (raw.get("description") or "").strip()
        attendees = [a for a in (raw.get("attendees") or []) if a]

        parts = [summary]
        if attendees:
            parts.append("Attendees: " + ", ".join(attendees))
        if description:
            parts.append(description)
        text = "\n\n".join(p for p in parts if p)

        return IngestItem(
            id=f"calendar:{raw.get('id', '')}",
            source=Source.CALENDAR,
            text=text or summary or "(untitled event)",
            title=summary or "(untitled event)",
            timestamp=parse_timestamp(raw.get("start")),
            meta={k: raw[k] for k in _META_KEYS if raw.get(k)},
        )

    # ── live pull ──────────────────────────────────────────────────────────────

    def _live_configured(self) -> bool:
        from .providers.google_client import google_configured

        return google_configured()

    def _fetch_raw_live(self, limit: int) -> list[dict[str, Any]]:
        from .providers.google_client import build_service

        svc = build_service("calendar", "v3")
        n = limit or 10
        time_min = (datetime.now(timezone.utc) - timedelta(days=14)).isoformat()
        listing = (
            svc.events()
            .list(
                calendarId="primary",
                maxResults=n,
                singleEvents=True,
                orderBy="startTime",
                timeMin=time_min,
            )
            .execute()
        )
        return [_event_to_raw(ev) for ev in listing.get("items", [])[:n]]


# ── Calendar API event → raw record (pure, unit-tested) ────────────────────────

def _event_to_raw(ev: dict[str, Any]) -> dict[str, Any]:
    start = ev.get("start", {}) or {}
    end = ev.get("end", {}) or {}
    attendees = [
        a.get("email", "") for a in (ev.get("attendees") or []) if a.get("email")
    ]
    return {
        "id": ev.get("id", ""),
        "summary": ev.get("summary", ""),
        "start": start.get("dateTime") or start.get("date", ""),
        "end": end.get("dateTime") or end.get("date", ""),
        "attendees": attendees,
        "location": ev.get("location", ""),
        "calendar": "primary",
        "description": ev.get("description", ""),
    }
