"""AES-256-GCM helpers for the Contxt two-tier store.

Key: 256-bit raw bytes, base64url-encoded as CONTXT_PRIVATE_KEY in .env.
The key lives on the user's device — the cloud SQLite file holds ciphertext only
(blind relay). The AESGCM tag is authenticated, so tampering is detected.

No libsignal. Uses the Apache-2.0 `cryptography` package only.
"""
from __future__ import annotations

import base64
import os
import sys

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _CRYPTO_OK = True
except ImportError:
    _CRYPTO_OK = False

ALGO = "AES-256-GCM"
KEY_SIZE = 32   # 256 bits
NONCE_SIZE = 12  # 96-bit nonce — GCM standard


def _require_crypto() -> None:
    if not _CRYPTO_OK:
        raise RuntimeError(
            "cryptography package missing — run: pip install -r server/requirements.txt"
        )


# ── key helpers ───────────────────────────────────────────────────────────────

def generate_key() -> bytes:
    """Generate a fresh 256-bit AES key (random, not derived)."""
    _require_crypto()
    return os.urandom(KEY_SIZE)


def key_to_b64url(key: bytes) -> str:
    return base64.urlsafe_b64encode(key).rstrip(b"=").decode()


def key_from_b64url(b64: str) -> bytes:
    # Restore base64url padding before decoding.
    rem = len(b64) % 4
    if rem:
        b64 = b64 + "=" * (4 - rem)
    return base64.urlsafe_b64decode(b64)


# ── encrypt / decrypt ─────────────────────────────────────────────────────────

def encrypt(plaintext: str | bytes, key: bytes) -> tuple[str, str]:
    """Encrypt *plaintext* with AES-256-GCM using a fresh random nonce.

    Returns:
        (ciphertext_b64url, nonce_b64url)  — both are base64url, no padding.
    """
    _require_crypto()
    if isinstance(plaintext, str):
        plaintext = plaintext.encode()
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext, None)  # no AAD
    return (
        base64.urlsafe_b64encode(ct).rstrip(b"=").decode(),
        base64.urlsafe_b64encode(nonce).rstrip(b"=").decode(),
    )


def decrypt(ciphertext_b64: str, nonce_b64: str, key: bytes) -> str:
    """Decrypt a base64url ciphertext+nonce pair.

    Returns the original plaintext as a UTF-8 string.
    Raises ``cryptography.exceptions.InvalidTag`` on wrong key or corrupt data.
    """
    _require_crypto()

    def _decode(s: str) -> bytes:
        rem = len(s) % 4
        if rem:
            s = s + "=" * (4 - rem)
        return base64.urlsafe_b64decode(s)

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(_decode(nonce_b64), _decode(ciphertext_b64), None)
    return plaintext.decode()


# ── environment helpers ───────────────────────────────────────────────────────

def load_key_from_env() -> bytes | None:
    """Return the key from CONTXT_PRIVATE_KEY, or None if unset."""
    raw = os.getenv("CONTXT_PRIVATE_KEY", "").strip()
    return key_from_b64url(raw) if raw else None


def ensure_key() -> bytes:
    """Return the private key.

    If CONTXT_PRIVATE_KEY is unset, generate one, print it to stderr for the
    user to copy into .env and the browser key-sync dialog, then return it.
    """
    key = load_key_from_env()
    if key:
        return key
    key = generate_key()
    b64 = key_to_b64url(key)
    print(
        "\n[contxt] CONTXT_PRIVATE_KEY not set — generated a new key for this session.\n"
        "  Copy it into your .env and into the browser via the key-sync dialog:\n"
        f"\n  CONTXT_PRIVATE_KEY={b64}\n",
        file=sys.stderr,
    )
    return key
