#!/usr/bin/env python3
"""Validate + dedup + rule-check compact rows, then expand into train/test JSONL.

Input: a folder of COMPACT JSONL (finetune/generate_seed.py output + your Kimi
batches dropped in as kimi_*.jsonl). Each line:
    {"text","tier","sensitivity","categories","reason",
     "source","region","lang","difficulty","hard_negative"}

It:
  1. validates every field against the closed contract in finetune/prompt.py,
  2. re-derives the deterministic rule verdict and flags any row where a
     rule-triggerable item is NOT PRIVATE (the one unforgivable label error —
     that would teach the model to leak a crown jewel),
  3. dedups by normalized item text,
  4. prints + writes a balance report, and
  5. EXPANDS clean rows into the ready-to-train Gemma chat format and writes a
     stratified train/test split (this is the file the notebook trains on).

Usage:
    python finetune/validate.py --in finetune/dataset/raw --out finetune/dataset \
        --test-frac 0.15 [--fix-rule-violations]
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import pathlib
import random
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from gateway.rules import rule_hits  # noqa: E402
from finetune.prompt import CATEGORIES, VALID_TIERS, build_messages  # noqa: E402

RNG = random.Random(1601)
_WS = re.compile(r"\s+")


def norm(t: str) -> str:
    return _WS.sub(" ", t.strip().lower())


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", default="finetune/dataset/raw")
    ap.add_argument("--out", default="finetune/dataset")
    ap.add_argument("--test-frac", type=float, default=0.15)
    ap.add_argument("--fix-rule-violations", action="store_true",
                    help="force PRIVATE on rule-triggerable rows instead of dropping them")
    args = ap.parse_args()

    files = sorted(glob.glob(str(pathlib.Path(args.indir) / "*.jsonl")))
    if not files:
        sys.exit(f"no *.jsonl in {args.indir} — run generate_seed.py and drop Kimi batches there first")

    clean, seen = [], set()
    stats = collections.Counter()
    cat_counter = collections.Counter()
    by = {k: collections.Counter() for k in ("tier", "source", "lang", "region", "difficulty")}
    problems = collections.Counter()

    for fp in files:
        for ln, line in enumerate(pathlib.Path(fp).read_text(encoding="utf-8").splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            stats["seen"] += 1
            try:
                r = json.loads(line)
            except Exception:
                problems[f"bad_json ({pathlib.Path(fp).name}:{ln})"] += 1
                continue

            text = str(r.get("text", "")).strip()
            if not text or len(text) > 500:
                problems["missing_or_oversized_text"] += 1
                continue

            tier = str(r.get("tier", "")).upper()
            if tier not in VALID_TIERS:
                problems["bad_tier"] += 1
                continue

            try:
                sens = float(r.get("sensitivity"))
                assert 0.0 <= sens <= 1.0
            except Exception:
                problems["bad_sensitivity"] += 1
                continue

            cats = r.get("categories") or []
            if not isinstance(cats, list):
                problems["bad_categories_type"] += 1
                continue
            cats = [str(c) for c in cats if not str(c).startswith("kw:")]
            unknown = [c for c in cats if c not in CATEGORIES]
            if unknown:
                cats = [c for c in cats if c in CATEGORIES] or ["misc"]
                problems["unknown_categories_coerced"] += 1

            # THE safety check: rule-triggerable items MUST be PRIVATE.
            hits = rule_hits(text)
            if hits and tier != "PRIVATE":
                if args.fix_rule_violations:
                    tier, sens = "PRIVATE", max(sens, 0.9)
                    problems["rule_violation_fixed"] += 1
                else:
                    problems["rule_violation_dropped"] += 1
                    continue

            # Soft sanity: PRIVATE should not sit very low, SHARED not very high.
            if tier == "PRIVATE" and sens < 0.4:
                sens = 0.5; problems["private_sens_bumped"] += 1
            if tier == "SHARED" and sens > 0.5:
                problems["shared_high_sens_dropped"] += 1
                continue

            key = norm(text)
            if key in seen:
                stats["dup"] += 1
                continue
            seen.add(key)

            label = {"tier": tier, "sensitivity": round(sens, 2), "categories": cats,
                     "reason": str(r.get("reason", ""))[:120]}
            clean.append({
                "messages": build_messages(text, label),
                "_meta": {k: r.get(k) for k in ("source", "region", "lang", "difficulty",
                                                "hard_negative", "origin")},
                "_tier": tier,
            })
            by["tier"][tier] += 1
            by["source"][r.get("source", "?")] += 1
            by["lang"][r.get("lang", "?")] += 1
            by["region"][r.get("region", "?")] += 1
            by["difficulty"][r.get("difficulty", "?")] += 1
            for c in cats:
                cat_counter[c] += 1

    if not clean:
        sys.exit("no clean rows survived — check the problems report above")

    # Stratified split by tier.
    RNG.shuffle(clean)
    priv = [r for r in clean if r["_tier"] == "PRIVATE"]
    shar = [r for r in clean if r["_tier"] == "SHARED"]

    def split(rows):
        k = int(len(rows) * args.test_frac)
        return rows[k:], rows[:k]

    ptr, pte = split(priv)
    str_, ste = split(shar)
    train, test = ptr + str_, pte + ste
    RNG.shuffle(train); RNG.shuffle(test)

    outdir = pathlib.Path(args.out)
    outdir.mkdir(parents=True, exist_ok=True)
    for name, rows in (("train", train), ("test", test)):
        with (outdir / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({"messages": r["messages"]}, ensure_ascii=False) + "\n")
    # Full audit copy (messages + meta) for eyeballing.
    with (outdir / "audit.jsonl").open("w", encoding="utf-8") as f:
        for r in clean:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    lines = [
        "# Dataset report\n",
        f"- seen: {stats['seen']}  |  clean: {len(clean)}  |  dups removed: {stats['dup']}",
        f"- split: train={len(train)}  test={len(test)}  (test-frac {args.test_frac})",
        f"- tier balance: {dict(by['tier'])}",
        f"- by source: {dict(by['source'])}",
        f"- by lang: {dict(by['lang'])}  |  by region: {dict(by['region'])}",
        f"- by difficulty: {dict(by['difficulty'])}",
        f"- category counts: {dict(cat_counter.most_common())}",
        f"\n## Problems ({sum(problems.values())} total)",
    ]
    for k, v in problems.most_common():
        lines.append(f"- {k}: {v}")
    report = "\n".join(lines) + "\n"
    (outdir / "REPORT.md").write_text(report, encoding="utf-8")
    print(report)

    priv_frac = by["tier"]["PRIVATE"] / max(1, len(clean))
    print(f">> PRIVATE fraction {priv_frac:.0%} (target 45-52%). "
          f"Wrote {outdir/'train.jsonl'}, {outdir/'test.jsonl'}, {outdir/'audit.jsonl'}.")
    if problems.get("rule_violation_dropped"):
        print(f"!! {problems['rule_violation_dropped']} rows dropped for labeling a rule-hit item "
              f"SHARED — that's the dangerous error; inspect those Kimi batches.")


if __name__ == "__main__":
    main()
