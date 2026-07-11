"""Validate every fixture against context_card.schema.json (draft 2020-12).

    pip install jsonschema
    python schema/validate.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

HERE = Path(__file__).parent
SCHEMA = json.loads((HERE / "context_card.schema.json").read_text())
DEFS = SCHEMA["$defs"]


def _validator(def_name: str) -> Draft202012Validator:
    """A validator bound to one $defs shape, resharing the same $defs registry."""
    sub = {"$schema": SCHEMA["$schema"], "$defs": DEFS, "$ref": f"#/$defs/{def_name}"}
    return Draft202012Validator(sub)


def _check(def_name: str, items, label: str) -> int:
    v = _validator(def_name)
    errors = 0
    for i, item in enumerate(items):
        for err in v.iter_errors(item):
            errors += 1
            print(f"  ✗ {label}[{i}] {list(err.path)}: {err.message}")
    if not errors:
        print(f"  ✓ {label}: {len(items)} valid against {def_name}")
    return errors


def main() -> int:
    total = 0
    cards = json.loads((HERE / "fixtures/cards.json").read_text())
    total += _check("ContextCard", cards, "cards.json")

    decisions = json.loads((HERE / "fixtures/tier_decisions.json").read_text())
    total += _check("TierDecision", decisions, "tier_decisions.json")

    resp = json.loads((HERE / "fixtures/get_context_response.json").read_text())
    total += _check("GetContextResponse", [resp], "get_context_response.json")

    print("\nAll fixtures valid." if total == 0 else f"\n{total} validation error(s).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
