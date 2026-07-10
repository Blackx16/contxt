"""Base source adapter: fetch raw records → normalize → `IngestItem`, capped.

Adapters are **READ-ONLY**. Each has two raw sources:

  * `_fetch_raw_live(limit)`   — pull from the real API (Gmail/Calendar/Notion)
                                 using the user's connected account. Read-only.
  * `_fetch_raw_samples(limit)`— read the on-disk sample dump
                                 (`ingest/samples/<source>.json`), the offline path.

`fetch()` picks between them (see `_want_live`), and **any live failure falls
back to the sample dump** so the demo never crashes on a missing token — the
same graceful-degrade philosophy as `gateway/distill.py`'s offline mock.

Live control (env `CONTXT_INGEST_LIVE`):
  * "1"    force live (still falls back to samples on error)
  * "0"    force samples (never touches the network)
  * unset  auto — live only if this source's credentials are configured
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from schema.models import Source

from .models import IngestItem
from .providers.errors import LiveAuthUnavailable

logger = logging.getLogger(__name__)

_SAMPLES = Path(__file__).parent / "samples"


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO-8601 (or RFC-2822) timestamp to a UTC-aware datetime.

    Sample records use ISO-8601; a live Gmail pull returns RFC-2822 dates, so we
    fall back to `email.utils` for those. Returns None on anything unparseable —
    a missing timestamp must never sink an item.
    """
    if not value:
        return None
    text = value.strip()
    try:
        iso = text[:-1] + "+00:00" if text.endswith("Z") else text
        dt = datetime.fromisoformat(iso)
    except ValueError:
        try:
            from email.utils import parsedate_to_datetime

            dt = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            logger.warning("contxt:ingest_bad_timestamp value=%r", value[:40])
            return None
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class SourceAdapter:
    """Read-only adapter for one source. Subclasses set `source`/`sample_file`,
    implement `_normalize()`, and (for live) `_fetch_raw_live()`/`_live_configured()`."""

    source: Source
    sample_file: str

    # ── live vs. offline resolution ───────────────────────────────────────────

    def _live_configured(self) -> bool:
        """True if credentials for a live pull are present. Default: no."""
        return False

    def _want_live(self, live: Optional[bool]) -> bool:
        if live is not None:
            return live
        flag = os.getenv("CONTXT_INGEST_LIVE")
        if flag == "1":
            return True
        if flag == "0":
            return False
        return self._live_configured()  # auto

    # ── raw record sources ─────────────────────────────────────────────────────

    def _fetch_raw_live(self, limit: int) -> list[dict[str, Any]]:
        """Pull raw, source-shaped records from the live API. Override in subclass."""
        raise NotImplementedError

    def _fetch_raw_samples(self, limit: int) -> list[dict[str, Any]]:
        """Read raw records from the on-disk sample dump (offline default)."""
        path = _SAMPLES / self.sample_file
        if not path.exists():
            logger.warning("contxt:ingest_no_sample source=%s path=%s", self.source, path)
            return []
        try:
            raw = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("contxt:ingest_sample_read_error source=%s err=%s", self.source, exc)
            return []
        if not isinstance(raw, list):
            return []
        return raw[:limit] if limit else raw

    def _fetch_raw(self, limit: int, live: Optional[bool]) -> list[dict[str, Any]]:
        if self._want_live(live):
            try:
                records = self._fetch_raw_live(limit)
                logger.info("contxt:ingest_live source=%s n=%d", self.source.value, len(records))
                return records
            except (LiveAuthUnavailable, NotImplementedError) as exc:
                logger.warning(
                    "contxt:ingest_live_unavailable source=%s err=%s — using samples",
                    self.source.value, exc,
                )
            except Exception as exc:  # network/API error must not sink the demo
                logger.warning(
                    "contxt:ingest_live_failed source=%s err=%s — using samples",
                    self.source.value, exc,
                )
        return self._fetch_raw_samples(limit)

    # ── normalize ───────────────────────────────────────────────────────────────

    def _normalize(self, raw: dict[str, Any]) -> IngestItem:
        raise NotImplementedError

    def fetch(self, limit: int = 10, live: Optional[bool] = None) -> list[IngestItem]:
        """Return up to `limit` normalized items. `live`: True/False force the
        source; None = auto (env-driven, defaults to samples if no creds)."""
        items: list[IngestItem] = []
        for raw in self._fetch_raw(limit, live):
            try:
                items.append(self._normalize(raw))
            except Exception as exc:  # a malformed record must not sink the batch
                logger.warning(
                    "contxt:ingest_normalize_skip source=%s id=%s err=%s",
                    self.source, (raw or {}).get("id"), exc,
                )
        return items[:limit] if limit else items
