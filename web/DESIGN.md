# Contxt — Design System

Adapted from **Impeccable** (github.com/pbakaus/impeccable, impeccable.style) — its
anti-slop discipline and the "Neo-Kinpaku" aesthetic, mapped onto Contxt's own semantics.

## North star

A crafted, technical, privacy-first object: warm dark lacquer surfaces, two brand
anchors, hairline structure, almost no decorative shadow. Restraint in chrome,
brilliance where an element carries brand weight.

**The two anchors map to Contxt's tiers:**

- **Kinpaku gold = PRIVATE** (the crown jewels). CTAs, active state, the wordmark mark,
  encrypted-card panel, on-device markers.
- **Verdigris patina = SHARED** (cloud-readable). Shared tags, shared sensitivity meters.

## Tokens

Source of truth: `src/app.css` (`:root`). All color is OKLCH.

| Role | Token | Value |
| --- | --- | --- |
| Page ground | `--lacquer` | `oklch(7% 0.006 95)` (warm, never pure black) |
| Deepest inset | `--lacquer-deep` | `oklch(4% 0.004 95)` |
| Panels / cards | `--raised` | `oklch(11% 0.006 95)` |
| Inactive surface | `--graphite` / `--graphite-2` | `oklch(15% / 19% …)` |
| Headlines | `--champagne` | `oklch(91% 0 0)` |
| Body | `--text` | `oklch(88% 0 0)` |
| Muted / faint | `--text-muted` / `--text-faint` | `oklch(72% / 62% 0 0)` |
| PRIVATE accent | `--gold` | `oklch(84% 0.19 80.46)` |
| SHARED accent | `--patina` | `oklch(70% 0.12 188)` |
| Default rule | `--rule` | `oklch(78% 0 0 / 0.14)` (hairline) |
| Active rule | `--rule-strong` | `oklch(74% 0.09 82 / 0.55)` (gold) |
| Warning | `--vermilion` | `oklch(58% 0.15 35)` (sparingly) |

Radii are small: `--r-xs 2px` … `--r-lg 8px`. Spacing on an 8px rhythm.

## Typography

- **Display** (`h1`, `h2`): **Alumni Sans**. Weight-inversion — `h1` is thin **100**, `h2`
  is heavier **300**. The hero breathes; section anchors ground the page.
- **Body / UI**: **Albert Sans**. Everything below ~1.2rem uses this face, never the thin
  display cut. Body line-height 1.7, measure capped ~65–75ch.
- **Mono** (eyebrows, tags, meta, labels): system mono, tracked uppercase, kept short.
- Wordmark: Alumni Sans 400, uppercase, letter-spacing 0.15em.

Fonts load from Google Fonts in `src/app.html`, with Arial/system fallbacks.

## Rules (what keeps it out of the AI-slop bucket)

- No Inter / system-default body font; no purple→blue gradients, neon, glow, or glass.
- No pure black / pure white — surfaces are tinted warm.
- Hairline borders before shadow; cards are flat and sharply bounded.
- **No side-tab left-border accents** on cards. **No cards nested inside cards** — group
  on a single plinth split by a hairline seam (see the landing two-tier block).
- No rounded-square icon tile stacked above every heading.
- Motion is a quiet ease — no bounce/elastic.
- One accent carries brand per moment; gold and patina have meaning, not decoration.

## Components

- `.btn` / `.btn-primary` (gold fill, dark text) / `.btn-secondary` (gold outline).
- `.tag` + `.tag-private` (gold) / `.tag-shared` (patina) — slim mono chips.
- `.eyebrow`, `.mono` — tracked labels.
- Cards: `--raised` bg, `--rule` border, `--r-lg`, flat; hover lifts 2px + gold-hairline.
- Encrypted PRIVATE card: an **inset** `--lacquer-deep` panel (a distinct material, not a
  nested card) showing ciphertext + crypto meta only — the demo money-shot.
