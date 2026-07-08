# Contxt — the shared contract (CHA-15)

The single data contract every other piece builds against. **Define once, freeze early**
so the Pipeline, MCP server, and UI can work in parallel against the mock fixtures.

## Files

| File | Role |
| --- | --- |
| `context_card.schema.json` | **Canonical** JSON Schema (draft 2020-12). Source of truth. |
| `types.ts` | TypeScript mirror for the SvelteKit web app + MV3 extension. |
| `models.py` | Python (pydantic v2) mirror for the MCP server + Gateway. |
| `fixtures/cards.json` | 3–4 mock context cards (mix of private/shared) — code against these. |
| `fixtures/tier_decisions.json` | Sample Gateway envelopes (`gateway.Decision`). |
| `fixtures/get_context_response.json` | Sample MCP `get_context` response. |

`context_card.schema.json` is authoritative. `types.ts` and `models.py` are hand-kept
mirrors — **change all three together, or not at all.**

## The three shapes

### 1. Context card
One distilled unit of context.
`id · tier · source · title · summary · body · entities · sensitivity_score · created_at · embedding_ref` (+ optional `encryption`, `meta`).

- `tier`: `"private"` | `"shared"`.
- **SHARED** cards are served over MCP as-is.
- **PRIVATE** cards are decrypted client-side and never leave the device in plaintext.
  At rest in the cloud blind relay they carry an `encryption` block (AES-256-GCM) and
  `summary`/`body` are `null` (see `cards.json` card #3). On-device they may be plaintext
  with `embedding_ref` under a `local:` namespace (card #4).

### 2. Tier-decision envelope
What the Crown-Jewels Gateway emits **per ingested item, before distillation**:
`tier · sensitivity_score · categories · reason` (+ optional `source_ref`).
Maps 1:1 to `gateway.Decision`.

### 3. MCP tool I/O
- `get_context(query, limit?) -> { cards: ContextCard[] }` — SHARED cards only.
- `draft_reply(email, max_words?) -> { draft, used_card_ids[] }` — the demo's agentic action.

## Conventions (locked)
- `tier` and `source` are **lowercase** enums in the wire contract.
  Per _[parse, don't validate](https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/)_,
  the `Tier` enum **value IS the wire value** (`"private"` / `"shared"`) — parse once at the
  Gateway boundary, serialize with no transform. `Tier._missing_` tolerates model/legacy casing
  (`"PRIVATE"`) at the boundary but canonicalizes to the single lowercase representation.
- `sensitivity_score` is the one name (not `sensitivity`) across card + envelope.
- `id` format: `card_<uuidv4>`.
- Timestamps: ISO 8601 / RFC 3339, UTC (`...Z`).
- Objects are `additionalProperties: false` except `meta` (free-form connector data).

## Verify
```bash
# Python: pydantic parse of all fixtures
python -m schema.models

# JSON Schema validation of every card (needs: pip install jsonschema)
python schema/validate.py
```

## Blocks
CHA-17 (Gateway classifier) · CHA-18 (cloud distillation) · CHA-20 (MCP `get_context`) · UI context viewer.
