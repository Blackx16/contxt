"""Notion adapter — page content → IngestItem. Read-only.

Raw record shape (sample dump + live pull):
  {id, title, url, last_edited, text}
"""
from __future__ import annotations

from typing import Any

from schema.models import Source

from .base import SourceAdapter, parse_timestamp
from .models import IngestItem

_META_KEYS = ("url",)


class NotionAdapter(SourceAdapter):
    source = Source.NOTION
    sample_file = "notion.json"

    # ── normalize (shared by live + samples) ──────────────────────────────────

    def _normalize(self, raw: dict[str, Any]) -> IngestItem:
        title = (raw.get("title") or "").strip()
        body = (raw.get("text") or "").strip()
        text = f"{title}\n\n{body}".strip() if body else title
        return IngestItem(
            id=f"notion:{raw.get('id', '')}",
            source=Source.NOTION,
            text=text or title or "(empty page)",
            title=title or "(untitled page)",
            timestamp=parse_timestamp(raw.get("last_edited")),
            meta={k: raw[k] for k in _META_KEYS if raw.get(k)},
        )

    # ── live pull ──────────────────────────────────────────────────────────────

    def _live_configured(self) -> bool:
        from .providers.notion_api import notion_configured

        return notion_configured()

    def _fetch_raw_live(self, limit: int) -> list[dict[str, Any]]:
        from .providers.notion_api import NotionAPI, page_title

        api = NotionAPI()
        n = limit or 10
        out: list[dict[str, Any]] = []
        for page in api.search_pages(page_size=n)[:n]:
            pid = page.get("id", "")
            try:
                text = api.page_plaintext(pid)
            except Exception:  # a single unreadable page shouldn't drop the rest
                text = ""
            out.append(
                {
                    "id": pid,
                    "title": page_title(page),
                    "url": page.get("url", ""),
                    "last_edited": page.get("last_edited_time", ""),
                    "text": text,
                }
            )
        return out
