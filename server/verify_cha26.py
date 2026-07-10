"""CHA-26 verification — the inject-into-any-AI bridge, end to end.

Proves the transport the browser extension relies on:

  1. The HTTP bridge boots and reports store health.
  2. /get_context returns SHARED-only context cards the extension can inject,
     with an always-on `private_total` trust count.
  3. THE MONEY-SHOT: querying a PRIVATE topic ("ICICI loan EMI") returns the
     crown jewel as `private_withheld`, and NONE of its plaintext (nor any
     ciphertext/nonce) crosses the bridge into the card payload.
  4. /draft_reply (offline mock) drafts from SHARED cards and reports how many
     PRIVATE cards it excluded from the cloud model.

Run:  python3 server/verify_cha26.py

Self-contained: uses a fresh temp DB seeded from the fixtures, so it passes on
any machine (teammate, CI) with no .env or prior state required.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Deterministic, machine-independent run: offline draft + throwaway DB.
os.environ["CONTXT_MOCK_GEMMA"] = "1"
os.environ["CONTXT_DB"] = str(Path(tempfile.mkdtemp(prefix="contxt_cha26_")) / "contxt.db")

from server.http_bridge import build_server  # noqa: E402

PORT = int(os.getenv("CONTXT_BRIDGE_PORT", "8799"))
BASE = f"http://127.0.0.1:{PORT}"


def _get(path: str):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return r.status, dict(r.headers), json.loads(r.read().decode())


def _post(path: str, obj: dict):
    data = json.dumps(obj).encode()
    req = urllib.request.Request(
        BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status, json.loads(r.read().decode())


def main() -> int:
    httpd = build_server(PORT)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        # 1) health
        st, _, health = _get("/health")
        assert st == 200 and health.get("ok"), f"health failed: {health}"
        print(f"1. bridge up ✓  health = {health}")

        # 2) get_context → SHARED-only, injectable, with a private_total trust count
        st, headers, ctx = _get("/get_context?query=" + urllib.parse.quote("what am I working on"))
        assert st == 200, f"get_context status {st}"
        assert "application/json" in headers.get("Content-Type", ""), "not JSON"
        assert headers.get("Access-Control-Allow-Origin") == "*", "missing CORS header"
        cards = ctx.get("cards", [])
        assert cards, "expected at least one SHARED card to inject"
        assert all(c["tier"] == "shared" for c in cards), "non-SHARED card served to the browser!"
        assert "private_total" in ctx, "missing private_total trust count"
        print(
            f"2. get_context → {len(cards)} SHARED card(s) to inject, "
            f"{ctx['private_total']} private on-device (never served) ✓"
        )
        for c in cards:
            print(f"     [{c['tier']:6}] {c['source']:8} {c['title'][:44]}")

        # 3) MONEY-SHOT: a PRIVATE query. The crown jewel is counted as withheld,
        #    and its plaintext never appears in the served cards.
        st, _, priv = _get("/get_context?query=" + urllib.parse.quote("ICICI loan EMI"))
        served_cards_blob = json.dumps(priv.get("cards", [])).lower()
        leaked = [w for w in ("icici", "emi", "ciphertext", "nonce") if w in served_cards_blob]
        assert priv.get("private_withheld", 0) >= 1, "expected a PRIVATE card to be withheld"
        assert not leaked, f"PRIVATE plaintext/ciphertext leaked across the bridge: {leaked}"
        assert all(c["tier"] == "shared" for c in priv.get("cards", [])), "served a PRIVATE card!"
        print(
            f"3. get_context('ICICI loan EMI') → {priv['private_withheld']} PRIVATE card withheld; "
            f"zero private plaintext crossed the bridge ✓  (money-shot)"
        )

        # 4) draft_reply (offline mock) drafts from SHARED, excludes PRIVATE
        st, d = _post("/draft_reply", {"email": "when's our standup?", "max_words": 60})
        assert st == 200 and d.get("draft"), f"draft_reply failed: {d}"
        print(
            f"4. draft_reply → drafted from {len(d.get('used_card_ids', []))} SHARED card(s), "
            f"excluded {d.get('private_cards_excluded', 0)} PRIVATE from the cloud ✓"
        )

        print("\nCHA-26 PASS ✅  — the extension can pull SHARED context and inject it into any AI,")
        print("                and the crown jewels never leave the device.")
        return 0
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
