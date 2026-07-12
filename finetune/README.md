# `finetune/` — the fine-tuned gateway classifier

Two tracks, **one shared dataset**, A/B after the demo — pick the winner on the eval gate:

- **Generative (this dir):** specialize **Gemma 3 270M** to emit the tier JSON. Trains on a
  free Colab T4, q4f16/WASM, 273 MB. Keeps the "local Gemma" narrative. Full rationale +
  size math + WebGPU bug: [`docs/FINETUNE_PLAN.md`](../docs/FINETUNE_PLAN.md).
- **Encoder ([`router/`](router/README.md)):** fine-tune a tiny BERT (DistilBERT-66M /
  MiniLM-22M) as a PRIVATE/SHARED classifier — the org's AMD query-router shape. Trains on
  your **M1 in ~5 min**, ~66 MB int8, `sensitivity = P(PRIVATE)`, no JSON/WebGPU failure
  modes. Doesn't touch the AMD-hosted-Gemma cloud prize.

Both read `finetune/dataset/{train,test}.jsonl`, so the comparison is fair. Sections below
cover the generative track; the encoder track lives in [`router/`](router/README.md).

## The contract (don't drift it)
`prompt.py` is the single source of truth for the instruction, the label shape, the
category vocab, and the sensitivity bands. The Kimi prompt, the seed generator, the
validator, the evaluator, and the deployed `extension/offscreen.js` must all agree with it.
Train-time formatting == infer-time formatting, or a 270M fine-tune silently degrades.

Model output shape (drop-in with offscreen.js): `{"tier":"PRIVATE"|"SHARED","sensitivity":0.0-1.0,"categories":[],"reason":""}`

## Files
| File | Role |
|---|---|
| `prompt.py` | Canonical instruction + label contract (shared by every stage) |
| `KIMI_PROMPT.md` | **Master prompt for Kimi** + field dictionary + 40-batch matrix |
| `generate_seed.py` | Free rules-oracle seed rows (guaranteed-correct PRIVATE/SHARED) |
| `validate.py` | Validate → rule-check → dedup → expand → stratified train/test split |
| `eval.py` | The ship gate: json-valid / tier-acc / PRIVATE-recall / sens-MAE, base vs tuned |
| `train_gemma_gateway.ipynb` | Colab: train → merge → export ONNX (q4f16) → eval → push to HF |

## Run order
```bash
# 1. seed (free, deterministic)
python finetune/generate_seed.py

# 2. data (Kimi) — run the master prompt per batch-matrix row, save each as
#    finetune/dataset/raw/kimi_<id>.jsonl   (see KIMI_PROMPT.md)

# 3. validate + build the split  → finetune/dataset/{train,test,audit}.jsonl + REPORT.md
python finetune/validate.py --in finetune/dataset/raw

# 4. commit the data so Colab can clone it
git add finetune/dataset/train.jsonl finetune/dataset/test.jsonl && git commit -m "data"

# 5. open train_gemma_gateway.ipynb in Colab (T4) → Run all
#    trains, exports q4f16 ONNX, runs eval.py (base vs tuned), pushes to HF

# 6. SHIP GATE (finetune/dataset/eval.md): fine-tune must beat base on json-valid +
#    tier-accuracy with PRIVATE recall >= 0.98 and >= base. If not, do not ship.

# 7. deploy: point extension/offscreen.js MODEL_ID at the HF repo, dtype 'q4f16',
#    device 'wasm' (NOT fp16/webgpu — see the plan).
```

## The two "run buttons" that need you
- **Kimi**: run the master prompt ~40× (batch matrix). Everything else is one command.
- **Colab**: press Run-all in the notebook (needs your Google account + a HF token).
