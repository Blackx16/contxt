# AMD compute usage — proof (Track 3 requirement)

The Contxt on-device gateway classifier was **fine-tuned on an AMD Instinct MI300X GPU** via `notebooks.amd.com/hackathon`, satisfying Track 3's AMD compute requirement.

## Environment
- Platform: `notebooks.amd.com/hackathon` (AMD Radeon Cloud, ROCm image)
- ROCm/HIP Version: **7.2.53211-e1a6bc5663**
- PyTorch: **2.9.1+gitff65f5b** (ROCm build)
- GPU: **AMD Instinct MI300X, 47.98 GB VRAM**
- Date: 2026-07-13

## Training run
Fine-tuned a DistilBERT-based sequence classifier as an alternative to the deployed Gemma model. Training completed cleanly on the MI300X in ~5 minutes.

device=cuda base=distilbert-base-uncased train=1438 PRIVATE=899 SHARED=539 class_weights=[1.334, 0.800] epoch 1/4 loss=0.2552 epoch 2/4 loss=0.0801 epoch 3/4 loss=0.0263 epoch 4/4 loss=0.0191 saved → finetune/router/checkpoint



## Eval (held-out 253 rows)

| Model | Tier accuracy | PRIVATE recall | PRIVATE precision | Latency | Size |
|---|---|---|---|---|---|
| Encoder (AMD-trained) | **97.6%** | **99.4%** | 96.9% | 56 ms | 67 MB int8 |

Ship gate (PRIVATE recall ≥ 0.98): cleared at 0.994.

## Evidence

![rocm-smi — MI300X visible](./amd/rocm-smi.png)
![torch.cuda + ROCm version](./amd/torch-gpu.png)
![training loss curve](./amd/train-log.png)
![eval table](./amd/eval-table.png)

## Deployment note
The deployed browser model is the Gemma 3 270M fine-tune (`chandr1601/contxt-gateway-270m-onnx`, q4f16/WASM) which achieves identical accuracy (97.6% / 99.4% recall). The AMD-trained encoder is the alternative track and demonstrates that our fine-tuning pipeline runs end-to-end on AMD ROCm — an honest, reproducible AMD compute claim.