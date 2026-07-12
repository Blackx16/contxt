# Contxt — demo video script

**Target:** ≤ 4 minutes · 1440p · AMD Developer Hackathon ACT II (Track 3).
The climax is the **live injection into Claude** — linger there. Everything else sets it up.

## Pre-flight (before you hit record)
- [ ] Extension loaded (`chrome://extensions` → Load unpacked → `extension/`), **Google + Notion connected**, **On-device** mode with the model already downloaded (so no wait on camera).
- [ ] `.env` has `FIREWORKS_API_KEY` set so one real `cloud_llm` call can fire (for the AMD beat). If the key isn't ready, skip the log shot and keep the sourced claim on the slide/README.
- [ ] Live site open: **https://blackx16.github.io/contxt/** — one tab in **Live** mode, be ready to flip the top-right toggle.
- [ ] A logged-in **claude.ai/new** tab.
- [ ] DevTools console open on the offscreen doc / popup if you want to show the `contxt:cloud_llm` line.
- [ ] Hide bookmarks/extra tabs; zoom the Claude composer so the injected block + badge are both legible.

## Script

| Time | On screen | Say (beat) |
|---|---|---|
| 0:00–0:20 | You, then 5 AI logos (ChatGPT/Claude/Gemini/Copilot/Grok) | "Every AI grew a memory in 2026 — five walled gardens that don't talk to each other, so you re-introduce yourself to each one. And every memory startup is cloud-first. I built the missing piece." |
| 0:20–0:45 | Live site homepage → the two-tier block | "Contxt: one portable, privacy-first context layer for **every** AI. Two tiers — SHARED context any AI can use, and PRIVATE crown jewels that never leave your device. An **on-device gateway** decides which is which." |
| 0:45–1:30 | Extension popup: Connected as you (Google + Notion) → Refresh → live cards appear, tagged by source; point at "🔒 N private kept on-device" | "Here's the product. It's connected to my Gmail, Calendar, and Notion. It pulls my real context and classifies every item **on-device** — Gemma 270M plus deterministic rules. See the sources. And these private items? Flagged and kept local — never shown here, never sent anywhere." |
| 1:30–2:25 | **claude.ai/new** — page loads, context auto-injects into the composer, badge shows *N shared → this AI · P private kept on-device*. Ask Claude a real question that uses the context. | "The payoff. My extension just put my SHARED context into Claude automatically — and the badge shows the private cards it withheld. Claude answers me **with** my context… and it never saw the crown jewels. This works the same on ChatGPT and Gemini." *(linger)* |
| 2:25–2:55 | Back to the live site, **Live** mode, `/viewer` → the SAME live cards + a green Google/Notion connection row. Toggle top-right **Demo ↔ Live**. | "And it's one product, not two. The website, in Live mode, reads the exact same context from the extension — in real time. Flip to Demo mode and anyone can explore it without installing anything." |
| 2:55–3:25 | Site → **Devices** tab (Demo mode): Seal on A → relay shows ciphertext → QR → Decrypt on B | "Privacy, proven. A PRIVATE card is sealed on device A, relayed through the cloud as **ciphertext**, and decrypted on device B — but only after the key crosses by **QR**. The cloud never holds the key. Ciphertext alone is useless." |
| 3:25–3:55 | Console/log: `contxt:cloud_llm endpoint=… model=llama-v3p3-70b-instruct usage=…` (+ the Fireworks/AMD source on a card) | "The SHARED tier is distilled by **Llama 3.3 70B on Fireworks — which serves on AMD Instinct MI300X** via FireAttention V3. The private tier runs on-device Gemma. AMD compute end to end." |
| 3:55–4:10 | Roadmap card | "Today: web + extension across every AI. Next: fully local mobile Gemma, Signal-grade sync. One context layer, every AI — and your private data stays yours. That's Contxt." |

## Recording tips
- Keep the cursor deliberate on the **badge** during 1:30–2:25 — that's the money shot.
- If the on-device model emits noise, it silently falls back to the deterministic rules — the tiering is unaffected, so the demo is safe either way.
- Record the injection beat in one clean take; re-inject with the extension's **Re-inject** button if the composer clears.
- Narrate in your own voice; the "Say" column is a guide, not a script to read verbatim.

## Notes
- The **slide deck** (PPT) is on hold pending direct AMD-notebook GPU access; the AMD story here rests on the Fireworks→MI300X path, which is real and sourced in the README.
- Supersedes the earlier timed script in `SUBMISSION.md §2`.
