# Capturing AMD-hosted Gemma for the prize submission

**Track:** "Best AMD-Hosted Gemma Project" ($2k). Eligibility = SHARED-tier context
cards are distilled by **Gemma running on AMD Dev Cloud**, with the inference
call captured (log or screenshot) for judges.

Where it happens: [`gateway/distill.py`](../gateway/distill.py) →
`_call_cloud_gemma()` POSTs to `AMD_CLOUD_ENDPOINT` and logs two INFO lines per
call:

```
contxt:cloud_gemma endpoint=<amd-url> model=<gemma-model>
contxt:cloud_gemma_ok id=<response-id> usage=<token-usage>
```

## Capture steps

1. In `.env`, point at AMD Dev Cloud and set the model:
   ```
   AMD_CLOUD_ENDPOINT=https://<your-amd-inference-url>/v1/chat/completions
   FIREWORKS_API_KEY=<bearer-token-for-that-endpoint>
   GEMMA_CLOUD_MODEL=<gemma-model-id-on-amd>
   ```
   `AMD_CLOUD_ENDPOINT` overrides Fireworks. Leave `CONTXT_MOCK_GEMMA` unset — the
   real HTTP path only runs when an endpoint + key are present.

2. Run a real distillation and capture the log:
   ```bash
   PYTHONPATH=. python3 -m gateway.distill 2>&1 | tee docs/amd_gemma_capture.log
   ```
   The `endpoint=<amd-url> … model=…` and `…_ok id=… usage=…` lines are the proof.
   Screenshot the terminal too — judges like a visual.

3. (Optional) Same lines flow through the live MCP `draft_reply` tool, so a
   screenshot of Claude Desktop calling `draft_reply` against the AMD endpoint
   doubles as a demo + capture.

## Offline / demo safety

- No endpoint or key wired → `_call_cloud_gemma` auto-falls back to a deterministic
  **mock** (logged `endpoint=mock … mock=1`) so the pipeline never crashes on stage.
- Force mock in tests/CI with `CONTXT_MOCK_GEMMA=1`; force the real call with
  `CONTXT_MOCK_GEMMA=0`.
- Responses are cached under `gateway/.cache/` (gitignored) so a live demo isn't
  rate-limited by repeated identical calls. Disable with `CONTXT_CACHE=0`.

## Privacy guarantee (say this to judges)

PRIVATE-tier items **never** reach the cloud model. `distill_item` raises before any
HTTP call, `distill_batch` skips them, and `server/mcp_server.draft_reply` filters to
SHARED cards only. Proven by `tests/test_distill.py::test_private_item_is_refused_before_any_cloud_call`.
