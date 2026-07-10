"""CHA-22 — multi-device QR key transfer + blind-relay tests.

Covers the key envelope (what the QR carries) and the BlindRelay (what the cloud
holds), then the full two-client round-trip: encrypt on A → relay ciphertext →
transfer key by QR → decrypt on B.

Run:  pytest tests/test_multidevice.py -v
"""
from __future__ import annotations

import json

import pytest

try:
    from server.crypto_utils import generate_key, key_to_b64url, key_from_b64url, encrypt, decrypt
    from server.relay import (
        BlindRelay,
        build_key_envelope,
        parse_key_envelope,
        ENVELOPE_VERSION,
    )
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="cryptography not installed")


# ── key envelope ────────────────────────────────────────────────────────────────

def test_envelope_roundtrip():
    key_b64 = key_to_b64url(generate_key())
    env = build_key_envelope(key_b64)
    parsed = json.loads(env)
    assert parsed["v"] == ENVELOPE_VERSION
    assert parsed["alg"] == "AES-256-GCM"
    assert parse_key_envelope(env) == key_b64


def test_envelope_accepts_bare_b64():
    key_b64 = key_to_b64url(generate_key())
    # A hand-pasted bare key (no JSON wrapper) must still import.
    assert parse_key_envelope(key_b64) == key_b64


def test_envelope_rejects_wrong_alg():
    key_b64 = key_to_b64url(generate_key())
    bad = json.dumps({"v": 1, "alg": "AES-128-CBC", "k": key_b64})
    with pytest.raises(ValueError):
        parse_key_envelope(bad)


def test_envelope_rejects_non_32_byte_key():
    with pytest.raises(ValueError):
        build_key_envelope("dG9vLXNob3J0")  # "too-short" — not 32 bytes
    with pytest.raises(ValueError):
        parse_key_envelope("dG9vLXNob3J0")


def test_envelope_rejects_empty():
    with pytest.raises(ValueError):
        parse_key_envelope("   ")


# ── blind relay ─────────────────────────────────────────────────────────────────

def test_relay_holds_ciphertext_only():
    relay = BlindRelay()
    key = generate_key()
    ct, nonce = encrypt("crown jewels", key)
    relay.push(id="c1", ciphertext=ct, nonce=nonce, created_at="2026-07-10T00:00:00Z")

    info = relay.inspect()
    assert info["holds_key"] is False
    assert info["fields"] == ["id", "ciphertext", "nonce", "created_at"]
    assert "key" not in info["fields"] and "k" not in info["fields"]


def test_relay_rejects_key_shaped_fields():
    relay = BlindRelay()
    key = generate_key()
    ct, nonce = encrypt("x", key)
    for bad in ("key", "k", "secret", "private_key", "aeskey"):
        with pytest.raises(ValueError):
            relay.push(
                id="c", ciphertext=ct, nonce=nonce, created_at="t",
                **{bad: key_to_b64url(key)},
            )


def test_relay_rejects_unexpected_fields():
    relay = BlindRelay()
    key = generate_key()
    ct, nonce = encrypt("x", key)
    with pytest.raises(ValueError):
        relay.push(id="c", ciphertext=ct, nonce=nonce, created_at="t", note="harmless?")


def test_relay_pull_missing_returns_none():
    assert BlindRelay().pull("nope") is None


def test_relay_record_is_opaque():
    relay = BlindRelay()
    key = generate_key()
    payload = "ICICI EMI ₹14,200 XXXX4821"
    ct, nonce = encrypt(payload, key)
    relay.push(id="c", ciphertext=ct, nonce=nonce, created_at="t")
    rec = relay.pull("c")
    assert rec is not None
    assert payload not in rec.ciphertext
    for marker in ("ICICI", "14,200", "XXXX4821"):
        assert marker not in rec.ciphertext


# ── the money-shot: two-client decrypt after QR key transfer ────────────────────

def test_two_client_decrypt_after_qr_transfer():
    relay = BlindRelay()

    # Device A seals a private card and pushes ciphertext only.
    key_a = generate_key()
    secret = json.dumps({"title": "ICICI loan EMI due", "body": "₹14,200 due 2026-07-15"})
    ct, nonce = encrypt(secret, key_a)
    relay.push(id="card_p", ciphertext=ct, nonce=nonce, created_at="2026-07-09T03:15:00Z")

    # Key crosses to Device B via the QR envelope (out-of-band, not through the relay).
    envelope = build_key_envelope(key_to_b64url(key_a))
    key_b = key_from_b64url(parse_key_envelope(envelope))
    assert key_b == key_a

    # Device B pulls the ciphertext and decrypts the SAME card locally.
    rec = relay.pull("card_p")
    assert rec is not None
    recovered = decrypt(rec.ciphertext, rec.nonce, key_b)
    assert recovered == secret
    assert json.loads(recovered)["title"] == "ICICI loan EMI due"


def test_stranger_device_cannot_decrypt_relay_blob():
    from cryptography.exceptions import InvalidTag

    relay = BlindRelay()
    key_a = generate_key()
    ct, nonce = encrypt("secret", key_a)
    relay.push(id="c", ciphertext=ct, nonce=nonce, created_at="t")

    rec = relay.pull("c")
    # A device that never received the QR key holds only ciphertext — useless.
    with pytest.raises(InvalidTag):
        decrypt(rec.ciphertext, rec.nonce, generate_key())


def test_tampered_relay_blob_rejected():
    import base64
    from cryptography.exceptions import InvalidTag

    relay = BlindRelay()
    key = generate_key()
    ct_b64, nonce = encrypt("secret", key)
    rem = len(ct_b64) % 4
    ct_bytes = bytearray(base64.urlsafe_b64decode(ct_b64 + "=" * (4 - rem if rem else 0)))
    ct_bytes[-1] ^= 0xFF  # flip an auth-tag byte
    bad_ct = base64.urlsafe_b64encode(bytes(ct_bytes)).rstrip(b"=").decode()
    relay.push(id="c", ciphertext=bad_ct, nonce=nonce, created_at="t")

    rec = relay.pull("c")
    with pytest.raises(InvalidTag):
        decrypt(rec.ciphertext, rec.nonce, key)
