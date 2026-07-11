# Fine-tuning the Crown-Jewels Gateway classifier

> Plan to specialize the on-device Gemma 3 270M tier-classifier so it emits reliable
> JSON at a **smaller** footprint than today. Training happens on a free Colab GPU;
> the result runs **fully on-device** (in-browser WASM / any M-series Mac). No Chrome
> AI APIs, no cloud inference for tiering.

**Status:** planning. This is the roadmap item already named in `docs/ARCHITECTURE.md`
("fine-tuned 270M classifier"). See [§10 Timeline](#10-timeline--is-this-a-today-thing) —
there is a **zero-training quick win** that should ship first.

---

## 0. TL;DR decision

**Yes — fine-tune, and it clears both of your bars** (≤ ~270 MB *and* better than today):

- **Keep Gemma 3 270M.** It is purpose-built for exactly this (task-specific
  classification/extraction), it already beats Qwen2.5-0.5B on IFEval at a third the
  size, it ships QAT checkpoints so it quantizes cleanly, and — decisive for us — it
  keeps the **$2k "Best AMD-Hosted Gemma" bonus** eligibility and drops straight into our
  existing Transformers.js pipeline. Switching to LFM2-350M/Qwen3-0.6B would trade all of
  that for a marginal param win. See [§2](#2-model-selection).
- **Ship `q4f16` weights (273 MB) on the WASM/CPU backend, not fp16-on-WebGPU.**
- **For truly < 270 MB** (≈135–180 MB), do a custom int4/int8 export that also quantizes
  the embedding table. See [§5](#5-export--quantize).
- **Fine-tuning's real payoff** is not size — it is a ~99% valid-JSON rate and tier
  decisions that match *our* policy, which in turn makes aggressive quantization safe
  (a narrow fine-tuned model is far more quantization-robust than a prompted base model).

### Two corrections this plan is built on

1. **The "q4 ≈ 270 MB" premise was wrong.** On the live repo `q4` is **323 MB** and the
   int8-style `model_quantized` is **545 MB** — both *bigger* than the ≤270 target. The
   only prebuilt variant at the target is **`q4f16` = 273 MB**. Google's marketed
   "125 MB / 270 MB" INT4 figure is a *different* build (LiteRT/GGUF, embeddings included),
   not the Transformers.js ONNX path we use.
2. **The "emits junk" symptom is a runtime bug, not a quantization/quality problem.**
   [onnxruntime #26732](https://github.com/microsoft/onnxruntime/issues/26732): Gemma 3's
   activations overflow to infinity in **float16 on WebGPU**, so `fp16`+`webgpu` (our
   *current* `offscreen.js` config) returns repeated `<unused56>` garbage. The **same fp16
   weights work correctly on WASM/CPU.** So switching the *backend* fixes the junk — before
   we fine-tune anything.

---

## 1. What the model actually does (the task spec)

The classifier is **Pass 2** of the gateway (`extension/offscreen.js`). Pass 1 is the
deterministic rules (`gateway/rules.py` / `extension/rules.js`) which force `PRIVATE` on any
hit and can never be overruled. The model only adds *nuance* on items the rules let through.

**Input** — one personal-data item (email line, calendar event, or note), capped at 400 chars.

**Output** — strict JSON, nothing else:

```json
{"tier":"PRIVATE"|"SHARED","sensitivity":0.0-1.0,"categories":[],"reason":""}
```

**Why this is the ideal fine-tuning target:** narrow, fixed output schema, small input, a
label policy we already encode deterministically, and a hard safety asymmetry (a missed
PRIVATE = a leaked crown jewel). Google's own guidance: after fine-tuning, a 270M model hits
**85–92% on domain classification** and reliable structured extraction — and *overfitting is
a feature* here, since we want it to forget general chit-chat and only do this one job.

### Label policy (the ground truth for data generation)

From `gateway/policy.py` + `gateway/rules.py`:

- **Forced PRIVATE (rules, sensitivity ≈ 1.0):** money (`₹`, `Rs`, `$`, lakh/crore, "millions"),
  finance words (revenue, salary, invoice, valuation…), card numbers, `a/c`+digits, Indian
  phone numbers, health (diagnosis, prescription, report), and the keyword toggles
  (`salary, loan, emi, family, school, client`, plus category unions: financials / family /
  clients / health).
- **Model's job (nuance on the rest):** things the regexes miss — *implied* sensitivity
  ("my daughter's parent-teacher meeting", "the Acme renewal is at risk"), and correctly
  leaving genuinely public/work-safe items **SHARED** with low sensitivity
  ("Team standup 10am", "Read the SvelteKit docs").

---

## 2. Model selection

Requirement: fine-tunable, runs in-browser via ONNX/Transformers.js, quantizes to ~270 MB,
strong at short structured classification.

| Model | Params | ≤270 MB feasible? | Browser/ONNX maturity | Gemma bonus? | Verdict |
|---|---|---|---|---|---|
| **Gemma 3 270M-it** | 270M | ✅ q4f16=273; int4-emb≈135–180 | ✅ shipped, we already use it | ✅ **yes** | **Chosen** |
| LFM2-350M | 350M | ⚠️ ~180–260 @ 4-bit | ⚠️ new hybrid arch, weak ort-web support | ❌ | Backup only |
| Qwen3-0.6B | 600M | ❌ int8≈600, q4≈300+ | ✅ good | ❌ | Too big |
| SmolLM2-360M | 360M | ✅ small vocab → q4≈180 | ✅ good | ❌ | Backup if we drop Gemma |

**Decision: stay on `google/gemma-3-270m-it`.** The tunability benchmarks (LFM2/Qwen3 score
higher on "fine-tuning ROI") are real but irrelevant here: they cost us the Gemma prize and
add browser-runtime risk, to specialize a model that's already ~90%-capable on this task
class. Gemma 3 270M is the right tool *and* the right story.

---

## 3. Size math — why the embedding table is the whole game

Gemma 3 270M = **~168M embedding params** (256k vocab) **+ ~100M transformer params.** The
embedding matrix is *bigger than the model*. That's why:

- Quantizing only the transformer matmuls (what `q4`/`q4f16` do) barely helps — the fp16
  embedding table alone is ~336 MB. That is exactly why `q4f16` bottoms out at **273 MB**.
- To get **truly < 270 MB you must quantize the embeddings too:**

| Strategy | Embeddings | Transformer | Approx size | Notes |
|---|---|---|---|---|
| `q4f16` (prebuilt) | fp16 | 4-bit | **273 MB** | At target; ships today; needs WASM backend |
| int8 everything | int8 | int8 | **~270 MB** | Safe quality; custom export |
| int4 everything | 4-bit | 4-bit | **~135–180 MB** | Matches Google's 125 MB claim; needs care/QAT |

**Both int8-everything and int4-everything require a custom export step** (§5). q4f16 is the
free option that already sits at "about 270 MB."

---

## 4. Training data — the make-or-break

We have almost no gold data (4 rows in `schema/fixtures/tier_decisions.json`). We generate a
**teacher-distilled synthetic set**, which doubles as a clean methodology story.

**Recipe (~2,000 examples, balanced):**

1. **Rules oracle (free, ~40%).** Sample realistic items, run `gateway/rules.py`; every hit is a
   guaranteed-correct PRIVATE label with exact `categories`/`sensitivity`. This anchors the
   safety-critical cases for free.
2. **Teacher model (~60%).** Use the **cloud Gemma we already call** (`gateway/distill.py`,
   Fireworks / AMD endpoint) as the labeling teacher: prompt it to *both invent* diverse
   items and label them in our schema. Student (270M) learns to imitate. This is textbook
   distillation and ties into the AMD-hosted-Gemma narrative.
3. **Coverage checklist:**
   - 50/50 PRIVATE vs SHARED.
   - Heavy **Indian context**: `Rs`/`₹`, ICICI/RBL/Fibe, EMI, lakh/crore, GST — matches our demo.
   - All sources: gmail / calendar / notion phrasings.
   - **Hard negatives both ways:** SHARED items containing scary words that are actually fine
     ("the *salary* negotiation *webinar* is public"), and PRIVATE items with *no* trigger word
     that the rules would miss (implied family/health/deal sensitivity) — the latter is the
     entire reason the model exists.
4. **Format:** Gemma chat template. `system`+`user` = the exact `buildPrompt()` string from
   `offscreen.js` (train on the deployment prompt verbatim); `assistant` = the JSON. **Train on
   the completion only** (mask the prompt).
5. **Hold out 15%** as a frozen test set (§6). Spot-check 100 rows by hand — synthetic labels
   have errors; the safety-critical PRIVATE recall must be measured on *clean* data.

Deliverable: `data/finetune/{train,test}.jsonl` + a `data/finetune/generate.py` (rules oracle +
teacher calls). Keep the generator in-repo so the dataset is reproducible.

---

## 5. Fine-tune → export → quantize (the Colab notebook)

Free **Colab T4 (16 GB)** is plenty; 270M does **full fine-tuning** comfortably (no LoRA merge
step needed), and full-FT gives better small-model quality. QLoRA is the fallback if VRAM is
tight. End-to-end runs in **well under an hour**.

### 5a. Train (HF TRL `SFTTrainer`)

```python
# Colab: T4. pip install -U transformers trl peft datasets accelerate bitsandbytes
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTTrainer, SFTConfig
BASE = "google/gemma-3-270m-it"
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype="bfloat16", attn_implementation="eager")
# dataset: {"messages":[{system},{user=buildPrompt(item)},{assistant=json}]}
cfg = SFTConfig(
    output_dir="contxt-gw-270m", num_train_epochs=3, per_device_train_batch_size=16,
    gradient_accumulation_steps=1, learning_rate=5e-5, lr_scheduler_type="cosine",
    warmup_ratio=0.03, max_seq_length=512, bf16=True,
    completion_only_loss=True,   # train on the JSON, not the prompt
    logging_steps=10, save_strategy="epoch",
)
SFTTrainer(model=model, processing_class=tok, train_dataset=train, args=cfg).train()
model.save_pretrained("contxt-gw-270m"); tok.save_pretrained("contxt-gw-270m")
```

*(QLoRA fallback: load `load_in_4bit=True`, `LoraConfig(r=16, alpha=32,
target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])`, then
`merge_and_unload()` before export.)*

### 5b. Export to ONNX + quantize — reuse Google's exact tool

Google's own [Convert_Gemma_3_270M_to_ONNX](https://colab.research.google.com/github/google-gemini/gemma-cookbook/blob/main/Demos/Emoji-Gemma-on-Web/resources/Convert_Gemma_3_270M_to_ONNX.ipynb)
notebook uses **Xenova's `build_gemma.py`** — the same script behind the `onnx-community` repo.
Point it at our merged fine-tune:

```bash
pip install transformers==4.56.1 onnx==1.19.0 onnx_ir==0.1.7 onnxruntime==1.22.1
wget https://gist.githubusercontent.com/xenova/a219dbf3c7da7edd5dbb05f92410d7bd/raw/build_gemma.py
python build_gemma.py --model_name ./contxt-gw-270m --output ./onnx -p fp16 q4 q4f16
```

- Produces `model_q4f16.onnx` (~273 MB) — the **primary artifact**, drop-in for our pipeline.
- **Stretch (< 270 MB):** after this, run `onnxruntime.quantization.matmul_4bits_quantizer`
  / dynamic int8 over the **embedding + LM head** nodes that `build_gemma.py` leaves in
  fp16. That is the step that takes 273 MB → ~135–180 MB. Validate quality hasn't dropped
  (§6) — Gemma 3's QAT makes this usually safe.

### 5c. Host

Upload the ONNX folder to our own HF repo (e.g. `Blackx16/contxt-gateway-270m-onnx`). Don't
bundle 270 MB in the extension zip — keep the current Cache-API-on-first-load behaviour.

---

## 6. Evaluation — the gate that decides whether we ship

Run the frozen test set through three configs and compare. **We ship only if the fine-tune
beats the working baseline** (your stated condition).

| Metric | Baseline: rules-only | Baseline: base q4f16/WASM | Target: fine-tuned |
|---|---|---|---|
| Valid-JSON rate | n/a | measure (expect mediocre) | **≥ 99%** |
| Tier accuracy | ~rules coverage | measure | **≥ 90%** |
| **PRIVATE recall** (safety) | high | measure | **≥ 0.98 and ≥ baseline** |
| Sensitivity MAE | n/a | measure | lower is better |
| Size | 0 | 273 MB | **≤ 273 MB (≤180 stretch)** |
| Latency (80 tok, WASM) | ~0 | measure | usable (~1–3 s ok) |

**PRIVATE recall is the veto metric.** The deterministic rules are the safety floor, but the
model must not *reduce* recall vs the working base. If it can't beat the base q4f16/WASM model
on JSON-validity + tier accuracy while holding PRIVATE recall, **do not ship it** — that's the
"only if better than now" bar, made concrete.

Note on honesty: the *current live* config (fp16/WebGPU) emits garbage, so its true quality is
≈ rules-only. Compare against the **fixed** base (q4f16/WASM) so the "we improved it" claim is
real, not an artifact of comparing against a broken runtime.

---

## 7. Deployment changes (`extension/offscreen.js`)

Once the artifact passes §6:

```js
const MODEL_ID = 'Blackx16/contxt-gateway-270m-onnx';   // our fine-tune
// ...
const clf = await pipeline('text-generation', MODEL_ID, {
  dtype: 'q4f16',      // 273 MB (or 'int8' custom for <270)
  device: 'wasm',      // NOT webgpu — dodges onnxruntime#26732 fp16 overflow
});
```

- Single-thread WASM needs **no** SharedArrayBuffer / cross-origin isolation — this also
  deletes the whole `crossOriginIsolated=false` failure mode the current code fights.
- Because output is now reliable JSON, the defensive `extractJSON` regex + silent
  rules-fallback become a true safety net rather than the common path.
- Keep `fp32`/`webgpu` as an optional fast path *only if* onnxruntime PR #29599 (the overflow
  fix) lands in a bundled ort-web version.

---

## 8. Positioning for judges (true and stronger)

Say it exactly like this — it's accurate and it's a better story than "we ran a base model":

> "We **fine-tuned Gemma 3 270M** into a specialized on-device privacy classifier — trained on
> a free Colab T4, distilled from our AMD/Fireworks-hosted Gemma teacher — and it runs **fully
> locally in the browser** (WASM), so tiering never touches the cloud. The specialized model is
> **smaller (273 MB → <180 MB) and more reliable** than the base."

Do **not** claim it was *trained* on an M1 — it wasn't, and you don't need to. The credible,
checkable claims are: *trained on Colab*, *runs on-device* (including M-series Macs and
in-browser). That combination is what impresses; a false training-hardware claim only adds risk.

---

## 9. Risks

- **Export path for a fine-tuned Gemma 3 is the riskiest step** (Gemma 3 is newish in ONNX
  land). Mitigation: use Xenova's `build_gemma.py` exactly as Google's notebook does — the
  proven path — before attempting the custom int4-embedding step.
- **Custom embedding quantization may dent quality.** Mitigation: it's a *stretch*; q4f16 at
  273 MB already meets "about 270 MB." Only chase <180 MB if §6 stays green.
- **Synthetic-label noise.** Mitigation: rules-oracle for the safety-critical rows +
  hand-audit of 100 test rows.
- **WASM latency.** For 80-token classification it's ~1–3 s — fine for a gateway that runs on
  ingest/paste, not a chat loop.

---

## 10. Timeline — is this a "today" thing?

**No — and that's the right call.** Deadline is **2026-07-11 21:30 IST** (~hours away) and this
is explicitly a roadmap item. Split it:

### Ship TODAY (zero training, ~15 min) — do this regardless
Flip `offscreen.js` from `fp16`/`webgpu` (broken, 570 MB) to **`q4f16`/`wasm`** (working,
273 MB). This alone: (a) fixes the `<unused56>` garbage, (b) meets the ≤~270 MB size target,
(c) removes the SharedArrayBuffer fragility. **Highest value-per-minute thing on the board.**
*(One-line change — say the word and I'll make it + re-run `verify_cha26.py`.)*

### The fine-tune project (post-deadline / stretch), critical path
1. `data/finetune/generate.py` → 2,000 rows, hand-audit 100. **(½ day — the real work)**
2. Colab: train + `build_gemma.py -p q4f16`. **(~1 hr)**
3. Eval vs baselines (§6). **Gate.** **(2 hr)**
4. If green: host on HF, flip `MODEL_ID`, re-verify. **(½ hr)**
5. Stretch: custom int4-embedding export → <180 MB, re-gate. **(½ day)**

**Definition of done:** a hosted ONNX model ≤ 273 MB that beats base-q4f16/WASM on JSON-validity
and tier accuracy at ≥0.98 PRIVATE recall, wired into `offscreen.js`, proven by an updated
`verify_cha26.py` and an A/B eval table committed to `data/finetune/eval.md`.

**Smallest first step:** write `generate.py`, produce **50 rows**, eyeball them. If the labels
look right, the other 1,950 are just volume. If they don't, you've spent 30 minutes, not a day.
