# `finetune/dataset/`

Training data for the gateway classifier. Lives here (not under `data/`, which is
gitignored and reserved for live user data) so `train.jsonl`/`test.jsonl` can be
committed for the Colab notebook to clone.

```
raw/            # inputs (gitignored): seed.jsonl + your kimi_<id>.jsonl batches
train.jsonl     # generated + committed: ready-to-train Gemma chat format
test.jsonl      # generated + committed: held-out split for the ship gate
audit.jsonl     # generated (gitignored): clean rows WITH _meta, for eyeballing
REPORT.md       # generated (gitignored): balance + problems report
eval.md         # generated (gitignored): base-vs-tuned metrics
```

Rebuild: `python finetune/generate_seed.py && python finetune/validate.py --in finetune/dataset/raw`.
Then commit `train.jsonl` + `test.jsonl` so Colab can pull them.
