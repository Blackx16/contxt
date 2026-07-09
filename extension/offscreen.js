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

import {
  pipeline,
  env,
} from 'https://cdn.jsdelivr.net/npm/@huggingface/transformers@3/dist/transformers.min.js';
import { classifyFallback, ruleHits, DEFAULT_PRIVATE_KEYWORDS } from './rules.js';

// ── Transformers.js config ────────────────────────────────────────────────────

// Cache downloaded weights so the user only pays the download cost once.
env.useBrowserCache = true;
// Disable Node.js fs — we're in a browser context.
env.useFS = false;

// Gemma 3 270M Q4 ONNX model on Hugging Face.
// Weights are ~270 MB on first load; subsequent loads are from Cache API.
const MODEL_ID = 'onnx-community/gemma-3-270m-it-ONNX';

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
    console.warn('[contxt] Gemma inference error — using fallback:', err);
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
function applyToggles(result, privateToggles = []) {
  if (!privateToggles.length) return result;

  const combined = [...result.categories, result.reason].join(' ').toLowerCase();
  for (const toggle of privateToggles) {
    if (combined.includes(toggle.toLowerCase())) {
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

// ── Message handler ───────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type !== 'classify:offscreen') return false;

  const {
    text = '',
    privateKeywords = DEFAULT_PRIVATE_KEYWORDS,
    privateToggles = [],
  } = msg;

  classifyText(text, privateKeywords)
    .then((result) => applyToggles(result, privateToggles))
    .then((result) => sendResponse({ ok: true, ...result }))
    .catch((err) => sendResponse({ ok: false, error: String(err) }));

  return true; // keep channel open for async sendResponse
});
