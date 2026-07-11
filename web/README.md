# Contxt — web app

The marketing + interactive-demo surface for **Contxt**, a portable, privacy-first
context layer for every AI. This is one of two surfaces:

- **Web app (this folder)** — explains the two-tier model and *proves* the crypto:
  a fully client-side demo of on-device classification, client-side encryption, and
  cross-device key transfer by QR.
- **Browser extension (`../extension`)** — the working product: connects Gmail /
  Calendar / Notion, tiers context on-device, and injects the SHARED tier into
  Claude / ChatGPT / Gemini live.

## Pages

| Route | What it shows |
|-------|---------------|
| `/` | The pitch: one context layer, two tiers (Private / Shared). |
| `/onboarding` | Connect sources (Gmail, Calendar, Notion). |
| `/viewer` | Distilled context cards, filterable by tier, with in-browser decrypt/lock and key sync. |
| `/multi-device` | Seal on Device A → relay ciphertext → transfer key by QR → decrypt on Device B. The "cloud is a blind relay" proof. |

## Tech

- **SvelteKit 2 + Svelte 5** (runes), TypeScript, Vite.
- **Web Crypto API** (AES-256-GCM + ECDH) — encryption/decryption runs in the browser; keys never touch a server.
- **Fully static** (`@sveltejs/adapter-static`, every route prerendered) — no server, deploys anywhere.

## Develop

```sh
npm install
npm run dev        # http://localhost:5173
```

## Build

```sh
npm run build      # → build/  (static)
npm run preview    # serve the production build locally
```

## Deploy

Pushing to `main` (or running the **Deploy web to GitHub Pages** workflow) builds
with `BASE_PATH=/contxt` and publishes `build/` to GitHub Pages at
`https://<owner>.github.io/contxt/`. Relative asset paths mean it also works at
the domain root, so any static host (Netlify, Cloudflare Pages, Vercel) works too.
