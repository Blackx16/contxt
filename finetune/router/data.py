"""Shared data adapter — turn the SAME dataset into (text, label) pairs.

Both tracks train on finetune/dataset/{train,test}.jsonl (the ready-to-train chat
format). The generative track uses the full messages; the encoder track just needs
the item text + its tier. This reads that one dataset so the two approaches are a
fair A/B on identical data.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from finetune.prompt import extract_item  # noqa: E402

LABEL2ID = {"SHARED": 0, "PRIVATE": 1}
ID2LABEL = {0: "SHARED", 1: "PRIVATE"}


def load_pairs(path: str) -> list[dict]:
    """Return [{'text','label','tier','sensitivity'}] from a chat-format jsonl."""
    rows = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        text = extract_item(obj["messages"][0]["content"])
        m = re.search(r"\{.*\}", obj["messages"][-1]["content"], re.DOTALL)
        if not text or not m:
            continue
        lab = json.loads(m.group(0))
        tier = str(lab.get("tier", "")).upper()
        if tier not in LABEL2ID:
            continue
        rows.append({
            "text": text,
            "label": LABEL2ID[tier],
            "tier": tier,
            "sensitivity": float(lab.get("sensitivity", 0.5)),
        })
    return rows


if __name__ == "__main__":  # quick check: python finetune/router/data.py
    tr = load_pairs("finetune/dataset/train.jsonl")
    priv = sum(r["label"] for r in tr)
    print(f"{len(tr)} pairs | PRIVATE {priv} / SHARED {len(tr)-priv}")
    for r in tr[:3]:
        print(" ", r["tier"], "::", r["text"][:70])
