<p align="center">
  <img src="docs/cover.png" alt="Contxt — one private context layer for every AI" width="100%" />
</p>

# Contxt

> One context layer every AI talks to — it remembers you, acts for you, and your private data stays yours.

Portable, privacy-first context layer for every AI. Built for the **AMD Developer Hackathon ACT II** (Track 3 — Unicorn; on-device Gemma bonus).

**▶ Live demo:** https://blackx16.github.io/contxt/
**Repo:** https://github.com/Blackx16/contxt 
**Model:** [chandr1601/contxt-gateway-270m-onnx](https://huggingface.co/chandr1601/contxt-gateway-270m-onnx)

## Why
Every AI (ChatGPT, Claude, Gemini, Copilot, Grok) grew a memory in 2026 — five walled gardens, none talk to each other, and you re-introduce yourself to each one. Every memory product (Mem0, Supermemory, Letta) is cloud-first and developer-facing. Contxt is the consumer piece nobody built: **portable across every AI, and privacy-first — your crown jewels never leave your device.**

## Two surfaces, one product
- **Browser extension** (`extension/`) — the working product. Connect Gmail, Calendar & Notion (in-extension OAuth), tier every item **on-device**, inject your SHARED context into Claude/ChatGPT/Gemini live, and keep PRIVATE items encrypted on your device.
- **Web app** (`web/`, deployed to GitHub Pages) — the explainer, dashboard, and crypto/multi-device proof. A **Demo / Live** toggle (top-right) switches between the built-in demo and *your* live context read from the installed extension in real time.

## Architecture — two tiers
- **PRIVATE (crown jewels):** classified on-device (a **fine-tuned Gemma 3 270M** + deterministic rules), end-to-end encrypted. The cloud is a **blind relay** (ciphertext only) for multi-device sync. Zero-knowledge.
- **SHARED:** distilled by a cloud LLM into reusable context cards any AI can read over MCP.
- **Crown-Jewels Gateway:** the on-device router that sorts each item PRIVATE vs SHARED. It is the trust boundary — and the product.

## Cloud inference
SHARED-tier distillation and `draft_reply` run on **gpt-oss-120B via Fireworks AI** (set with `CONTXT_CLOUD_MODEL`). The on-device PRIVATE tier runs **Gemma 3 270M** via WebGPU. Every cloud call logs `contxt:cloud_llm endpoint=… model=… usage=…` for capture (`gateway/distill.py`).

## On-device model (fine-tuned)
The PRIVATE-vs-SHARED decision runs on a **fine-tuned Gemma 3 270M**, hosted at [🤗 `chandr1601/contxt-gateway-270m-onnx`](https://huggingface.co/chandr1601/contxt-gateway-270m-onnx) and loaded in-browser via Transformers.js (q4f16 ONNX, WASM). It emits the tier JSON `{"tier","sensitivity","categories","reason"}`; deterministic rules (`gateway/rules.py`) are an always-on safety floor beneath it. Fine-tuned on 1,438 train / 253 held-out rows with a PRIVATE-recall ship gate.

| Metric (253 hold-out) | Fine-tuned | Base (zero-shot) |
| --- | --- | --- |
| JSON valid | **100%** | 79.4% |
| Tier accuracy | **97.6%** | 43.1% |
| PRIVATE recall | **99.4%** | 69.0% |
| Sensitivity MAE | **0.050** | 0.475 |

Training code, dataset, and the single-source-of-truth prompt contract live in `finetune/` on branch `finetune/gemma-gateway-270m`.

## Pipeline
Ingest (Gmail + Calendar + Notion) → Gateway (on-device tier decision) → Distill (on-device Gemma for PRIVATE / cloud gpt-oss-120B for SHARED → context cards) → Store (E2E blind relay for PRIVATE; store for SHARED) → Serve over MCP (`get_context` / `draft_reply`) → any AI.

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

# Container — pull the published image (GHCR, linux/amd64), or build locally
docker run -p 8787:8787 ghcr.io/blackx16/contxt:latest      # → curl http://127.0.0.1:8787/health
#   build instead: docker build -t contxt . && docker run -p 8787:8787 contxt
```
The published image serves the HTTP bridge in **mock mode** (no API keys). For real cloud distillation, set `FIREWORKS_API_KEY` and `CONTXT_CLOUD_MODEL` in `.env` — see `.env.example`. The stdio MCP server (Claude Desktop) runs via `docker run ghcr.io/blackx16/contxt python -m server.mcp_server`.

## Stack
- **Web:** SvelteKit 2 + Svelte 5 (fully static, GitHub Pages)
- **Extension:** MV3 — Svelte popup, offscreen WebGPU Gemma runtime, content-script injection + a site bridge
- **On-device model:** fine-tuned Gemma 3 270M (q4f16 ONNX, WASM) via Transformers.js — [🤗 chandr1601/contxt-gateway-270m-onnx](https://huggingface.co/chandr1601/contxt-gateway-270m-onnx)
- **Cloud model:** gpt-oss-120B on Fireworks AI
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
