# Contxt

> One context layer every AI talks to — it remembers you AND acts for you, and your private data stays yours.

Portable, privacy-first context layer. Built for the **AMD Developer Hackathon ACT II** (Track 3 — Unicorn + Gemma bonus).

## Why
Every AI (ChatGPT, Claude, Gemini, Copilot, Grok) shipped memory in 2026 — five walled gardens, none talk to each other. Every memory product (Mem0, Supermemory, Letta, OpenBrain) is cloud-first and developer-facing. Contxt is **consumer-facing, portable across every AI, and privacy-first.**

## Architecture — two tiers
- **PRIVATE (crown jewels):** classified on-device, distilled by local Gemma, end-to-end encrypted. Cloud is a blind relay (ciphertext only) for multi-device sync. Zero-knowledge.
- **SHARED:** distilled by cloud Gemma, lightly encrypted, any AI can use it directly.
- **Crown-Jewels Gateway:** the on-device router (Gemma + deterministic rules) that sorts each item PRIVATE vs SHARED. Users control it with simple toggles. It is the trust boundary — and the product.

## Pipeline
Ingest (Gmail + Calendar + Notion) -> Gateway (tier decision, on-device) -> Distill (local/cloud Gemma -> context cards) -> Store (E2E blind relay for PRIVATE; cloud store for SHARED) -> Serve over MCP (`get_context` / `draft_reply`) -> any AI.

## Multi-device (QR key transfer)
The PRIVATE key never touches the cloud. To bring your context to a second device, Device A shows the key as a QR envelope; Device B scans (or pastes) it, pulls the ciphertext from the blind relay, and decrypts the same card locally. Only ciphertext moves through the cloud — the relay structurally has no key field.
- Demo: run the web app → **Devices** tab (`web/src/routes/multi-device`).
- Proof: `python3 server/verify_cha22.py` · tests: `pytest tests/test_multidevice.py`.

## Stack
- Frontend: SvelteKit web app + browser extension
- Local model: Gemma 3 270M (Q4) via Transformers.js + WebGPU (MV3 offscreen document); Ollama sidecar fallback
- Cloud model: Gemma on Fireworks / AMD Dev Cloud
- Encryption: Web Crypto API (AES-256-GCM + ECDH), QR key transfer for multi-device
- Server: Python MCP server

## Repo layout
| Path | What |
| --- | --- |
| `ingest/` | Read-only source adapters (Gmail + Calendar + Notion) → normalized `IngestItem[]` |
| `schema/` | Frozen shared contract — context-card JSON Schema + Python/TS mirrors |
| `gateway/` | Crown-Jewels Gateway — rules + Gemma classifier |
| `server/` | Python MCP server (`get_context`, `draft_reply`) + blind relay (`relay.py`) |
| `web/` | SvelteKit app — onboarding, context viewer, multi-device QR key transfer |
| `extension/` | MV3 browser extension — offscreen Transformers.js runtime |
| `docs/` | Architecture |

## Status
Locked 2026-07-08. **Deadline: 2026-07-11 21:30 IST.**

## Team
Chandraveer Singh Solanki · Theerth K.R.

## License
AGPL-3.0
