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

Cross-origin lockdown: responses are readable cross-origin only by trusted
browser origins (chrome-extension://, localhost) — never a blanket "*", so an
arbitrary website that reaches the loopback port cannot read your SHARED cards.
Set CONTXT_BRIDGE_TOKEN to additionally require an X-Contxt-Token on data routes.

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
# Bind host. Defaults to loopback (safe on a dev machine — not reachable off-box);
# the Docker image sets 0.0.0.0 so the container is reachable via `-p`.
DEFAULT_HOST = os.getenv("CONTXT_BRIDGE_HOST", "127.0.0.1")

# CORS: only browser origins we trust may read responses cross-origin. The MV3
# background worker (extension origin) fetches with host_permissions and needs
# no CORS at all, so a random website that reaches 127.0.0.1 gets no
# Access-Control-Allow-Origin header and the browser blocks it from reading the
# body. Non-browser clients (curl) send no Origin and are unaffected.
_ALLOWED_ORIGIN_PREFIXES = (
    "chrome-extension://",
    "moz-extension://",
    "http://localhost",
    "http://127.0.0.1",
)

# Optional shared secret. When CONTXT_BRIDGE_TOKEN is set, data routes require it
# via the X-Contxt-Token header (or ?token=). Unset (default) → no token check;
# the origin restriction above is the baseline guard.
_TOKEN = os.getenv("CONTXT_BRIDGE_TOKEN") or None


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "ContxtBridge/1.0"

    # ── low-level helpers ──────────────────────────────────────────────────────

    def _cors(self) -> None:
        # Never a blanket "*": that would let ANY website the user visits fetch
        # 127.0.0.1:8787 and read their SHARED context cards. Only echo an
        # allow-origin for trusted browser origins (the extension / localhost).
        # The MV3 background worker fetches with host_permissions and needs no
        # CORS at all; a random site gets no header and the browser blocks it.
        origin = self.headers.get("Origin")
        if origin and origin.startswith(_ALLOWED_ORIGIN_PREFIXES):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Contxt-Token")

    def _authorized(self, params: dict | None = None) -> bool:
        # Optional shared-secret gate. Off unless CONTXT_BRIDGE_TOKEN is set.
        if not _TOKEN:
            return True
        supplied = self.headers.get("X-Contxt-Token")
        if not supplied and params:
            supplied = (params.get("token") or [None])[0]
        return supplied == _TOKEN

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
            if not self._authorized(params):
                return self._json({"error": "unauthorized"}, 401)
            query = (params.get("query", [""])[0]).strip()
            try:
                limit = int(params.get("limit", ["8"])[0])
            except ValueError:
                limit = 8
            # include_private=False → SHARED only + private_withheld count.
            return self._json(context_payload(query, limit, include_private=False))

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
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            email = str(body.get("email", "")).strip()
            if not email:
                return self._json({"error": "missing 'email' field"}, 400)
            max_words = int(body.get("max_words", 150))
            return self._json(draft_reply_payload(email, max_words))

        return self._json({"error": f"unknown route {route}"}, 404)


def build_server(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> ThreadingHTTPServer:
    """Construct the bridge server (bound, not yet serving).

    Exposed so tests (server/verify_cha26.py) can run it in a background thread.
    """
    return ThreadingHTTPServer((host, port), BridgeHandler)


def serve(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> None:
    httpd = build_server(port, host)
    print(
        f"[contxt-bridge] serving on http://{host}:{port}  "
        f"(routes: /health /get_context /draft_reply)",
        file=sys.stderr,
    )
    print(
        "[contxt-bridge] /get_context serves SHARED cards only — "
        "PRIVATE plaintext never crosses this bridge.",
        file=sys.stderr,
    )
    print(
        "[contxt-bridge] CORS locked to extension/localhost origins"
        + (" · token required" if _TOKEN else " · no token (set CONTXT_BRIDGE_TOKEN to require one)"),
        file=sys.stderr,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[contxt-bridge] shutting down.", file=sys.stderr)
        httpd.shutdown()


if __name__ == "__main__":
    serve()
