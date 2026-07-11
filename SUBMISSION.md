# Contxt — AMD Developer Hackathon ACT II · Submission Kit

> One context layer every AI talks to — it remembers you AND acts for you, and your private data stays yours.
> Track 3 (Unicorn) + Gemma bonus. Deadline 2026-07-11 21:30 IST.

---

## 1. Form copy (paste into lablab)

**Title (≤50 chars)** — pick one:
- `Contxt: one private context layer for every AI` (46)
- `Contxt — your portable, private AI context` (42)

**Short description (≤255 chars):**
> Every AI shipped memory in 2026 — five walled gardens that don't talk to each other. Contxt is the portable, privacy-first context layer that gives any AI (Claude, ChatGPT, Gemini) your context while a local Gemma gateway keeps your crown jewels encrypted on-device.

**Long description (≥100 words):**
> In 2026 every assistant grew a memory — and none of them share it, so you re-introduce yourself to each one. Every memory product (Mem0, Supermemory, Letta) is cloud-first and built for developers. Contxt is the consumer product nobody built: a portable, privacy-first context layer that works across every AI and keeps private data on your device.
>
> A Crown-Jewels Gateway runs on-device (Gemma 3 270M + deterministic rules) and sorts each item into two tiers. SHARED context is distilled by cloud Gemma and served to any AI over MCP. PRIVATE "crown jewels" are distilled locally, end-to-end encrypted, and the cloud is only a blind relay of ciphertext — synced across devices by a QR key transfer, decrypted locally. A browser extension injects your SHARED context into Claude/ChatGPT/Gemini live, and visibly withholds the private cards. The AI helps you using what you chose to share; it never sees the rest. That guarantee is enforced structurally — the transport that feeds the browser serves shared cards only.

**Tags:** `mcp` `gemma` `fireworks` `amd` `privacy` `context` `agents` `browser-extension` `sveltekit`

---

## 2. Five-minute demo script (timed)

**Pre-flight (do this before you hit record):**
- [ ] `CONTXT_MOCK_GEMMA=` unset and `FIREWORKS_API_KEY` set → real cloud Gemma (or `AMD_CLOUD_ENDPOINT` for the MI300X run).
- [ ] `python3 server/http_bridge.py` running (so the badge is NOT "demo data").
- [ ] Store seeded: `python3 server/verify_cha26.py` shows 2 shared / 2 private.
- [ ] ⚠️ Test the on-device gateway output once — the `gemma-3-270m` ONNX/WebGPU q4f16 garbage bug. If the popup classifier emits junk, switch dtype to `fp32` or lean on the rules fallback for the recording.
- [ ] A private item ready (e.g. the ICICI loan line) and the cloud SQLite open in a terminal.

| Time | Show | Say (beat) |
|---|---|---|
| 0:00–0:30 | You, then 5 AI logos | "Every AI has memory now — five walled gardens, none talk to each other, and every one re-asks who you are. And the memory startups are all cloud-first. So I built the missing piece." |
| 0:30–1:10 | `docs/ARCHITECTURE.md` diagram | "Contxt ingests Gmail/Calendar/Notion. An **on-device** Crown-Jewels Gateway — Gemma 270M plus rules — sorts every item into two tiers: SHARED, and PRIVATE crown jewels. That gateway is the trust boundary." |
| 1:10–1:35 | Extension popup: paste the ICICI line → PRIVATE (gold); paste a work note → SHARED (patina) | "On-device tiering. The loan is classified PRIVATE and never leaves. The work note is SHARED — cloud Gemma distills it into a reusable context card." |
| 1:35–2:40 | **claude.ai** — page loads, context auto-injects, badge shows *2 shared → this AI · 2 private kept on-device*. Ask Claude a real question. | "Here's the payoff. My extension put my SHARED context into Claude automatically — and the badge shows two private cards were withheld. Claude answers me *with* my context, and it never saw the crown jewels." *(This is the climax — linger here.)* |
| 2:40–3:20 | Terminal: `sqlite3 data/contxt.db "SELECT id, substr(ciphertext,1,40) FROM private_cards;"` → ciphertext. Then the Devices tab: QR → 2nd client decrypts the same card. | "Proof, not promise. Open the cloud store — the private cards are opaque ciphertext. The key only ever moved device-to-device by QR. A second device pulls the same blob and decrypts it locally." |
| 3:20–4:10 | Fireworks call logs (`contxt:cloud_gemma …`); then the MI300X `rocm-smi` + `vllm.log` screenshots | "SHARED distillation and the draft-reply action run on **Gemma via Fireworks**. And here's the same pipeline running on an **AMD MI300X** in AMD Dev Cloud — Gemma 3 27B on vLLM/ROCm." |
| 4:10–4:40 | draft_reply in Claude Desktop (MCP) → drafted reply + "0 private forwarded" | "One agentic action: a context-aware draft reply over MCP — grounded in shared context, private cards excluded from the cloud model." |
| 4:40–5:00 | Roadmap slide | "Today: web + extension. Next: fully local, mobile on-device Gemma 3n, Signal-grade sync. One context layer, every AI, your private data stays yours. That's Contxt." |

**Recording tips:** 1440p, hide bookmarks/extra tabs, zoom the composer so the injected block + badge are both legible, keep the cursor deliberate on the badge during 1:35–2:40.

---

## 3. Submission checklist status
- [x] Public GitHub repo + README (Blackx16/contxt)
- [x] Feature-complete build (CHA-26 = the last build issue; PR #1)
- [x] Containerized — **verified**: `docker run -p 8787:8787 contxt` serves `/health` + `/get_context` (mock mode, no keys). Fixed a missing `COPY schema/` that ran the server degraded.
- [ ] Cover image (16:9)
- [ ] Video ≤5 min, ≤300MB (script above)
- [ ] Slide deck
- [ ] Live demo URL
- [ ] Merge PR #1 so `main` is current for judges
- [ ] Re-check prize pool on the lablab page ($10k vs pinned $21k)
