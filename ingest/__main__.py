"""Run the ingest step and feed each item straight into the Crown-Jewels Gateway.

    python -m ingest

Demonstrates CHA-16's "Done when": a normalized IngestItem[] from all three
sources, at least one real item from each, feeding the Gateway with no
reshaping. Runs fully offline against the on-disk sample dump.
"""
from __future__ import annotations

import logging
from collections import Counter
from pathlib import Path

# Load repo-root .env so GOOGLE_*/NOTION_TOKEN/CONTXT_INGEST_LIVE take effect.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

from gateway.gateway import classify

from . import ingest_all


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(message)s")

    items = ingest_all(limit_per_source=10)
    by_source = Counter(i.source.value for i in items)
    print(
        f"Ingested {len(items)} items  ("
        + ", ".join(f"{k}={v}" for k, v in sorted(by_source.items()))
        + ")"
    )
    print("-" * 78)

    tiers: Counter[str] = Counter()
    for it in items:
        # The integration contract: ingest output feeds the Gateway unchanged.
        decision = classify(it.to_gateway_input())
        tiers[decision.tier.value] += 1
        cats = ", ".join(decision.categories) if decision.categories else "-"
        print(f"  {decision.tier.value:7} {it.source.value:8} {it.title[:44]:44} [{cats}]")

    print("-" * 78)
    print("Gateway routed:  " + ", ".join(f"{k}={v}" for k, v in sorted(tiers.items())))
    print(
        "\nPRIVATE items stay on-device (crown jewels); SHARED items go to the "
        "cloud distiller.\nNote: offline, only deterministic rules run — wiring "
        "local/cloud Gemma adds nuance."
    )


if __name__ == "__main__":
    main()
