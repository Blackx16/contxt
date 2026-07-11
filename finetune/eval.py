#!/usr/bin/env python3
"""Evaluate a gateway classifier on the held-out test set — the SHIP GATE.

Computes the metrics that decide whether the fine-tune replaces the base model:
  - json_valid_rate   : fraction of outputs that parse as a JSON object
  - tier_accuracy     : exact PRIVATE/SHARED match
  - private_recall    : of gold-PRIVATE items, how many we caught (SAFETY METRIC)
  - private_precision : of predicted-PRIVATE, how many were right
  - sensitivity_mae   : mean abs error on the sensitivity float (valid rows only)
  - avg_latency_s

Pass --base to A/B two models in one run (e.g. the base gemma-3-270m-it vs the
fine-tune) and emit a side-by-side markdown table.

Backends:
  --backend hf    (default) load a HF/merged checkpoint with transformers
  --backend onnx  load an exported ONNX dir with optimum.onnxruntime

Usage (Colab, after export):
    python finetune/eval.py --model ./contxt-gw-270m --base google/gemma-3-270m-it \
        --test finetune/dataset/test.jsonl --out finetune/dataset/eval.md
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from finetune.prompt import build_messages, extract_item  # noqa: E402


def load_test(path: str, limit: int | None):
    rows = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        text = extract_item(obj["messages"][0]["content"])
        gold = json.loads(re.search(r"\{.*\}", obj["messages"][-1]["content"], re.DOTALL).group(0))
        rows.append((text, gold))
        if limit and len(rows) >= limit:
            break
    return rows


def make_runner(model_id: str, backend: str):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model_id)
    if backend == "onnx":
        from optimum.onnxruntime import ORTModelForCausalLM
        model = ORTModelForCausalLM.from_pretrained(model_id)
    else:
        import torch
        from transformers import AutoModelForCausalLM
        model = AutoModelForCausalLM.from_pretrained(
            model_id, torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32
        )
        if torch.cuda.is_available():
            model = model.to("cuda")

    def run(text: str) -> str:
        msgs = build_messages(text)
        inputs = tok.apply_chat_template(msgs, add_generation_prompt=True, return_tensors="pt")
        if hasattr(model, "device"):
            inputs = inputs.to(model.device)
        out = model.generate(inputs, max_new_tokens=96, do_sample=False)
        return tok.decode(out[0][inputs.shape[-1]:], skip_special_tokens=True)

    return run


def parse(raw: str):
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def score(runner, rows):
    n = len(rows)
    valid = tier_ok = 0
    gold_priv = pred_priv = tp = 0
    sae = sae_n = 0.0
    t0 = time.time()
    for text, gold in rows:
        out = runner(text)
        pred = parse(out)
        g_tier = str(gold["tier"]).upper()
        gold_priv += g_tier == "PRIVATE"
        if pred and str(pred.get("tier", "")).upper() in ("PRIVATE", "SHARED"):
            valid += 1
            p_tier = str(pred["tier"]).upper()
            pred_priv += p_tier == "PRIVATE"
            tp += (p_tier == "PRIVATE" and g_tier == "PRIVATE")
            tier_ok += p_tier == g_tier
            try:
                sae += abs(float(pred.get("sensitivity")) - float(gold["sensitivity"])); sae_n += 1
            except Exception:
                pass
    dt = time.time() - t0
    return {
        "n": n,
        "json_valid_rate": valid / n,
        "tier_accuracy": tier_ok / n,
        "private_recall": (tp / gold_priv) if gold_priv else float("nan"),
        "private_precision": (tp / pred_priv) if pred_priv else float("nan"),
        "sensitivity_mae": (sae / sae_n) if sae_n else float("nan"),
        "avg_latency_s": dt / n,
    }


def fmt(m):
    return (f"| {m['n']} | {m['json_valid_rate']:.1%} | {m['tier_accuracy']:.1%} | "
            f"{m['private_recall']:.1%} | {m['private_precision']:.1%} | "
            f"{m['sensitivity_mae']:.3f} | {m['avg_latency_s']:.2f}s |")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--base", default=None, help="optional second model for A/B")
    ap.add_argument("--test", default="finetune/dataset/test.jsonl")
    ap.add_argument("--backend", choices=["hf", "onnx"], default="hf")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--out", default="finetune/dataset/eval.md")
    args = ap.parse_args()

    rows = load_test(args.test, args.limit)
    header = ("| model | n | json valid | tier acc | PRIVATE recall | PRIVATE prec | sens MAE | latency |\n"
              "|---|---|---|---|---|---|---|---|")
    body = []
    print(f"scoring fine-tune: {args.model}")
    body.append(f"| **{args.model}** " + fmt(score(make_runner(args.model, args.backend), rows))[1:])
    if args.base:
        print(f"scoring base: {args.base}")
        body.append(f"| {args.base} " + fmt(score(make_runner(args.base, args.backend), rows))[1:])

    table = header + "\n" + "\n".join(body) + "\n"
    note = ("\n**Ship gate:** fine-tune must beat base on json-valid + tier-accuracy while "
            "holding **PRIVATE recall >= 0.98 and >= base**. If not, do not ship.\n")
    pathlib.Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(args.out).write_text("# Eval\n\n" + table + note, encoding="utf-8")
    print("\n" + table + note)


if __name__ == "__main__":
    main()
