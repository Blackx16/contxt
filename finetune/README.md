# `finetune/` — the fine-tuned gateway classifier track

Specializes **Gemma 3 270M** into the Crown-Jewels Gateway tier-classifier so it emits
reliable JSON at ≤ ~270 MB and beats today's zero-shot base model. Full rationale,
size math, and the WebGPU bug that motivates this: [`docs/FINETUNE_PLAN.md`](../docs/FINETUNE_PLAN.md).

Training runs on a **free Colab T4**; the result runs **fully on-device** (in-browser WASM).

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
