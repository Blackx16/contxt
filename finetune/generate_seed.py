#!/usr/bin/env python3
"""Rules-oracle seed generator — free, deterministic, guaranteed-correct rows.

Pass-1 deterministic rules (gateway/rules.py) are an oracle: anything they match
is *definitely* PRIVATE. We use that to mint a few hundred anchor examples with
zero labeling risk, plus a matched set of obviously-SHARED items. This:
  1. bootstraps the dataset before Kimi runs,
  2. guarantees the safety-critical PRIVATE patterns are represented, and
  3. gives Kimi concrete gold examples to imitate (paste a few into KIMI_PROMPT).

Emits the COMPACT interchange schema (same one Kimi produces) — one JSON object
per line. finetune/validate.py expands these into the ready-to-train chat format.

Usage:
    python finetune/generate_seed.py --n 320 --out finetune/dataset/raw/seed.jsonl
"""
from __future__ import annotations

import argparse
import json
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gateway.rules import rule_hits  # noqa: E402
from finetune.prompt import CATEGORIES  # noqa: E402

RNG = random.Random(42)

INR = ["Rs 45,000", "₹1,20,000", "Rs 8.5 lakh", "₹2.3 crore", "Rs 12,500", "₹95,000"]
USD = ["$2,400", "$18,000", "$1.2M", "$450", "$96,000"]
BANKS = ["ICICI", "HDFC", "RBL", "Axis", "SBI", "Kotak"]
NAMES = ["Priya", "Rahul", "Aditya", "Meera", "Sarah", "David", "Chen", "Fatima"]
ORGS = ["Acme", "Zenith", "Nimbus", "Contoso", "Globex", "GSFC Agrotech"]

# (text builder, semantic category to add, sensitivity band). tier + rule
# categories are DERIVED from rule_hits() so they can never disagree with Pass-1.
PRIVATE_TEMPLATES = [
    (lambda: f"Your {RNG.choice(BANKS)} loan EMI of {RNG.choice(INR)} is due on the 5th.", "money", (0.9, 1.0)),
    (lambda: f"Salary credited: {RNG.choice(INR)} for this month.", "finance", (0.85, 0.98)),
    (lambda: f"{RNG.choice(ORGS)} Q3 revenue hit {RNG.choice(USD)}, up 20%.", "finance", (0.8, 0.95)),
    (lambda: f"Invoice #{RNG.randint(1000,9999)} for {RNG.choice(USD)} is overdue.", "finance", (0.75, 0.92)),
    (lambda: f"Card ending {RNG.randint(1000,9999)}: {RNG.randint(4000,4999)} {RNG.randint(1000,9999)} {RNG.randint(1000,9999)} {RNG.randint(1000,9999)}", "card", (0.95, 1.0)),
    (lambda: f"A/c {RNG.randint(100000,999999)} debited by {RNG.choice(INR)}.", "account", (0.9, 1.0)),
    (lambda: f"Call me on +91 {RNG.randint(70000,99999)}{RNG.randint(10000,99999)} after 6pm.", "phone", (0.55, 0.75)),
    (lambda: "Blood test report shows high cholesterol; doctor prescribed statins.", "health", (0.85, 0.98)),
    (lambda: f"Reimburse travel: {RNG.choice(USD)} for the {RNG.choice(NAMES)} onsite.", "money", (0.7, 0.9)),
]

SHARED_TEMPLATES = [
    (lambda: f"Team standup at 10am with {RNG.choice(NAMES)} to review the sprint board.", "scheduling", (0.05, 0.2)),
    (lambda: "Read the SvelteKit routing docs before Thursday's arch review.", "work", (0.05, 0.15)),
    (lambda: "Lunch-and-learn on WebGPU shaders, open to everyone in the office.", "work", (0.05, 0.2)),
    (lambda: "Blog post 'Getting started with MCP' is published on the company site.", "work", (0.05, 0.15)),
    (lambda: f"Book the {RNG.choice(['2pm','4pm','11am'])} slot for the design sync.", "scheduling", (0.05, 0.2)),
    (lambda: f"Conference CFP for {RNG.choice(['PyCon','JSConf','FOSSASIA'])} closes next month.", "work", (0.05, 0.2)),
    (lambda: "Public webinar: 'Intro to on-device AI' — share the signup link widely.", "work", (0.05, 0.2)),
]

IN_MARKERS = ("Rs", "₹", "+91", "lakh", "crore", "ICICI", "HDFC", "RBL", "Axis", "SBI", "Kotak", "GSFC")


def compact(text, tier, sens, extra_cat):
    hits = rule_hits(text)
    cats = [h for h in hits if h in CATEGORIES]  # keep rule tokens, drop kw:*
    if extra_cat in CATEGORIES and extra_cat not in cats:
        cats.append(extra_cat)
    if not cats:
        cats = [extra_cat if extra_cat in CATEGORIES else "misc"]
    return {
        "text": text,
        "tier": tier,
        "sensitivity": round(sens, 2),
        "categories": cats,
        "reason": "matches a privacy rule" if tier == "PRIVATE" else "routine, non-sensitive",
        "source": RNG.choice(["gmail", "notion", "calendar"]),
        "region": "IN" if any(m in text for m in IN_MARKERS) else "GLOBAL",
        "lang": "en",
        "difficulty": "easy",
        "hard_negative": False,
        "origin": "seed",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=320)
    ap.add_argument("--out", default="finetune/dataset/raw/seed.jsonl")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    rows, seen = [], set()
    n_priv = int(args.n * 0.55)
    n_shar = args.n - n_priv

    def emit(templates, tier, count):
        made, guard = 0, 0
        while made < count and guard < count * 40:
            guard += 1
            builder, cat, (lo, hi) = RNG.choice(templates)
            text = builder()
            if text in seen:
                continue
            if tier == "PRIVATE" and not rule_hits(text):
                continue
            seen.add(text)
            rows.append(compact(text, tier, RNG.uniform(lo, hi), cat))
            made += 1

    emit(PRIVATE_TEMPLATES, "PRIVATE", n_priv)
    emit(SHARED_TEMPLATES, "SHARED", n_shar)
    RNG.shuffle(rows)

    with out.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    priv = sum(1 for r in rows if r["tier"] == "PRIVATE")
    print(f"wrote {len(rows)} compact seed rows -> {out}  ({priv} PRIVATE / {len(rows)-priv} SHARED)")


if __name__ == "__main__":
    main()
