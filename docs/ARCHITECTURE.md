# Contxt — Architecture

## Two-tier context model
- **PRIVATE (crown jewels):** local Gemma distills, client-side E2E encryption, cloud stores ciphertext only (blind relay for multi-device sync). Zero-knowledge.
- **SHARED:** cloud Gemma distills, light encryption at rest, cloud-readable so any AI can use it.

## Crown-Jewels Gateway (the router)
Runs on-device — it is the trust boundary, so nothing leaves before it decides.
1. Deterministic rules force PRIVATE for obvious crown jewels (money, account/card numbers, phone, health, user keywords).
2. Gemma classifies the rest: `{tier, sensitivity, categories, reason}`.
Users control policy via simple toggles (never share: finance / family / clients).

## Classification prompt
`You are a privacy gateway. Output JSON {tier, sensitivity, categories, reason}. Always-private: {policy}.`

## Encryption
Web Crypto API: AES-256-GCM for card content; ECDH (X25519) for key agreement; QR code to transfer the key to a second device. PRIVATE cards are encrypted client-side before any upload.

## Local model
Gemma 3 270M (Q4) via Transformers.js + WebGPU inside an MV3 offscreen document; weights cached in OPFS. Fallback: Ollama sidecar.

## Deferred (roadmap)
Full local-everything · libsignal · desktop app (Tauri) · mobile on-device (Gemma 3n) · fine-tuned 270M classifier.
