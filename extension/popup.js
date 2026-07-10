/**
 * Contxt popup — the demo surface for the full two-tier flow.
 *
 *   1. Classify on-device (rules; Gemma 270M best-effort) → PRIVATE | SHARED
 *   2. If SHARED  → offer "Distill to context card" via cloud Gemma
 *      If PRIVATE → show it stays on-device; the distill path is NOT offered
 *
 * The classify step keeps the ephemeral service worker out of the response
 * path (popup ↔ offscreen direct). The distill step calls cloud Gemma straight
 * from the popup (extension pages bypass CORS via host_permissions).
 */

import { distillItem } from './distill.js';

const $ = (id) => document.getElementById(id);

const KEYS = {
  toggles: 'privateToggles',
  apiKey: 'fireworksApiKey',
  endpoint: 'cloudEndpoint',
  model: 'cloudModel',
  source: 'lastSource',
};

// last classification, so the Distill button knows tier/source/text
let last = null;

// ── message + storage helpers ─────────────────────────────────────────────────

function send(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message));
      resolve(resp);
    });
  });
}

const getLocal = (defaults) =>
  new Promise((resolve) => chrome.storage.local.get(defaults, resolve));
const setLocal = (obj) =>
  new Promise((resolve) => chrome.storage.local.set(obj, resolve));

const parseToggles = (str) =>
  str.split(',').map((s) => s.trim()).filter(Boolean);

// ── rendering ─────────────────────────────────────────────────────────────────

function renderTier(r) {
  if (!r || r.ok === false) {
    $('result').innerHTML = `<div class="card">Error: ${r?.error ?? 'no response'}</div>`;
    return;
  }
  const cats = (r.categories || []).join(', ') || '—';
  $('result').innerHTML = `
    <div class="card">
      <span class="badge ${r.tier}">${r.tier}</span>
      <div class="row"><span class="k">sensitivity:</span> ${r.sensitivity}</div>
      <div class="row"><span class="k">categories:</span> <span class="cats">${cats}</span></div>
      <div class="row"><span class="k">reason:</span> ${r.reason || '—'}</div>
    </div>`;
}

function renderDistillAffordance(tier) {
  if (tier === 'PRIVATE') {
    $('distill').innerHTML =
      '<div class="lock">🔒 PRIVATE — kept on-device. Not sent to cloud Gemma.</div>';
    return;
  }
  $('distill').innerHTML =
    '<button id="distillBtn" class="secondary">☁️ Distill to context card (cloud Gemma)</button>' +
    '<div id="distillOut"></div>';
  $('distillBtn').addEventListener('click', runDistill);
}

function renderCard(card) {
  $('distillOut').innerHTML = `
    <div class="card">
      <span class="badge SHARED">CONTEXT CARD</span>
      <div class="row"><span class="k">title:</span> ${card.title}</div>
      <div class="row"><span class="k">summary:</span> ${card.summary ?? '—'}</div>
      <div class="row"><span class="k">sensitivity:</span> ${card.sensitivity_score}</div>
      <pre>${JSON.stringify(card, null, 2)}</pre>
    </div>`;
}

// ── actions ────────────────────────────────────────────────────────────────────

async function classify() {
  const text = $('text').value.trim();
  if (!text) return;

  const toggles = parseToggles($('toggles').value);
  const source = $('source').value;
  await setLocal({ [KEYS.toggles]: toggles, [KEYS.source]: source });

  $('go').disabled = true;
  $('status').textContent = 'Classifying on-device…';
  $('result').innerHTML = '';
  $('distill').innerHTML = '';

  try {
    await send({ type: 'ensure:offscreen' });
    const r = await send({ type: 'classify:offscreen', text, privateToggles: toggles });
    last = { text, source, tier: r?.tier };
    renderTier(r);
    if (r && r.ok !== false) renderDistillAffordance(r.tier);
    $('status').textContent = 'Done.';
  } catch (e) {
    $('status').textContent = '';
    renderTier({ ok: false, error: String(e.message || e) });
  } finally {
    $('go').disabled = false;
  }
}

async function runDistill() {
  if (!last) return;
  const btn = $('distillBtn');
  btn.disabled = true;
  $('status').textContent = 'Distilling via cloud Gemma…';

  const { [KEYS.apiKey]: apiKey, [KEYS.endpoint]: endpoint, [KEYS.model]: model } =
    await getLocal({ [KEYS.apiKey]: '', [KEYS.endpoint]: '', [KEYS.model]: '' });

  try {
    const card = await distillItem(last.text, {
      source: last.source,
      tier: last.tier,
      apiKey,
      endpoint: endpoint || undefined,
      model: model || undefined,
    });
    renderCard(card);
    $('status').textContent = 'Context card ready.';
  } catch (e) {
    // Surface to the popup AND the console (as requested for debugging).
    console.error('[contxt] distill failed:', e);
    $('distillOut').innerHTML = `<div class="card">Distill error: ${
      String(e.message || e)
    }</div>`;
    $('status').textContent = '';
  } finally {
    btn.disabled = false;
  }
}

// ── wire up + restore persisted settings ────────────────────────────────────────

$('go').addEventListener('click', classify);

// persist cloud settings as the user types
for (const [el, key] of [
  ['apiKey', KEYS.apiKey],
  ['endpoint', KEYS.endpoint],
  ['model', KEYS.model],
]) {
  $(el).addEventListener('change', () => setLocal({ [key]: $(el).value.trim() }));
}

getLocal({
  [KEYS.toggles]: [],
  [KEYS.apiKey]: '',
  [KEYS.endpoint]: '',
  [KEYS.model]: '',
  [KEYS.source]: 'notion',
}).then((s) => {
  $('toggles').value = (s[KEYS.toggles] || []).join(', ');
  $('apiKey').value = s[KEYS.apiKey] || '';
  $('endpoint').value = s[KEYS.endpoint] || '';
  $('model').value = s[KEYS.model] || '';
  $('source').value = s[KEYS.source] || 'notion';
});
