#!/usr/bin/env python3
"""Contxt HTTP bridge — the browser-facing transport for the MCP tools.

Why this exists
---------------
The MCP server (server/mcp_server.py) speaks **stdio** — that's how Claude
Desktop and other MCP clients talk to it. A browser extension **cannot** speak
stdio. So the Contxt extension talks to this thin HTTP shim instead, which calls
the *same* ``get_context`` / ``draft_reply`` logic the MCP server exposes.

    One source of truth (server/mcp_server.py), two transports:
      • stdio  → MCP clients (Claude Desktop)          [mcp_server.py]
      • HTTP   → the browser extension (this file)      [http_bridge.py]

Privacy by construction
-----------------------
``/get_context`` serves **SHARED cards only** and returns a ``private_withheld``
count. PRIVATE plaintext never crosses this bridge, because the browser injects
retrieved context straight into a cloud AI (Claude / ChatGPT / Gemini web). The
crown jewels physically cannot leak through here — the route never serializes
them. That is the whole Contxt thesis, enforced at the transport boundary.

Routes
------
  GET  /health                         → { ok, shared, private }
  GET  /get_context?query=…&limit=8    → { cards:[SHARED…], private_withheld, … }
  POST /draft_reply  {email,max_words} → { draft, used_card_ids, private_cards_excluded }
  OPTIONS *                            → CORS preflight (204)

Run
---
  python3 server/http_bridge.py                 # http://127.0.0.1:8787
  CONTXT_BRIDGE_PORT=9000 python3 server/http_bridge.py

Depends only on the Python stdlib. No Flask, no FastAPI, no extra install.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

# Allow `python server/http_bridge.py` from the repo root.
sys.path.insert(0, str(Path(__file__).parent.parent))

# Reuse the exact tool logic the MCP server uses.
from server.mcp_server import context_payload, draft_reply_payload  # noqa: E402

try:  # store counts for /health — best-effort, never fatal
    from server.mcp_server import _get_store
except Exception:  # pragma: no cover
    _get_store = None

DEFAULT_PORT = int(os.getenv("CONTXT_BRIDGE_PORT", "8787"))


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "ContxtBridge/1.0"

    # ── low-level helpers ──────────────────────────────────────────────────────

    def _cors(self) -> None:
        # The extension reaches us from the background service worker (which has
        # host_permissions), but permissive CORS also lets you curl/test from a
        # page or the web app during the demo.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # keep stdout clean
        sys.stderr.write("[contxt-bridge] " + (fmt % args) + "\n")

    # ── verbs ──────────────────────────────────────────────────────────────────

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        route = parsed.path.rstrip("/") or "/"
        params = parse_qs(parsed.query)

        if route == "/health":
            counts = {"shared": 0, "private": 0}
            if _get_store is not None:
                try:
                    counts = _get_store().counts()
                except Exception as exc:  # pragma: no cover
                    return self._json({"ok": False, "error": str(exc)}, 500)
            return self._json({"ok": True, **counts})

        if route == "/get_context":
            query = (params.get("query", [""])[0]).strip()
            try:
                limit = int(params.get("limit", ["8"])[0])
            except ValueError:
                limit = 8
            # include_private=False → SHARED only + private_withheld count.
            payload = context_payload(query, limit, include_private=False)
            payload.setdefault("source", "bridge")
            return self._json(payload)

        return self._json({"error": f"unknown route {route}"}, 404)

    def do_POST(self) -> None:  # noqa: N802
        route = urlparse(self.path).path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return self._json({"error": "invalid JSON body"}, 400)

        if route == "/draft_reply":
            email = str(body.get("email", "")).strip()
            if not email:
                return self._json({"error": "missing 'email' field"}, 400)
            max_words = int(body.get("max_words", 150))
            return self._json(draft_reply_payload(email, max_words))

        return self._json({"error": f"unknown route {route}"}, 404)


def build_server(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Construct the bridge server (bound, not yet serving).

    Exposed so tests (server/verify_cha26.py) can run it in a background thread.
    """
    return ThreadingHTTPServer(("127.0.0.1", port), BridgeHandler)


def serve(port: int = DEFAULT_PORT) -> None:
    httpd = build_server(port)
    print(
        f"[contxt-bridge] serving on http://127.0.0.1:{port}  "
        f"(routes: /health /get_context /draft_reply)",
        file=sys.stderr,
    )
    print(
        "[contxt-bridge] /get_context serves SHARED cards only — "
        "PRIVATE plaintext never crosses this bridge.",
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[contxt-bridge] shutting down.", file=sys.stderr)
        httpd.shutdown()


if __name__ == "__main__":
    serve()
