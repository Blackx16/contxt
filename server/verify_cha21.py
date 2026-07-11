"""CHA-21 verification — the money-shot demo for draft_reply.

Launches the Contxt MCP server over stdio exactly like Claude Desktop would,
then calls draft_reply with a message that matches both SHARED and PRIVATE
context cards. Proves:

  1. draft_reply returns a coherent, context-aware draft string.
  2. The draft reflects SHARED context (standup, architecture).
  3. PRIVATE cards (ICICI EMI, blood test) are excluded from the cloud model.
  4. The draft itself contains no private data — the model was truly blind to it.

Run:
  python3 server/verify_cha21.py          # offline mock (no API key needed)
  FIREWORKS_API_KEY=fw-... python3 server/verify_cha21.py  # live cloud Gemma
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from server.crypto_utils import generate_key, key_to_b64url
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


_PRIVATE_LEAKAGE_MARKERS = [
    "ICICI",
    "14,200",
    "loan EMI",
    "blood test",
    "clinic",
    "fasting",
    "XXXX4821",
]

# This email mentions "doctor appointment" so it hits the PRIVATE health card as
# a keyword-ranked candidate — draft_reply then filters it out, proving exclusion.
_EMAIL = (
    "Hey — what time is our standup today? I have a doctor appointment later "
    "so want to sync on Contxt before then. Any quick notes I should catch up on?"
)


def payload_of(res):
    sc = getattr(res, "structuredContent", None)
    if isinstance(sc, dict) and sc:
        return sc
    for c in getattr(res, "content", []) or []:
        text = getattr(c, "text", None)
        if text:
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                pass
    return {}


async def main() -> int:
    # Generate a fresh AES key + temp DB so the server seeds from scratch with
    # the correct key and can decrypt private cards in-process.
    fresh_key = key_to_b64url(generate_key())
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        tmp_db = f.name

    server_env = {
        **os.environ,
        "CONTXT_PRIVATE_KEY": fresh_key,
        "CONTXT_DB": tmp_db,
        "CONTXT_MOCK_GEMMA": os.getenv("CONTXT_MOCK_GEMMA", "1"),  # offline by default
        "CONTXT_CACHE": "0",
    }

    params = StdioServerParameters(
        command=sys.executable,
        args=["server/mcp_server.py"],
        env=server_env,
    )

    try:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = {t.name for t in (await session.list_tools()).tools}
                assert "draft_reply" in tools, "draft_reply tool missing from MCP server"
                print("1. connected ✓  draft_reply tool present")

                # ── Call draft_reply with an email that triggers both tiers ────
                res = await session.call_tool("draft_reply", {"email": _EMAIL, "max_words": 120})
                p = payload_of(res)

                draft: str = p.get("draft", "")
                used_ids: list = p.get("used_card_ids", [])
                excluded: int = p.get("private_cards_excluded", -1)

                print(f"\n2. draft_reply response:")
                print(f"   used_card_ids         : {used_ids}")
                print(f"   private_cards_excluded: {excluded}")
                print(f"   draft (first 200 chars):\n     {draft[:200]!r}")

                # Criterion 1 — draft is a non-empty string
                assert isinstance(draft, str) and draft.strip(), \
                    "draft must be a non-empty string"
                print("\n3. draft is a non-empty string ✓")

                # Criterion 2 — at least one SHARED card was used
                assert used_ids, \
                    "used_card_ids must not be empty — no SHARED context was applied"
                print(f"4. used {len(used_ids)} SHARED card(s) for context ✓")

                # Criterion 3 — PRIVATE cards were excluded from the cloud model
                assert excluded > 0, (
                    f"private_cards_excluded={excluded}; expected > 0. "
                    "The store should include PRIVATE cards (ICICI EMI, doctor appointment) "
                    "that match the email but must be excluded from the cloud model."
                )
                print(f"5. {excluded} PRIVATE card(s) excluded from cloud model ✓")

                # Criterion 4 — the draft is blind to private data (money-shot)
                leaks = [m for m in _PRIVATE_LEAKAGE_MARKERS if m in draft]
                if leaks:
                    print(f"\n✗ PRIVACY LEAK: draft contains private markers: {leaks}")
                    print(f"  Full draft:\n{draft}")
                    return 1
                print("6. draft contains zero private data markers — model was truly blind ✓")

                # Criterion 5 — used_card_ids are all SHARED (belt-and-suspenders check)
                private_fixture_ids = {
                    "card_9f1c2a44-0003-4a10-8b21-000000000003",
                    "card_9f1c2a44-0004-4a10-8b21-000000000004",
                }
                leaked_ids = private_fixture_ids & set(used_ids)
                if leaked_ids:
                    print(f"\n✗ ID LEAK: private card IDs in used_card_ids: {leaked_ids}")
                    return 1
                print("7. used_card_ids contains no PRIVATE card IDs ✓")

    finally:
        Path(tmp_db).unlink(missing_ok=True)

    mode = "live cloud Gemma" if os.getenv("FIREWORKS_API_KEY") else "offline mock"
    print(f"\nCHA-21 PASS ✅  ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
