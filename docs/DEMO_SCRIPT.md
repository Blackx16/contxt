# Contxt — demo video (silent, caption-driven)

No voiceover, no narration. Just a screen recording with short on-screen text
captions. Target **~75–90 seconds**, 1440p, 30fps. The one beat to linger on is
the **live injection into Claude**.

## Setup (before recording)
- Extension loaded, **Google + Notion connected**, **On-device** mode with the model already downloaded.
- Tabs ready: the **popup**, `claude.ai/new`, and the live site (**https://blackx16.github.io/contxt/**).
- Hide bookmarks bar and other extensions; zoom the Claude composer so the injected block + badge are legible.
- Capture at 1440p. Add captions in your editor (CapCut / Premiere / DaVinci) — big, bottom-center, 2–4 words, on screen ~2.5s each.

## Shot list

| # | Duration | Screen (what to record) | Caption (on-screen text) |
|---|---|---|---|
| 1 | 0:00–0:04 | Black screen → the Contxt logo fades in, then the wordmark | **Contxt** |
| 2 | 0:04–0:09 | Cut to logo + tagline card | *One private context layer for every AI* |
| 3 | 0:09–0:16 | Extension popup — "Connect your sources": Google (Gmail + Calendar) + Notion, both showing **Connected** | *Connects Gmail, Calendar & Notion* |
| 4 | 0:16–0:24 | Popup "Your context" → click the **Private** tab; the on-device private items are listed | *Sensitive items detected on-device* |
| 5 | 0:24–0:30 | Still on Private tab — cursor points at "kept on-device · flagged: …" | *Kept on your device — never uploaded* |
| 6 | 0:30–0:36 | Click the **Shared** tab; the shareable cards list | *Only safe context is shareable* |
| 7 | 0:36–0:52 | Switch to **claude.ai/new**. Page loads → the SHARED context auto-injects into the composer → the badge appears (*N shared → this AI · P private kept on-device*). **Hold on the badge.** | *Auto-injected into Claude* → then *Private data withheld* |
| 8 | 0:52–1:00 | Type a real question in Claude that uses the context; send; Claude answers using it | *Answers with your context* |
| 9 | 1:00–1:10 | Cut to the live site (**Live** mode) `/viewer`: Google + Notion logos in the connection row, the same shared cards, the masked-private note. Toggle one **privacy rule** off → a card moves from Private into Shared | *Same context, on the web — in real time* |
| 10 | 1:10–1:20 | Site → **Devices** tab (Demo): Seal on Device A → relay shows ciphertext → QR → Decrypt on Device B (identical card) | *Private sync: ciphertext + QR key — cloud never sees it* |
| 11 | 1:20–1:28 | Closing card: logo + links | *blackx16.github.io/contxt · github.com/Blackx16/contxt* |

## Editing notes
- **No voiceover.** A light background music bed (low volume, no lyrics) is optional — keep it subtle.
- Keep captions to 2–4 words; let the UI do the talking. Don't explain the story — just label what's on screen.
- Use quick, clean cuts (no long fades except the intro/outro). Speed up any loading spinner (the model is pre-downloaded, so there shouldn't be one).
- The **injection beat (#7)** is the payoff — give it the most screen time and a caption pause.
- If the on-device model ever emits noise, it silently falls back to deterministic rules; the tiering is unaffected, so the demo is safe either way.
- Export 1080p or 1440p MP4 (H.264), ~8–12 Mbps.
