# Contxt

> One context layer every AI talks to — it remembers you, acts for you, and your private data stays yours.

Portable, privacy-first context layer for every AI. Built for the **AMD Developer Hackathon ACT II** (Track 3 — Unicorn; on-device Gemma bonus).

**▶ Live demo:** https://blackx16.github.io/contxt/ &nbsp;·&nbsp; **Repo:** https://github.com/Blackx16/contxt

## Why
Every AI (ChatGPT, Claude, Gemini, Copilot, Grok) grew a memory in 2026 — five walled gardens, none talk to each other, and you re-introduce yourself to each one. Every memory product (Mem0, Supermemory, Letta) is cloud-first and developer-facing. Contxt is the consumer piece nobody built: **portable across every AI, and privacy-first — your crown jewels never leave your device.**

## Two surfaces, one product
- **Browser extension** (`extension/`) — the working product. Connect Gmail, Calendar & Notion (in-extension OAuth), tier every item **on-device**, inject your SHARED context into Claude/ChatGPT/Gemini live, and keep PRIVATE items encrypted on your device.
- **Web app** (`web/`, deployed to GitHub Pages) — the explainer, dashboard, and crypto/multi-device proof. A **Demo / Live** toggle (top-right) switches between the built-in demo and *your* live context read from the installed extension in real time.

## Architecture — two tiers
- **PRIVATE (crown jewels):** classified on-device (Gemma 3 270M + deterministic rules), end-to-end encrypted. The cloud is a **blind relay** (ciphertext only) for multi-device sync. Zero-knowledge.
- **SHARED:** distilled by a cloud LLM into reusable context cards any AI can read over MCP.
- **Crown-Jewels Gateway:** the on-device router that sorts each item PRIVATE vs SHARED. It is the trust boundary — and the product.

## AMD compute
Contxt's SHARED-tier distillation and `draft_reply` run on **Llama 3.3 70B via Fireworks AI**, which serves inference on **AMD Instinct™ MI300X** GPUs using Fireworks' clean-sheet AMD kernel, **FireAttention V3**. The Fireworks credits are issued through the **AMD AI Developer Program**. The on-device PRIVATE tier runs **Gemma 3 270M** via WebGPU. Every cloud call logs `contxt:cloud_llm endpoint=… model=… usage=…` for capture (`gateway/distill.py`).
- Sources: [Fireworks is powered by AMD](https://fireworks.ai/partners/amd) · [FireAttention V3 — MI300X, benchmarked on Llama 8B/70B](https://fireworks.ai/blog/fireattention-v3)

## Pipeline
Ingest (Gmail + Calendar + Notion) → Gateway (on-device tier decision) → Distill (on-device Gemma for PRIVATE / cloud Llama for SHARED → context cards) → Store (E2E blind relay for PRIVATE; store for SHARED) → Serve over MCP (`get_context` / `draft_reply`) → any AI.

## The browser extension
Connect your sources, choose **On-device** (downloads Gemma 270M once via WebGPU) or **Online only**, and Contxt pulls your recent Gmail/Calendar/Notion, tiers each item **on-device**, and shows your SHARED context + a "🔒 N private kept on-device" count. On Claude/ChatGPT/Gemini it auto-injects your SHARED cards into the composer with a badge — *N shared → this AI · P private kept on-device*. Crown-jewel plaintext is never put on the wire.

```sh
# Load it (unpacked, dev):
#   chrome://extensions → Developer mode → Load unpacked → select ./extension
```
- The extension bridges to the deployed web app (content script), so the site shows *your* live context and connection state in real time.
- Optional local bridge for the seeded/offline path: `python3 server/http_bridge.py` → `http://127.0.0.1:8787`.
- Proof: `python3 server/verify_cha26.py` (boots the bridge, asserts zero private leakage).

## Multi-device (QR key transfer)
The PRIVATE key never touches the cloud. Device A shows the key as a QR envelope; Device B scans (or pastes) it, pulls the ciphertext from the blind relay, and decrypts the same card locally. Only ciphertext moves through the cloud — the relay structurally has no key field.
- Demo: web app → **Devices** tab. Proof: `python3 server/verify_cha22.py`.

## Run
```sh
# Web app (static; deploys anywhere)
cd web && npm install && npm run dev        # http://localhost:5173

# Server / HTTP bridge (mock mode — no API keys needed)
python3 server/http_bridge.py               # http://127.0.0.1:8787

# Container (serves the bridge in mock mode)
docker build -t contxt . && docker run -p 8787:8787 contxt
```
For real cloud distillation, set `FIREWORKS_API_KEY` (AMD Dev Program) and `CONTXT_CLOUD_MODEL` in `.env` — see `.env.example`. The stdio MCP server (Claude Desktop) runs via `docker run contxt python -m server.mcp_server`.

## Stack
- **Web:** SvelteKit 2 + Svelte 5 (fully static, GitHub Pages)
- **Extension:** MV3 — Svelte popup, offscreen WebGPU Gemma runtime, content-script injection + a site bridge
- **On-device model:** Gemma 3 270M (fp16) via Transformers.js + WebGPU
- **Cloud model:** Llama 3.3 70B on Fireworks → AMD Instinct MI300X
- **Encryption:** Web Crypto API (AES-256-GCM + ECDH), QR key transfer
- **Server:** Python MCP server (`get_context`, `draft_reply`) + local HTTP bridge + blind relay

## Repo layout
| Path | What |
| --- | --- |
| `ingest/` | Read-only source adapters (Gmail + Calendar + Notion) → normalized `IngestItem[]` |
| `schema/` | Frozen shared contract — context-card JSON Schema + Python/TS mirrors |
| `gateway/` | Crown-Jewels Gateway — deterministic rules + Gemma classifier + cloud distill |
| `server/` | MCP server + HTTP bridge (`http_bridge.py`) + blind relay (`relay.py`) |
| `web/` | SvelteKit app — landing, onboarding, context viewer (Demo/Live), multi-device QR |
| `extension/` | MV3 extension — Svelte popup (`ui-src/`), offscreen Gemma, injection + site bridge |
| `docs/` | Architecture, demo script |

## Team
Chandraveer Singh Solanki · Theerth K.R.

## License
AGPL-3.0
