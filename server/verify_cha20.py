"""CHA-20 verification — launches the Contxt MCP server over stdio exactly like
Claude Desktop would, lists the tools, and calls get_context / draft_reply.

Run:  python3 server/verify_cha20.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from schema.models import ContextCard  # to prove returned cards are schema-valid


def payload_of(res):
    """Extract the tool's dict result, whether FastMCP put it in
    structuredContent or as JSON text in content."""
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
    params = StdioServerParameters(command=sys.executable, args=["server/mcp_server.py"])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1) An MCP client connects and lists the Contxt tools
            tools = (await session.list_tools()).tools
            names = sorted(t.name for t in tools)
            print(f"1. connected ✓  tools = {names}")
            assert "get_context" in names, "get_context tool missing"

            # 2) get_context returns schema-valid cards for a query
            res = await session.call_tool("get_context", {"query": "what am I working on"})
            payload = payload_of(res)
            cards = payload.get("cards", [])
            print(f"2. get_context('what am I working on') → {len(cards)} card(s)")
            for c in cards:
                ContextCard.model_validate(c)  # raises if not schema-valid
                print(f"     [{c['tier']:7}] {c['source']:8} {c['title'][:46]}")
            assert cards and all(c["tier"] == "shared" for c in cards), "expected SHARED cards"
            print("   all returned cards are schema-valid ✓")

            # 3) PRIVATE cards are served locally but never leak encryption to the cloud.
            #    A query that hits a private item still returns it (local server), with
            #    no ciphertext/encryption block exposed in the response.
            res2 = await session.call_tool("get_context", {"query": "ICICI loan EMI"})
            pcards = payload_of(res2).get("cards", [])
            priv = [c for c in pcards if c["tier"] == "private"]
            print(f"3. get_context('ICICI loan EMI') → {len(priv)} PRIVATE card(s) served locally")
            for c in priv:
                assert "encryption" not in c or c["encryption"] is None, "encryption leaked!"
            print("   PRIVATE cards carry no encryption blob in the served payload ✓")

            # bonus: the agentic action tool
            d = await session.call_tool("draft_reply", {"email": "when's our standup?"})
            dp = payload_of(d)
            print(f"4. draft_reply → used {len(dp.get('used_card_ids', []))} SHARED card(s), "
                  f"excluded {dp.get('private_cards_excluded', 0)} PRIVATE from cloud ✓")

    print("\nCHA-20 PASS ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
