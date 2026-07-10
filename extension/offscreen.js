/**
 * Crown-Jewels Gateway — on-device Gemma 3 270M Q4 classifier.
 *
 * Runs in the MV3 offscreen document (never the service worker / content
 * script) so it can use WebGPU and keep model weights off the main thread.
 *
 * Pipeline
 * --------
 * 1. Pass 1: deterministic rules (rules.js) — forced PRIVATE if any hit.
 * 2. Pass 2: Gemma 270M via Transformers.js + WebGPU — nuanced tier/reason.
 * 3. Override: user privacy-toggle categories force PRIVATE unconditionally.
 *
 * Listener readiness
 * ------------------
 * Transformers.js (~888 KB + WASM) is imported LAZILY inside loadClassifier(),
 * NOT at the top of the module. That way the onMessage listener below is
 * registered the instant the offscreen document is created — no window where
 * the doc exists but can't yet receive messages ("Receiving end does not
 * exist"). The deterministic fallback is also available immediately.
 *
 * Weight caching
 * --------------
 * Transformers.js caches model weights in the browser's Cache API after the
 * first download (env.useBrowserCache = true). Subsequent loads are instant.
 *
 * Fallback
 * --------
 * When WebGPU is unavailable (or the model fails to load) the deterministic
 * rules result is returned with a note — no crash, sane decisions.
 */

import { classifyFallback, ruleHits, DEFAULT_PRIVATE_KEYWORDS } from './rules.js';

// ── Lazy Transformers.js loader ───────────────────────────────────────────────

// Gemma 3 270M Q4 ONNX model on Hugging Face.
// Weights are ~270 MB on first load; subsequent loads are from Cache API.
const MODEL_ID = 'onnx-community/gemma-3-270m-it-ONNX';

let _tf = null;
async function getTransformers() {
  if (_tf) return _tf;
  // Heavy import — deferred until the first time we actually need the model.
  _tf = await import('./transformers.min.js');
  const { env } = _tf;
  env.useBrowserCache = true; // cache weights after first download
  env.useFS = false; // browser context, no Node fs

  // MV3 `script-src 'self'` blocks importing the ONNX runtime from a CDN.
  // Serve the self-hosted copies in ./ort/ instead — chrome-extension:// is
  // the 'self' origin, so the .jsep.mjs import is allowed.
  env.backends.onnx.wasm.wasmPaths = chrome.runtime.getURL('ort/');
  // Offscreen docs are not cross-origin isolated, so SharedArrayBuffer (and
  // thus multi-threading) is unavailable — pin to a single thread.
  env.backends.onnx.wasm.numThreads = 1;

  return _tf;
}

// ── Classifier state ──────────────────────────────────────────────────────────

let _classifier = null;
let _webgpuReady = false;

async function detectWebGPU() {
  try {
    if (!navigator.gpu) return false;
    const adapter = await navigator.gpu.requestAdapter();
    return !!adapter;
  } catch {
    return false;
  }
}

async function loadClassifier() {
  if (_classifier) return _classifier;

  _webgpuReady = await detectWebGPU();
  if (!_webgpuReady) {
    console.info('[contxt] WebGPU unavailable — using deterministic fallback');
    return null;
  }

  const { pipeline } = await getTransformers();
  // Diagnostic: the only WebGPU wasm build transformers ships is threaded, which
  // needs SharedArrayBuffer → needs cross-origin isolation. If this logs
  // `crossOriginIsolated=false SharedArrayBuffer=undefined`, THAT is why the
  // model aborts in an offscreen doc.
  console.info(
    '[contxt] env check — crossOriginIsolated=%s SharedArrayBuffer=%s webgpu=%s',
    self.crossOriginIsolated,
    typeof SharedArrayBuffer,
    !!navigator.gpu,
  );
  console.info('[contxt] Loading Gemma 3 270M (Q4) via WebGPU…');
  _classifier = await pipeline('text-generation', MODEL_ID, {
    dtype: 'q4',
    device: 'webgpu',
  });
  console.info('[contxt] Gemma 270M loaded ✓');
  return _classifier;
}

// ── Prompt & JSON extraction ──────────────────────────────────────────────────

function buildPrompt(text) {
  // Capped at 400 chars to stay within the 270M context budget.
  const excerpt = text.slice(0, 400);
  return (
    'You are a privacy classifier for personal data. ' +
    'Classify this item. ' +
    'Output ONLY valid JSON — no preamble, no markdown.\n\n' +
    `Item: "${excerpt}"\n\n` +
    'JSON: {"tier":"PRIVATE"|"SHARED","sensitivity":0.0-1.0,"categories":[],"reason":""}'
  );
}

