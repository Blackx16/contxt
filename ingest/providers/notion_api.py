"""Minimal read-only Notion REST client for the ingest adapter (CHA-16).

Uses an internal-integration token (NOTION_TOKEN) — create one at
https://www.notion.so/my-integrations, then share the pages/databases you want
ingested with that integration. Uses httpx (already a dependency); no SDK.
Read-only: only `search` (POST) and block reads (GET). Nothing is written.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

import httpx

from .errors import LiveAuthUnavailable

logger = logging.getLogger(__name__)

_BASE = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"

# Block types whose rich_text we flatten into plaintext.
_TEXT_BLOCKS = {
    "paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item",
    "numbered_list_item", "to_do", "toggle", "quote", "callout", "code",
}


def notion_configured() -> bool:
    return bool(os.getenv("NOTION_TOKEN"))


def _rich_text_to_plain(rich: list[dict[str, Any]]) -> str:
    return "".join(r.get("plain_text", "") for r in rich or [])


def blocks_to_text(blocks: list[dict[str, Any]], limit_chars: int = 2000) -> str:
    """Flatten a list of Notion block objects into plaintext (shallow)."""
    lines: list[str] = []
    for b in blocks or []:
        btype = b.get("type")
        if btype not in _TEXT_BLOCKS:
            continue
        payload = b.get(btype) or {}
        text = _rich_text_to_plain(payload.get("rich_text", []))
        if text.strip():
            lines.append(text.strip())
    joined = "\n".join(lines)
    return joined[:limit_chars]


def page_title(page: dict[str, Any]) -> str:
    """Extract a page title from a Notion search result's properties."""
    props = page.get("properties") or {}
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            return _rich_text_to_plain(prop.get("title", [])).strip()
    return ""


class NotionAPI:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("NOTION_TOKEN")
        if not self.token:
            raise LiveAuthUnavailable("NOTION_TOKEN not set — cannot pull Notion live")
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": _NOTION_VERSION,
            "Content-Type": "application/json",
        }

    def search_pages(self, page_size: int = 10) -> list[dict[str, Any]]:
        """Return page objects the integration can see (most recently edited)."""
        body = {
            "page_size": max(1, min(page_size, 100)),
            "filter": {"property": "object", "value": "page"},
            "sort": {"direction": "descending", "timestamp": "last_edited_time"},
        }
        resp = httpx.post(f"{_BASE}/search", headers=self._headers, json=body, timeout=30)
        resp.raise_for_status()
        return resp.json().get("results", [])

    def page_plaintext(self, page_id: str, max_blocks: int = 50) -> str:
        """Concatenate the top-level text blocks of a page into plaintext."""
        resp = httpx.get(
            f"{_BASE}/blocks/{page_id}/children",
            headers=self._headers,
            params={"page_size": max_blocks},
            timeout=30,
        )
        resp.raise_for_status()
        return blocks_to_text(resp.json().get("results", []))
