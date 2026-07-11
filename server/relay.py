"""Blind relay + QR key-envelope for the multi-device flow (CHA-22).

The Python twin of ``web/src/lib/relay.ts`` + ``keyenvelope.ts``. It exists so the
multi-device claim is provable headlessly (see ``server/verify_cha22.py`` and
``tests/test_multidevice.py``), in the same runtime as the MCP server that already
decrypts PRIVATE cards.

Two moving parts, deliberately separate:

  * ``BlindRelay`` — models the cloud. Holds only ciphertext records
    ``{id, ciphertext, nonce, created_at}``. There is no key field and no code
    path that accepts one; ``push`` copies out just those four fields and rejects
    anything key-shaped. "The cloud never held the key" is thus structural.

  * key envelope — the versioned wrapper the QR carries out-of-band between the
    user's own devices. It never touches the relay.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass

ENVELOPE_VERSION = 1
_ALG = "AES-256-GCM"
_KEY_BYTES = 32  # 256-bit

# Property names the relay refuses to store — a tripwire against key leakage.
_FORBIDDEN_FIELDS = {"key", "k", "secret", "privatekey", "private_key", "aeskey"}


# ── key envelope ──────────────────────────────────────────────────────────────

def _b64url_len(b64: str) -> int:
    rem = len(b64) % 4
    padded = b64 + "=" * (4 - rem) if rem else b64
    return len(base64.urlsafe_b64decode(padded))


def _is_valid_key_b64(b64: str) -> bool:
    try:
        return _b64url_len(b64) == _KEY_BYTES
    except Exception:
        return False


def build_key_envelope(key_b64: str) -> str:
    """Wrap a base64url key into the versioned envelope string a QR will carry."""
    if not _is_valid_key_b64(key_b64):
        raise ValueError("refusing to wrap a non-32-byte key")
    return json.dumps({"v": ENVELOPE_VERSION, "alg": _ALG, "k": key_b64})


def parse_key_envelope(payload: str) -> str:
    """Parse a scanned/pasted QR payload back to a base64url key.

    Accepts the JSON envelope or a bare base64url key. Raises on anything that
    does not yield a valid 32-byte key.
    """
    text = payload.strip()
    if not text:
        raise ValueError("empty payload")

    if text.startswith("{"):
        try:
            env = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("malformed envelope JSON") from exc
        alg = env.get("alg")
        if alg and alg != _ALG:
            raise ValueError(f"unsupported alg: {alg}")
        k = env.get("k")
        if not isinstance(k, str) or not _is_valid_key_b64(k):
            raise ValueError("envelope has no valid key")
        return k

    if not _is_valid_key_b64(text):
        raise ValueError("not a valid 32-byte base64url key")
    return text


# ── blind relay ────────────────────────────────────────────────────────────────

@dataclass
class RelayRecord:
    id: str
    ciphertext: str
    nonce: str
    created_at: str


class BlindRelay:
    """In-memory ciphertext-only relay. Never accepts or returns a key."""

    def __init__(self) -> None:
        self._records: dict[str, RelayRecord] = {}

    def push(self, *, id: str, ciphertext: str, nonce: str, created_at: str, **extra) -> None:
        """Store one ciphertext record. Any key-shaped extra field is rejected."""
        for prop in extra:
            if prop.lower() in _FORBIDDEN_FIELDS:
                raise ValueError(f'refused: record carries forbidden field "{prop}"')
        if extra:
            raise ValueError(f"unexpected fields on relay record: {sorted(extra)}")
        if not id or not ciphertext or not nonce:
            raise ValueError("record must have id, ciphertext and nonce")
        self._records[id] = RelayRecord(
            id=id, ciphertext=ciphertext, nonce=nonce, created_at=created_at
        )

    def pull(self, id: str) -> RelayRecord | None:
        rec = self._records.get(id)
        return RelayRecord(**vars(rec)) if rec else None

    def list(self) -> list[RelayRecord]:
        return [RelayRecord(**vars(r)) for r in self._records.values()]

    def clear(self) -> None:
        self._records.clear()

    def inspect(self) -> dict:
        """Structural self-report — ``holds_key`` is False by construction."""
        return {
            "count": len(self._records),
            "fields": ["id", "ciphertext", "nonce", "created_at"],
            "holds_key": False,
        }