function extractJSON(raw) {
  // The model echoes the prompt; find the first { … } in the output.
  const match = raw.match(/\{[\s\S]*?\}/);
  if (!match) return null;
  try {
    return JSON.parse(match[0]);
  } catch {
    return null;
  }
}

// ── Core classify ─────────────────────────────────────────────────────────────

async function classifyText(text, privateKeywords = DEFAULT_PRIVATE_KEYWORDS) {
  // Pass 1 — deterministic rules (always run, fast, can't-miss).
  const fallback = classifyFallback(text, privateKeywords);
  if (fallback.tier === 'PRIVATE') return fallback;

  // Pass 2 — Gemma 270M nuance.
  try {
    const clf = await loadClassifier();
    if (!clf) {
      return {
        ...fallback,
        reason: fallback.reason + ' [WebGPU unavailable, Gemma skipped]',
      };
    }

    const prompt = buildPrompt(text);
    const result = await clf(prompt, {
      max_new_tokens: 80,
      do_sample: false,
      return_full_text: false, // only new tokens
    });

    const generated = result?.[0]?.generated_text ?? '';
    const parsed = extractJSON(generated);

    if (parsed && (parsed.tier === 'PRIVATE' || parsed.tier === 'SHARED')) {
      return {
        tier: parsed.tier,
        sensitivity: Math.min(1, Math.max(0, Number(parsed.sensitivity ?? 0.5))),
        categories: Array.isArray(parsed.categories) ? parsed.categories : [],
        reason: String(parsed.reason ?? 'gemma-270m'),
      };
    }

    console.warn('[contxt] Gemma output unparseable — using fallback', generated.slice(0, 100));
  } catch (err) {
    // ONNX-runtime WASM aborts throw a bare number (a pointer), which stringifies
    // to something useless like "10736504". Decode it so the log is actionable.
    const detail =
      typeof err === 'number'
        ? `WASM abort (code ${err}) — ONNX runtime crashed during load/inference. ` +
          `Check the [contxt] env check line above: if crossOriginIsolated is ` +
          `false, the threaded WebGPU build can't get SharedArrayBuffer here.`
        : err?.stack || err?.message || String(err);
    console.warn('[contxt] Gemma inference error — using fallback:', detail);
  }

  return fallback;
}

// ── Privacy toggle overrides ──────────────────────────────────────────────────

/**
 * User toggles like "never share financials" are hard overrides.
 * If any toggle keyword appears in the result categories or reason,
 * the item is forced PRIVATE unconditionally.
 *
 * @param {{ tier, sensitivity, categories, reason }} result
 * @param {string[]} privateToggles - user-configured forced-private terms
 */
function applyToggles(result, privateToggles = [], text = '') {
  if (!privateToggles.length) return result;

  // Match toggles against BOTH the item text and the derived categories/reason,
  // so "force-private: financials" fires whether the word is in the item or in
  // a rule category.
  const haystack = [text, ...result.categories, result.reason]
    .join(' ')
    .toLowerCase();
  for (const toggle of privateToggles) {
    if (haystack.includes(toggle.toLowerCase())) {
      return {
        ...result,
        tier: 'PRIVATE',
        sensitivity: 1.0,
        reason: `forced PRIVATE by toggle: "${toggle}"`,
      };
    }
  }
  return result;
}

// ── Message handler (registered synchronously — always ready) ──────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== 'classify:offscreen') return false;

  const {
    text = '',
    privateKeywords = DEFAULT_PRIVATE_KEYWORDS,
    privateToggles = [],
  } = msg;

  classifyText(text, privateKeywords)
    .then((result) => applyToggles(result, privateToggles, text))
    .then((result) => sendResponse({ ok: true, ...result }))
    .catch((err) => sendResponse({ ok: false, error: String(err) }));

  return true; // keep channel open for async sendResponse
});

// ── Dev/test hook ──────────────────────────────────────────────────────────────
// Call directly from the offscreen document's DevTools console — no message
// plumbing, tests rules + toggles + Gemma end to end:
//   await __contxtClassify('Your ICICI loan EMI of Rs 45,000 is due')
//   await __contxtClassify('Team standup 10am', { privateToggles: ['standup'] })
globalThis.__contxtClassify = (text, opts = {}) =>
  classifyText(text, opts.privateKeywords).then((r) =>
    applyToggles(r, opts.privateToggles || [], text),
  );

console.info('[contxt] offscreen classifier ready (listener registered)');
