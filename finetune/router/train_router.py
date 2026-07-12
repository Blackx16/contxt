#!/usr/bin/env python3
"""Encoder-classifier track — fine-tune a tiny BERT as a PRIVATE/SHARED classifier.

The org's AMD query-router tutorial does exactly this shape (DistilBertForSequence
Classification, class-weighted loss, MPS/CUDA/CPU). Our tier decision is the same
binary-classification problem, so this trains in minutes ON YOUR M1 (MPS) — no
Colab, no gated model, no HF token — and the output is a calibrated probability,
so sensitivity = P(PRIVATE) with no JSON to parse.

    pip install -r finetune/router/requirements.txt
    python finetune/router/train_router.py                 # distilbert, ~66MB int8 later
    python finetune/router/train_router.py --base sentence-transformers/all-MiniLM-L6-v2  # ~22MB

Trains on finetune/dataset/train.jsonl (build it first via generate_seed + validate).
"""
from __future__ import annotations

import argparse
import pathlib
import sys

import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from finetune.router.data import load_pairs, ID2LABEL, LABEL2ID  # noqa: E402


def get_device() -> str:
    if torch.backends.mps.is_available():
        return "mps"              # Apple Silicon (M1/M2/M3) — the "trained on my M1" path
    if torch.cuda.is_available():
        return "cuda"             # also the ROCm/MI300X path on AMD Dev Cloud
    return "cpu"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="distilbert-base-uncased")
    ap.add_argument("--train", default="finetune/dataset/train.jsonl")
    ap.add_argument("--out", default="finetune/router/checkpoint")
    ap.add_argument("--epochs", type=int, default=4)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--max-length", type=int, default=128)
    args = ap.parse_args()

    device = get_device()
    print(f"device={device}  base={args.base}")

    rows = load_pairs(args.train)
    if not rows:
        sys.exit(f"no rows in {args.train} — run generate_seed.py + validate.py first")
    texts = [r["text"] for r in rows]
    labels = torch.tensor([r["label"] for r in rows])

    tok = AutoTokenizer.from_pretrained(args.base)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.base, num_labels=2, id2label=ID2LABEL, label2id=LABEL2ID
    ).to(device)

    enc = tok(texts, truncation=True, padding="max_length", max_length=args.max_length,
              return_tensors="pt")

    # Class-weighted loss (their trick) — PRIVATE is the safety-critical, often-rarer class.
    n_priv = int(labels.sum())
    n_shar = len(labels) - n_priv
    w = torch.tensor([len(labels) / (2 * max(1, n_shar)),
                      len(labels) / (2 * max(1, n_priv))], device=device)
    loss_fn = torch.nn.CrossEntropyLoss(weight=w)
    print(f"train={len(labels)}  PRIVATE={n_priv}  SHARED={n_shar}  class_weights={w.tolist()}")

    ds = torch.utils.data.TensorDataset(enc["input_ids"], enc["attention_mask"], labels)
    dl = DataLoader(ds, batch_size=args.batch_size, shuffle=True)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr)

    model.train()
    for ep in range(args.epochs):
        tot = 0.0
        for ids, mask, y in dl:
            ids, mask, y = ids.to(device), mask.to(device), y.to(device)
            opt.zero_grad()
            logits = model(input_ids=ids, attention_mask=mask).logits
            loss = loss_fn(logits, y)
            loss.backward()
            opt.step()
            tot += loss.item()
        print(f"epoch {ep+1}/{args.epochs}  loss={tot/len(dl):.4f}")

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(out)
    tok.save_pretrained(out)
    print(f"saved → {out}  (next: python finetune/router/export_onnx.py)")


if __name__ == "__main__":
    main()
