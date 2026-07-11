#!/usr/bin/env python3
"""Emit train_gemma_gateway.ipynb (valid nbformat-4 JSON) from cell sources here.

Kept in-repo so the notebook is reproducible and reviewable as plain code.
Run: python finetune/_build_notebook.py
"""
import json
import pathlib

REPO = "https://github.com/Blackx16/contxt.git"
BRANCH = "finetune/gemma-gateway-270m"
HF_REPO = "Blackx16/contxt-gateway-270m-onnx"

md = lambda s: {"cell_type": "markdown", "metadata": {}, "source": s.splitlines(keepends=True)}
code = lambda s: {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                  "source": s.strip("\n").splitlines(keepends=True)}

cells = [
    md("""# Fine-tune Gemma 3 270M → Crown-Jewels Gateway classifier

Runtime → **T4 GPU**. Trains on the ready-to-train chat data, exports a `q4f16` ONNX
(~273 MB) that runs on-device via Transformers.js **WASM**, evals base-vs-tuned, and
pushes to Hugging Face. See `docs/FINETUNE_PLAN.md`.
"""),
    code("""%pip -q install -U "transformers>=4.56" "trl>=0.12" peft datasets accelerate \\
    onnx onnx_ir onnxruntime "optimum[onnxruntime]" huggingface_hub"""),
    code("""# Gemma is a GATED model. ONE-TIME: open https://huggingface.co/google/gemma-3-270m-it
# and click "Agree and access". Then create a token (Settings > Access Tokens, role
# 'Write') and paste it below. This same login is reused to push the model at the end.
from huggingface_hub import login
login()"""),
    code(f"""# Get the contract (prompt.py) + committed data.
!git clone -q -b {BRANCH} {REPO} /content/contxt || (cd /content/contxt && git pull -q)
import sys; sys.path.insert(0, "/content/contxt")
%cd /content/contxt
from finetune.prompt import INSTRUCTION, build_messages
print(INSTRUCTION[:120], "...")"""),
    code("""import json, pathlib, datasets
def load(p):
    p = pathlib.Path(p)
    if not p.exists():
        from google.colab import files          # data not committed yet? upload it.
        up = files.upload(); p.write_bytes(next(iter(up.values())))
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
train = load("finetune/dataset/train.jsonl"); test = load("finetune/dataset/test.jsonl")
print(len(train), "train /", len(test), "test")
train_ds = datasets.Dataset.from_list(train)
print(train[0]["messages"][0]["content"][:200])"""),
    code("""import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from trl import SFTTrainer, SFTConfig
BASE = "google/gemma-3-270m-it"
tok = AutoTokenizer.from_pretrained(BASE)
model = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16,
                                             attn_implementation="eager")
cfg = SFTConfig(
    output_dir="contxt-gw-270m", num_train_epochs=3, per_device_train_batch_size=16,
    gradient_accumulation_steps=1, learning_rate=5e-5, lr_scheduler_type="cosine",
    warmup_ratio=0.03, max_length=512, bf16=True, logging_steps=10,
    completion_only_loss=True,   # train on the JSON answer, not the repeated instruction
    save_strategy="epoch", report_to="none",
)
SFTTrainer(model=model, processing_class=tok, train_dataset=train_ds, args=cfg).train()
model.save_pretrained("contxt-gw-270m"); tok.save_pretrained("contxt-gw-270m")
# QLoRA fallback if VRAM is tight: load with load_in_4bit=True + LoraConfig(r=16, alpha=32,
# target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"]),
# then model = model.merge_and_unload() before save_pretrained."""),
    code("""# Sanity: does it emit clean JSON now?
import torch
m = build_messages('Your HDFC loan EMI of Rs 54,000 is due on the 5th.')
ids = tok.apply_chat_template(m, add_generation_prompt=True, return_tensors="pt").to(model.device)
print(tok.decode(model.generate(ids, max_new_tokens=96, do_sample=False)[0][ids.shape[-1]:],
                 skip_special_tokens=True))"""),
    code("""# Export to ONNX + quantize with Xenova's build_gemma.py (same script behind onnx-community).
!wget -q https://gist.githubusercontent.com/xenova/a219dbf3c7da7edd5dbb05f92410d7bd/raw/45f4c5a5227c1123efebe1e36d060672ee685a8e/build_gemma.py
!python build_gemma.py --model_name ./contxt-gw-270m --output ./onnx-out -p fp16 q4 q4f16
!ls -lah onnx-out/onnx"""),
    code("""# The ship gate: fine-tune vs base on the held-out set.
!python finetune/eval.py --model ./contxt-gw-270m --base google/gemma-3-270m-it \\
    --test finetune/dataset/test.jsonl --out finetune/dataset/eval.md --backend hf
print(open("finetune/dataset/eval.md").read())"""),
    code(f"""# Push the ONNX folder to HF (reuses the login from the top of the notebook).
from huggingface_hub import upload_folder, create_repo
create_repo("{HF_REPO}", exist_ok=True)
upload_folder(folder_path="onnx-out", repo_id="{HF_REPO}",
              commit_message="fine-tuned gateway classifier (q4f16)")
print("pushed → {HF_REPO}")"""),
    md(f"""## Deploy
In `extension/offscreen.js`:
```js
const MODEL_ID = '{HF_REPO}';
const clf = await pipeline('text-generation', MODEL_ID, {{ dtype: 'q4f16', device: 'wasm' }});
// call with build_messages(): clf([{{role:'user', content: prompt}}], ...) so the chat
// template is applied — matches training. NOT fp16/webgpu (onnxruntime#26732 garbage).
```
Then re-run `python server/verify_cha26.py` to confirm zero private leakage still holds.
"""),
]

nb = {"cells": cells, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
      "accelerator": "GPU", "colab": {"provenance": []}}, "nbformat": 4, "nbformat_minor": 5}

out = pathlib.Path(__file__).parent / "train_gemma_gateway.ipynb"
out.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
print("wrote", out)
