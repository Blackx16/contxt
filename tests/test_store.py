"""CHA-19 — round-trip test: encrypt → store → decrypt.

Tests the full two-tier store without any server/MCP wiring.
Run:  pytest tests/test_store.py -v
"""
from __future__ import annotations

import json
import tempfile

import pytest

try:
    from server.crypto_utils import generate_key, encrypt, decrypt, key_to_b64url, key_from_b64url
    from server.store import TwoTierStore
    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

pytestmark = pytest.mark.skipif(not HAS_DEPS, reason="cryptography not installed")


# ── crypto_utils ──────────────────────────────────────────────────────────────

def test_encrypt_decrypt_roundtrip():
    key = generate_key()
    plaintext = json.dumps({"title": "ICICI EMI", "body": "₹14,200 due 2026-07-15"})
    ct, nonce = encrypt(plaintext, key)
    # ciphertext must not be the plaintext
    assert plaintext not in ct
    # round-trip must recover original
    assert decrypt(ct, nonce, key) == plaintext


def test_different_keys_produce_different_ciphertext():
    key1, key2 = generate_key(), generate_key()
    ct1, _ = encrypt("same plaintext", key1)
    ct2, _ = encrypt("same plaintext", key2)
    assert ct1 != ct2


def test_fresh_nonce_each_call():
    key = generate_key()
    _, nonce1 = encrypt("hello", key)
    _, nonce2 = encrypt("hello", key)
    assert nonce1 != nonce2, "nonces must be random (unique per call)"


def test_wrong_key_raises():
    from cryptography.exceptions import InvalidTag
    key1, key2 = generate_key(), generate_key()
    ct, nonce = encrypt("secret", key1)
    with pytest.raises(InvalidTag):
        decrypt(ct, nonce, key2)


def test_tampered_ciphertext_raises():
    from cryptography.exceptions import InvalidTag
    import base64
    key = generate_key()
    ct_b64, nonce = encrypt("secret", key)
    # Decode, flip a byte in the GCM auth tag (last 16 bytes), re-encode.
    rem = len(ct_b64) % 4
    ct_bytes = bytearray(base64.urlsafe_b64decode(ct_b64 + "=" * (4 - rem if rem else 0)))
    ct_bytes[-1] ^= 0xFF  # flip auth-tag byte — GCM must reject this
    bad_ct = base64.urlsafe_b64encode(bytes(ct_bytes)).rstrip(b"=").decode()
    with pytest.raises(InvalidTag):
        decrypt(bad_ct, nonce, key)


def test_key_serialisation_roundtrip():
    key = generate_key()
    assert key_from_b64url(key_to_b64url(key)) == key


# ── TwoTierStore ──────────────────────────────────────────────────────────────

def test_store_shared_roundtrip():
    with tempfile.TemporaryDirectory() as tmp:
        store = TwoTierStore(f"{tmp}/test.db")
        store.put_shared(
            id="card_s_001",
            data={"title": "Contxt standup", "tier": "shared"},
            created_at="2026-07-10T00:00:00Z",
        )
        rows = store.get_all_shared()
        assert len(rows) == 1
        assert rows[0]["title"] == "Contxt standup"


def test_store_private_is_opaque():
    with tempfile.TemporaryDirectory() as tmp:
        store = TwoTierStore(f"{tmp}/test.db")
        key = generate_key()
        payload = "ICICI EMI ₹14,200"
        ct, nonce = encrypt(payload, key)
        store.put_private(
            id="card_p_001",
            ciphertext=ct,
            nonce=nonce,
            created_at="2026-07-10T00:00:00Z",
        )
        raw = store.get_all_private_raw()
        assert len(raw) == 1
        # The store returns ciphertext — not the original payload
        assert raw[0]["ciphertext"] != payload
        assert raw[0]["ciphertext"] == ct  # untouched


def test_store_private_decrypt_locally():
    with tempfile.TemporaryDirectory() as tmp:
        store = TwoTierStore(f"{tmp}/test.db")
        key = generate_key()
        payload = json.dumps({"title": "Blood test", "body": "Fasting before 09:00"})
        ct, nonce = encrypt(payload, key)
        store.put_private(id="card_p_002", ciphertext=ct, nonce=nonce, created_at="2026-07-10T01:00:00Z")

        row = store.get_all_private_raw()[0]
        recovered = decrypt(row["ciphertext"], row["nonce"], key)
        assert json.loads(recovered)["title"] == "Blood test"


def test_store_private_wrong_key_raises():
    from cryptography.exceptions import InvalidTag
    with tempfile.TemporaryDirectory() as tmp:
        store = TwoTierStore(f"{tmp}/test.db")
        key = generate_key()
        ct, nonce = encrypt("secret", key)
        store.put_private(id="card_p_003", ciphertext=ct, nonce=nonce, created_at="2026-07-10T02:00:00Z")

        row = store.get_all_private_raw()[0]
        with pytest.raises(InvalidTag):
            decrypt(row["ciphertext"], row["nonce"], generate_key())


def test_store_counts_and_empty():
    with tempfile.TemporaryDirectory() as tmp:
        store = TwoTierStore(f"{tmp}/test.db")
        assert store.is_empty()

        key = generate_key()
        ct, nonce = encrypt("x", key)
        store.put_private(id="p1", ciphertext=ct, nonce=nonce, created_at="2026-07-10T00:00:00Z")
        store.put_shared(id="s1", data={"x": 1}, created_at="2026-07-10T00:00:00Z")

        c = store.counts()
        assert c["private"] == 1
        assert c["shared"] == 1
        assert not store.is_empty()


def test_store_upsert():
    with tempfile.TemporaryDirectory() as tmp:
        store = TwoTierStore(f"{tmp}/test.db")
        store.put_shared(id="card_s_1", data={"v": 1}, created_at="2026-07-10T00:00:00Z")
        store.put_shared(id="card_s_1", data={"v": 2}, created_at="2026-07-10T00:00:00Z")
        rows = store.get_all_shared()
        assert len(rows) == 1
        assert rows[0]["v"] == 2, "second put should overwrite (INSERT OR REPLACE)"
