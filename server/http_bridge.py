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

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
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

# ── Notion OAuth token exchange ─────────────────────────────────────────────
# Notion's token endpoint authenticates with Basic base64(client_id:client_secret),
# so the secret CANNOT live in the browser extension. The extension gets the auth
# `code` via chrome.identity and POSTs it here; the bridge exchanges it. Env is
# already loaded (server.mcp_server calls load_dotenv on import above).
_NOTION_CLIENT_ID = os.getenv("NOTION_OAUTH_CLIENT_ID") or ""
_NOTION_SECRET = os.getenv("NOTION_OAUTH_SECRET") or ""

# macOS python.org builds ship no CA bundle, so urllib's HTTPS to Notion fails
# with CERTIFICATE_VERIFY_FAILED. Use certifi's bundle when available; fall back
# to the system default (Docker slim, Linux) otherwise.
try:
    import certifi

    _SSL_CTX = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL_CTX = ssl.create_default_context()


def _notion_token_exchange(code: str, redirect_uri: str) -> dict:
    if not (_NOTION_CLIENT_ID and _NOTION_SECRET):
        return {"error": "bridge is missing NOTION_OAUTH_CLIENT_ID / NOTION_OAUTH_SECRET"}
    basic = base64.b64encode(f"{_NOTION_CLIENT_ID}:{_NOTION_SECRET}".encode()).decode()
    payload = {"grant_type": "authorization_code", "code": code}
    if redirect_uri:
        payload["redirect_uri"] = redirect_uri
    req = urllib.request.Request(
        "https://api.notion.com/v1/oauth/token",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15, context=_SSL_CTX) as r:
            data = json.loads(r.read().decode())
    except urllib.error.HTTPError as exc:
        return {"error": f"notion HTTP {exc.code}: {exc.read().decode()[:300]}"}
    except Exception as exc:  # URLError/SSL/timeout — return cleanly, never crash the handler
        return {"error": f"notion exchange failed: {exc}"}
    # Return only what the extension needs (never log the access token).
    return {
        "ok": True,
        "access_token": data.get("access_token"),
        "workspace_name": data.get("workspace_name"),
        "workspace_id": data.get("workspace_id"),
        "bot_id": data.get("bot_id"),
    }

DEFAULT_PORT = int(os.getenv("CONTXT_BRIDGE_PORT", "8787"))
# Bind host. Defaults to loopback (safe on a dev machine — not reachable off-box);
# the Docker image sets 0.0.0.0 so the container is reachable via `-p`.
DEFAULT_HOST = os.getenv("CONTXT_BRIDGE_HOST", "127.0.0.1")

# CORS: only browser origins we trust may read responses cross-origin. The MV3
# background worker (extension origin) fetches with host_permissions and needs
# no CORS at all, so a random website that reaches 127.0.0.1 gets no
# Access-Control-Allow-Origin header and the browser blocks it from reading the
# body. Non-browser clients (curl) send no Origin and are unaffected.
_ALLOWED_EXTENSION_SCHEMES = (
    "chrome-extension",
    "moz-extension",
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
        if not origin:
            return

        allowed = False
        try:
            parsed = urlparse(origin)
            if parsed.scheme in _ALLOWED_EXTENSION_SCHEMES:
                allowed = True
            elif parsed.hostname in ("localhost", "127.0.0.1"):
                allowed = True
        except ValueError:
            pass

        if allowed:
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

        if route == "/notion/exchange":
            if not self._authorized():
                return self._json({"error": "unauthorized"}, 401)
            code = str(body.get("code", "")).strip()
            if not code:
                return self._json({"error": "missing 'code' field"}, 400)
            redirect_uri = str(body.get("redirect_uri", "")).strip()
            result = _notion_token_exchange(code, redirect_uri)
            return self._json(result, 200 if result.get("ok") else 502)

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
