#!/usr/bin/env python3
"""Export the fine-tuned encoder classifier to ONNX + int8, laid out for Transformers.js.

Produces (~66 MB for distilbert at int8, ~22 MB for MiniLM):
    finetune/router/onnx-out/
        config.json, tokenizer.json, vocab.txt, ...          # repo root
        onnx/model.onnx            (fp32)
        onnx/model_quantized.onnx  (dynamic int8)            # what the extension loads

Transformers.js text-classification expects the tokenizer/config at the repo root
and the graph under onnx/. Upload this folder to a HF repo and point the extension
at it.

    python finetune/router/export_onnx.py --ckpt finetune/router/checkpoint
"""
from __future__ import annotations

import argparse
import pathlib
import shutil

from optimum.onnxruntime import ORTModelForSequenceClassification, ORTQuantizer
from optimum.onnxruntime.configuration import AutoQuantizationConfig
from transformers import AutoTokenizer


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", default="finetune/router/checkpoint")
    ap.add_argument("--out", default="finetune/router/onnx-out")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Export to ONNX (writes model.onnx + config at `out`).
    model = ORTModelForSequenceClassification.from_pretrained(args.ckpt, export=True)
    model.save_pretrained(out)
    AutoTokenizer.from_pretrained(args.ckpt).save_pretrained(out)

    # 2. Dynamic int8 quantization (portable, CPU/WASM-friendly, no calibration set).
    quantizer = ORTQuantizer.from_pretrained(out)
    dqconfig = AutoQuantizationConfig.arm64(is_static=False, per_channel=False)
    quantizer.quantize(save_dir=out, quantization_config=dqconfig)
    # -> writes model_quantized.onnx alongside model.onnx

    # 3. Re-lay for Transformers.js: graph files under onnx/, tokenizer/config at root.
    onnx_dir = out / "onnx"
    onnx_dir.mkdir(exist_ok=True)
    for name in ("model.onnx", "model_quantized.onnx"):
        src = out / name
        if src.exists():
            shutil.move(str(src), str(onnx_dir / name))

    q = onnx_dir / "model_quantized.onnx"
    size_mb = q.stat().st_size / 1e6 if q.exists() else float("nan")
    print(f"exported → {out}")
    print(f"  onnx/model.onnx (fp32) + onnx/model_quantized.onnx (int8, ~{size_mb:.0f} MB)")
    print("  upload this folder to HF, e.g. Blackx16/contxt-gateway-router-onnx")


if __name__ == "__main__":
    main()
