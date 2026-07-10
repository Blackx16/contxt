"""Refresh the on-disk sample dump from a live pull.

    python -m ingest.capture                 # all sources
    python -m ingest.capture gmail notion     # specific sources
    python -m ingest.capture --limit 8

Pulls live (read-only) and overwrites ingest/samples/<source>.json with the raw
records, so the offline demo dump reflects current real data. Requires the same
credentials as a live pull (see .env.example).

⚠️  The repo is PUBLIC. Review the regenerated JSON and scrub PII (account /
order numbers, phone numbers, sensitive bodies) before committing it.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Load repo-root .env so GOOGLE_*/NOTION_TOKEN take effect for the live pull.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from . import ADAPTERS

_SAMPLES = Path(__file__).parent / "samples"


def capture(sources: list[str], limit: int) -> int:
    written = 0
    by_name = {a.source.value: a for a in ADAPTERS}
    targets = sources or list(by_name)
    for name in targets:
        adapter = by_name.get(name)
        if adapter is None:
            print(f"  skip: unknown source {name!r}")
            continue
        try:
            records = adapter._fetch_raw_live(limit)  # noqa: SLF001 - capture is an ingest-internal tool
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: live pull failed ({exc}); left sample dump untouched")
            continue
        out = _SAMPLES / adapter.sample_file
        out.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n")
        print(f"  {name}: wrote {len(records)} records → {out.relative_to(Path.cwd())}"
              if out.is_relative_to(Path.cwd()) else f"  {name}: wrote {len(records)} records → {out}")
        written += 1
    return written


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(description="Refresh ingest sample dump from live sources")
    parser.add_argument("sources", nargs="*", help="gmail calendar notion (default: all)")
    parser.add_argument("--limit", type=int, default=10, help="max records per source")
    args = parser.parse_args()

    print("Capturing live records (read-only)…")
    n = capture(args.sources, args.limit)
    if n:
        print("\n⚠️  Public repo — review and scrub PII before committing the JSON.")
    else:
        print("\nNothing captured. Configure credentials (see .env.example) or check --limit.")
        sys.exit(1)


if __name__ == "__main__":
    main()
