#!/usr/bin/env python3
"""Evaluate the encoder classifier — metrics aligned with the generative eval.py
so you can A/B the two tracks on the SAME test set and pick a winner.

sensitivity is taken as P(PRIVATE); tier = argmax. json_valid_rate is 1.0 by
construction (a classifier can't emit malformed output — that's the point).

    python finetune/router/eval_router.py --ckpt finetune/router/checkpoint
    python finetune/router/eval_router.py --onnx finetune/router/onnx-out   # eval the shipped int8
"""
from __future__ import annotations

import argparse
import pathlib
import sys
import time

import torch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from finetune.router.data import load_pairs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="finetune/router/checkpoint")
    ap.add_argument("--onnx", default=None, help="eval an exported ONNX dir instead of the HF ckpt")
    ap.add_argument("--test", default="finetune/dataset/test.jsonl")
    ap.add_argument("--threshold", type=float, default=0.5)
    ap.add_argument("--out", default="finetune/router/eval.md")
    args = ap.parse_args()

    rows = load_pairs(args.test)
    from transformers import AutoTokenizer
    src = args.onnx or args.ckpt
    tok = AutoTokenizer.from_pretrained(src)
    if args.onnx:
        from optimum.onnxruntime import ORTModelForSequenceClassification
        model = ORTModelForSequenceClassification.from_pretrained(args.onnx, file_name="onnx/model_quantized.onnx")
    else:
        from transformers import AutoModelForSequenceClassification
        model = AutoModelForSequenceClassification.from_pretrained(args.ckpt)
    model.eval()

    n = len(rows)
    tier_ok = gold_priv = pred_priv = tp = 0
    sae = 0.0
    t0 = time.time()
    for r in rows:
        enc = tok(r["text"], truncation=True, max_length=128, return_tensors="pt")
        with torch.no_grad():
            logits = model(**enc).logits
        p_priv = torch.softmax(logits, -1)[0, 1].item()
        pred = 1 if p_priv >= args.threshold else 0
        gold_priv += r["label"] == 1
        pred_priv += pred == 1
        tp += pred == 1 and r["label"] == 1
        tier_ok += pred == r["label"]
        sae += abs(p_priv - r["sensitivity"])
    dt = time.time() - t0

    m = {
        "n": n,
        "json_valid_rate": 1.0,   # structural — a classifier cannot emit garbage
        "tier_accuracy": tier_ok / n,
        "private_recall": (tp / gold_priv) if gold_priv else float("nan"),
        "private_precision": (tp / pred_priv) if pred_priv else float("nan"),
        "sensitivity_mae": sae / n,
        "avg_latency_s": dt / n,
    }
    row = (f"| **encoder ({pathlib.Path(src).name})** | {m['n']} | 100% | "
           f"{m['tier_accuracy']:.1%} | {m['private_recall']:.1%} | {m['private_precision']:.1%} | "
           f"{m['sensitivity_mae']:.3f} | {m['avg_latency_s']*1000:.0f}ms |")
    table = ("| model | n | json valid | tier acc | PRIVATE recall | PRIVATE prec | sens MAE | latency |\n"
             "|---|---|---|---|---|---|---|---|\n" + row + "\n")
    note = ("\n**A/B:** compare this against the generative track's `finetune/dataset/eval.md`. "
            "Ship the one with higher tier-accuracy at **PRIVATE recall >= 0.98**, then break ties "
            "on size (encoder int8 ~66MB vs gemma q4f16 273MB) and latency.\n")
    pathlib.Path(args.out).write_text("# Encoder eval\n\n" + table + note, encoding="utf-8")
    print(table + note)


if __name__ == "__main__":
    main()
