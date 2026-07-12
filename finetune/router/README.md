# `finetune/router/` — encoder-classifier track (the fast one)

An alternative to the generative Gemma track: fine-tune a **tiny BERT encoder** as a
binary PRIVATE/SHARED classifier — the same shape as the org's AMD query-router
tutorial ([lablab](https://lablab.ai/ai-tutorials/fine-tune-llm-query-router-amd) ·
[repo](https://github.com/Stephen-Kimoi/fine-tune-llm-query-router-amd)).

**Same dataset as the Gemma track** (`finetune/dataset/{train,test}.jsonl`), so the two
are a fair A/B.

## Why this exists
| | Gemma 270M (generative) | Encoder (this) |
|---|---|---|
| Train | Colab T4, gated model, HF token | **your M1 (MPS), ~5 min, no token** |
| Output | free-text JSON (must parse) | **calibrated probability** |
| `sensitivity` | model must emit it | **= P(PRIVATE), for free** |
| Failure modes | JSON parse, WebGPU #26732 | **none** |
| Size (int8) | 273 MB | **~66 MB** (distilbert) / **~22 MB** (MiniLM) |
| Browser | `text-generation` + prompt | `text-classification`, one call |

It does **not** affect the AMD-hosted-Gemma prize — that's the *cloud* distillation
path (`docs/AMD_PRIZE.md`), which stays Gemma-on-AMD. This only swaps the local router.

## Run it (on your M1)
```bash
pip install -r finetune/router/requirements.txt

# dataset must exist first (shared with the Gemma track):
python finetune/generate_seed.py && python finetune/validate.py --in finetune/dataset/raw

python finetune/router/train_router.py          # DistilBERT; MPS auto-detected. ~5 min.
python finetune/router/export_onnx.py            # → onnx-out/ (fp32 + int8), Transformers.js layout
python finetune/router/eval_router.py            # metrics; writes finetune/router/eval.md
#   smaller variant: python finetune/router/train_router.py --base sentence-transformers/all-MiniLM-L6-v2
```

## The A/B (post-demo)
Compare `finetune/router/eval.md` vs `finetune/dataset/eval.md` (Gemma track). **Ship the
higher tier-accuracy at PRIVATE recall ≥ 0.98**; break ties on size + latency. The
encoder almost always wins on size/latency/reliability; the Gemma track wins only if
you specifically want the "local Gemma" narrative.

## Deploy (if the encoder wins)
Upload `onnx-out/` to a HF repo (e.g. `Blackx16/contxt-gateway-router-onnx`). In
`extension/offscreen.js`, replace the generative Pass-2 with:
```js
const clf = await pipeline('text-classification', 'Blackx16/contxt-gateway-router-onnx',
                           { dtype: 'q8', device: 'wasm' });   // uses onnx/model_quantized.onnx
const [out] = await clf(text);                                 // {label:'PRIVATE'|'SHARED', score}
const tier = out.label, sensitivity = out.label === 'PRIVATE' ? out.score : 1 - out.score;
```
`categories` continue to come from the deterministic rules layer (Pass 1 already emits
them); `reason` can be templated. Then re-run `python server/verify_cha26.py`.

> Transformers.js quantized-file naming differs across versions — this exports
> `onnx/model_quantized.onnx`; use `{ dtype: 'q8' }` (v3) or `{ quantized: true }` (v2) to
> match your bundled `transformers.min.js`.
