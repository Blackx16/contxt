"""Contxt MCP server — serves context to any AI client.

Tools:
  - get_context(query): return relevant SHARED context cards. PRIVATE cards are
    decrypted client-side and are never served from the cloud.
  - draft_reply(email): the one agentic action for the demo.

Stub: wire the store + cloud Gemma where marked TODO.
"""
from __future__ import annotations

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # keep importable before deps are installed
    FastMCP = None

app = FastMCP("contxt") if FastMCP else None


def _search_shared_cards(query: str):
    # TODO: query the cloud store (SQLite + vector index) for SHARED cards.
    return [{"card": "stub", "query": query}]


if app:
    @app.tool()
    def get_context(query: str):
        """Return SHARED context cards relevant to the query."""
        return _search_shared_cards(query)

    @app.tool()
    def draft_reply(email: str) -> str:
        """Draft a context-aware reply (the demo's agentic action)."""
        cards = _search_shared_cards(email)
        # TODO: call cloud Gemma with (email + cards) to draft.
        return f"[draft using {len(cards)} context card(s)]"


if __name__ == "__main__":
    if app:
        app.run()
    else:
        print("Install deps first: pip install -r server/requirements.txt")
