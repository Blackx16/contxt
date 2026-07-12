# Fine-tune on the AMD MI300X notebook — and capture the Track-3 AMD proof

**Why this doc exists:** Track 3 **disqualifies** any project that doesn't *demonstrate*
AMD compute usage. Running our fine-tune on `notebooks.amd.com/hackathon` (MI300X, ROCm)
**is** that proof — and it produces the actual on-device model. Two birds. It also upgrades
the pitch line to a true *"fine-tuned on AMD MI300X, runs on-device."*

No local GPU needed (your 2015 Air never trains). Everything below runs in the AMD notebook.

## 0. Get the pod
1. lablab event dashboard → **create/join a team** (required to get a GPU pod).
2. Open **https://notebooks.amd.com/hackathon** (8h per 24h).

## 1. Setup + first proof (one cell)
```bash
!rocm-smi                      # 📸 SCREENSHOT #1 — shows the AMD MI300X GPU
!git clone -b finetune/gemma-gateway-270m https://github.com/Blackx16/contxt.git
%cd contxt
# ROCm PyTorch is PRE-INSTALLED on the AMD image — do NOT reinstall torch.
!pip -q install "transformers>=4.56" "trl>=0.12" datasets accelerate "optimum[onnxruntime]" onnx onnx_ir
```
```python
import torch
print(torch.cuda.is_available(), torch.cuda.get_device_name(0))  # ROCm surfaces as .cuda; expect an AMD/MI300X name
```

## 2. Data
- If you've committed Kimi data, it's already at `finetune/dataset/`.
- For a fast **P0 DQ-proof run**, seed-only is enough — it's still a real AMD training run:
```bash
!python finetune/generate_seed.py && python finetune/validate.py --in finetune/dataset/raw
```

## 3. Train — capture proof #2
Pick ONE:

**A) Gemma path (pitch-aligned "local Gemma", needs `huggingface_hub` login for the gated model):**
Run the cells in `finetune/train_gemma_gateway.ipynb`. It works on ROCm unchanged — we do
**full fine-tune (no bitsandbytes/QLoRA**, which is flaky on ROCm), and `attn_implementation="eager"`
is already set. `bf16` is fine on MI300X.

**B) Encoder path (faster, no gated model, ~66 MB):**
```bash
!python finetune/router/train_router.py    # auto-detects the ROCm GPU via torch.cuda
```
While it trains, in a second cell:
```bash
!rocm-smi                      # 📸 SCREENSHOT #2 — GPU utilization DURING training
```
Also copy the training log (loss per epoch) and note wall-clock + device name.

## 4. Export + eval (as normal)
```bash
!python finetune/router/export_onnx.py && python finetune/router/eval_router.py   # encoder
# or the export/eval cells in the Gemma notebook
```

## 5. Turn the run into the submission proof  ← this is what closes the DQ risk
Create `docs/amd_compute_capture.md` **in the contxt repo** (main, cha-26 branch) with:
- both `rocm-smi` screenshots,
- the training log (loss curve / final metrics),
- one line: *"Gateway classifier fine-tuned on AMD Instinct MI300X via
  notebooks.amd.com/hackathon on 2026-07-12; <N> GPU-minutes; device: <name>."*
Then:
- add an **"AMD compute"** slide to the deck citing it,
- mention it in the README,
- commit + push.

That single doc + slide is what the automated pre-screen and human judges look for. **P0 done.**

## 6. (Optional) $2k AMD-hosted-Gemma bonus
Separate from the Track-3 requirement. Per [`docs/AMD_PRIZE.md`](../docs/AMD_PRIZE.md): serve
Gemma on the AMD **Dev Cloud** ($100 credits), point `AMD_CLOUD_ENDPOINT` at it, run
`PYTHONPATH=. python3 -m gateway.distill`, and capture the
`contxt:cloud_gemma endpoint=<amd-url> …` log lines.

## ROCm gotchas
- Use the **pre-installed** torch; reinstalling can pull a CUDA build that won't see the GPU.
- **Skip QLoRA/bitsandbytes** — do full FT (our 270M/66M models don't need it).
- If `bf16` errors, fall back to `fp16`; MI300X supports both.
