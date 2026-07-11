"""CHA-22 verification — the money-shot for multi-device QR key transfer.

Proves portability end-to-end, headlessly, in the same runtime as the MCP server:

  1. Device A encrypts a PRIVATE card locally with its own key.
  2. Only the ciphertext moves through a blind relay (the cloud) — never the key.
  3. The key crosses to Device B out-of-band, in the QR key envelope.
  4. Device B pulls the ciphertext and decrypts the SAME card locally.

And the two guarantees that make it real:

  * A device WITHOUT the transferred key cannot read the relay blob (InvalidTag).
  * The relay never held a key — structurally (no key field, key-shaped pushes rejected).

Run:
  python3 server/verify_cha22.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cryptography.exceptions import InvalidTag

from server.crypto_utils import generate_key, key_to_b64url, key_from_b64url, encrypt, decrypt
from server.relay import BlindRelay, build_key_envelope, parse_key_envelope

_FIXTURES = Path(__file__).parent.parent / "schema" / "fixtures" / "cards.json"
_DEMO_CARD_ID = "card_9f1c2a44-0004-4a10-8b21-000000000004"  # blood-test — PRIVATE (health)

# Markers that must NEVER appear in anything the relay holds.
_PRIVATE_MARKERS = ["blood test", "clinic", "Fasting", "prescription", "2026-07-14"]


def _load_demo_card() -> dict:
    cards = json.loads(_FIXTURES.read_text())
    card = next(c for c in cards if c["id"] == _DEMO_CARD_ID)
    # The private payload Device A seals (mirrors the store: content minus index cols).
    return {
        "title": card["title"],
        "summary": card["summary"],
        "body": card["body"],
        "entities": card["entities"],
    }


def main() -> int:
    relay = BlindRelay()

    # ── Device A — has the key, seals the card ────────────────────────────────
    key_a = generate_key()
    key_a_b64 = key_to_b64url(key_a)
    secret = _load_demo_card()
    plaintext = json.dumps(secret, ensure_ascii=False)
    ct, nonce = encrypt(plaintext, key_a)
    print("1. Device A sealed the card locally ✓  (AES-256-GCM)")

    # ── Relay — ciphertext only ───────────────────────────────────────────────
    relay.push(id=_DEMO_CARD_ID, ciphertext=ct, nonce=nonce, created_at="2026-07-09T03:15:00Z")
    info = relay.inspect()
    assert info["holds_key"] is False, "relay must never report holding a key"
    assert "key" not in info["fields"] and "k" not in info["fields"], "relay fields leak a key column"
    print(f"2. Pushed to blind relay — holds {info['fields']}, holds_key={info['holds_key']} ✓")

    # The relay's stored record must be opaque — no private marker in the clear.
    rec = relay.pull(_DEMO_CARD_ID)
    assert rec is not None
    blob_str = f"{rec.id}{rec.ciphertext}{rec.nonce}{rec.created_at}"
    leaked = [m for m in _PRIVATE_MARKERS if m in blob_str]
    assert not leaked, f"relay record leaks plaintext markers: {leaked}"
    print("3. Relay record is opaque — zero plaintext markers ✓")

    # Structural tripwire: the relay refuses a key-shaped push.
    for bad_field in ("key", "k", "secret"):
        try:
            relay.push(
                id="evil", ciphertext=ct, nonce=nonce, created_at="x", **{bad_field: key_a_b64}
            )
        except ValueError:
            pass
        else:
            print(f"✗ relay accepted a forbidden field '{bad_field}'")
            return 1
    print("4. Relay rejects any key-shaped field ✓  (cloud cannot hold the key)")

    # ── Negative — a device without the key cannot read the blob ──────────────
    key_stranger = generate_key()
    try:
        decrypt(rec.ciphertext, rec.nonce, key_stranger)
    except InvalidTag:
        print("5. A device WITHOUT the key fails to decrypt the relay blob ✓  (ciphertext alone is useless)")
    else:
        print("✗ PRIVACY BREAK: relay blob decrypted without the correct key")
        return 1

    # ── QR key transfer A → B (out-of-band) ───────────────────────────────────
    envelope = build_key_envelope(key_a_b64)
    print(f"\n6. QR key envelope (what the QR encodes, key redacted): "
          f'{{"v":1,"alg":"AES-256-GCM","k":"{key_a_b64[:8]}…"}}')
    key_b_b64 = parse_key_envelope(envelope)
    key_b = key_from_b64url(key_b_b64)
    assert key_b == key_a, "transferred key must equal Device A's key"
    print("7. Device B imported the key from the QR envelope — identical to A ✓")

    # ── Device B — pull ciphertext, decrypt locally ───────────────────────────
    rec_b = relay.pull(_DEMO_CARD_ID)
    assert rec_b is not None
    recovered = decrypt(rec_b.ciphertext, rec_b.nonce, key_b)
    assert recovered == plaintext, "Device B decrypt must match Device A's plaintext exactly"
    recovered_card = json.loads(recovered)
    assert recovered_card["title"] == secret["title"]
    print("8. Device B decrypted the SAME card locally — byte-for-byte match ✓")
    print(f"     recovered title  : {recovered_card['title']!r}")
    print(f"     recovered summary: {recovered_card['summary'][:60]!r}…")

    print("\nCHA-22 PASS ✅  key: A→B via QR · ciphertext: A→relay→B · cloud never held the key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
