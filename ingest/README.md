# Contxt — ingest (CHA-16)

Read-only source adapters that pull from **Gmail + Calendar + Notion** and
normalize everything into one `IngestItem` shape the Crown-Jewels Gateway can
classify. First stage of the pipeline:

```
Ingest ─▶ Gateway ─▶ Distill ─▶ Store ─▶ Serve (MCP) ─▶ any AI
```

## Quick start

```bash
# Offline (default) — runs against the on-disk sample dump, no accounts needed:
python -m ingest

# Live — real pulls from your connected accounts (see setup below):
CONTXT_INGEST_LIVE=1 python -m ingest
```

Both print each item and the Gateway's PRIVATE/SHARED decision.

## The `IngestItem` contract

Every adapter emits the same shape (`ingest/models.py`), so ingest output feeds
`gateway.classify()` and `gateway.distill.distill_item()` **with no reshaping**:

| field | notes |
| --- | --- |
| `id` | stable, source-prefixed — `gmail:…` / `calendar:…` / `notion:…` |
| `source` | frozen `schema.models.Source` enum (`gmail`/`calendar`/`notion`) |
| `text` | what the Gateway classifies on (subject+body / title+notes / page text) |
| `title` | short human label |
| `timestamp` | UTC-aware `datetime` or `None` |
| `meta` | source extras (from, attendees, url…) kept for distillation |

```python
from ingest import ingest_all
from gateway.gateway import classify

for item in ingest_all(limit_per_source=10):
    decision = classify(item.to_gateway_input())   # dict: {id, source, text, title, timestamp, meta}
```

## Live vs. offline

`base.SourceAdapter.fetch()` chooses per source and **always falls back to the
sample dump on any auth/API failure**, so the demo never crashes.

| `CONTXT_INGEST_LIVE` | behaviour |
| --- | --- |
| `1` | force live (falls back to samples on error) |
| `0` | force samples (never touches the network) |
| unset | auto — live per source only if its credentials are present, else samples |

The sample dump (`ingest/samples/*.json`) is real data captured from the
connected accounts, scrubbed for the public repo. Refresh it from live with:

```bash
python -m ingest.capture           # ⚠️ review + scrub PII before committing
```

## Credentials (read-only)

Put values in the repo-root `.env` (gitignored). See `.env.example`.

- **Notion** — create an internal integration at
  <https://www.notion.so/my-integrations>, set `NOTION_TOKEN`, and **share** the
  pages with it. Token-based, no browser step.
- **Google (Gmail + Calendar)** — create an OAuth **Desktop app** client, enable
  the Gmail + Calendar APIs, save the JSON to `secrets/google_client_secret.json`.
  First live run opens a browser once for consent and writes
  `secrets/google_token.json` (auto-refreshed thereafter).

## Files

| Path | Role |
| --- | --- |
| `models.py` | `IngestItem` + `to_gateway_input()` |
| `base.py` | fetch/normalize/cap + live↔offline resolution + fallback |
| `gmail.py` · `calendar.py` · `notion.py` | per-source normalize + live pull |
| `providers/` | Google auth + Notion REST client |
| `samples/*.json` | offline sample dump |
| `capture.py` | refresh the sample dump from live |

Tests: `tests/test_ingest.py` (offline + Gateway integration) and
`tests/test_ingest_live.py` (live-payload normalization + fallback, no network).
