"""SQLite two-tier store for Contxt context cards.

Schema
------
  private_cards (id TEXT PRIMARY KEY, ciphertext TEXT, nonce TEXT, created_at TEXT)
  shared_cards  (id TEXT PRIMARY KEY, data TEXT NOT NULL,          created_at TEXT)

The ``ciphertext`` column holds AES-256-GCM encrypted card JSON.
The ``data`` column holds plaintext card JSON for SHARED cards (cloud-readable).

The store never decrypts PRIVATE cards — that is the caller's job (mcp_server.py
with the local key). A party who only has the SQLite file sees opaque ciphertext.

Opening the DB file directly shows the money-shot:
  $ sqlite3 data/contxt.db "SELECT id, substr(ciphertext,1,40) FROM private_cards;"
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


class TwoTierStore:
    def __init__(self, db_path: str | Path = "data/contxt.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    # ── internal ──────────────────────────────────────────────────────────────

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS private_cards (
                    id          TEXT PRIMARY KEY,
                    ciphertext  TEXT NOT NULL,
                    nonce       TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS shared_cards (
                    id          TEXT PRIMARY KEY,
                    data        TEXT NOT NULL,
                    created_at  TEXT NOT NULL
                );
            """)

    # ── PRIVATE tier (blind relay — store never decrypts) ────────────────────

    def put_private(
        self, *, id: str, ciphertext: str, nonce: str, created_at: str
    ) -> None:
        """Store an encrypted card. The store is a blind relay — no decryption here."""
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO private_cards(id, ciphertext, nonce, created_at) "
                "VALUES (?, ?, ?, ?)",
                (id, ciphertext, nonce, created_at),
            )

    def get_all_private_raw(self) -> list[dict]:
        """Return all PRIVATE rows as raw dicts (ciphertext intact, never decrypted)."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, ciphertext, nonce, created_at "
                "FROM private_cards ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── SHARED tier (cloud-readable plaintext) ────────────────────────────────

    def put_shared(self, *, id: str, data: dict, created_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO shared_cards(id, data, created_at) VALUES (?, ?, ?)",
                (id, json.dumps(data, ensure_ascii=False), created_at),
            )

    def get_all_shared(self) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT data FROM shared_cards ORDER BY created_at DESC"
            ).fetchall()
        return [json.loads(r["data"]) for r in rows]

    # ── housekeeping ──────────────────────────────────────────────────────────

    def counts(self) -> dict[str, int]:
        with self._connect() as conn:
            priv = conn.execute("SELECT COUNT(*) FROM private_cards").fetchone()[0]
            shared = conn.execute("SELECT COUNT(*) FROM shared_cards").fetchone()[0]
        return {"private": priv, "shared": shared}

    def is_empty(self) -> bool:
        c = self.counts()
        return c["private"] == 0 and c["shared"] == 0
