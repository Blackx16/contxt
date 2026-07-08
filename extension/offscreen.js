// Runs the local Gemma 3 270M (Q4) classifier in-browser via Transformers.js
// + WebGPU. Weights are cached (OPFS/Cache API) after first load.
import { pipeline, env } from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers';

env.useBrowserCache = true;

let classifier = null;
async function getClassifier() {
  if (classifier) return classifier;
  // TODO: swap to the published Q4 Gemma 3 270M model id.
  classifier = await pipeline('text-generation', 'onnx-community/gemma-3-270m', {
    dtype: 'q4', device: 'webgpu'
  });
  return classifier;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === 'classify:offscreen') {
    getClassifier()
      .then(async (clf) => {
        // TODO: build the gateway prompt; parse JSON {tier, sensitivity, ...}.
        const out = await clf(msg.text, { max_new_tokens: 64 });
        sendResponse({ raw: out });
      })
      .catch((e) => sendResponse({ error: String(e) }));
    return true;
  }
});
