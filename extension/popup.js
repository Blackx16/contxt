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
  // Read by the background service worker's getBridgeConfig().
  bridge: 'bridgeUrl',
  bridgeToken: 'bridgeToken',
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

// ── least-privilege host access ─────────────────────────────────────────────
// The manifest ships with permission for the default hosts only (localhost
// bridge + Fireworks) instead of <all_urls>. A user-pasted custom cloud endpoint
// or bridge lives on an unknown origin, so we request just that origin on demand
// — from a user gesture — against the manifest's optional_host_permissions.

const originPattern = (url) => {
  try {
    const u = new URL(url);
    // Match patterns can't carry a port, and the default bridge is on :8787 —
    // so build a host-only pattern (it matches the host on any port), the same
    // granularity the manifest's http://127.0.0.1/* default uses.
    return `${u.protocol}//${u.hostname}/*`;
  } catch {
    return null; // not a URL yet; let the eventual fetch surface a real error
  }
};

// Request host access for `url`'s origin. Safe to call from any user-gesture
// handler; requesting an already-granted origin (e.g. the default Fireworks or
// localhost host) resolves true silently with no prompt. Returns false on
// deny/error.
const ensureHostPermission = (url) => {
  const pattern = originPattern(url);
  if (!pattern) return Promise.resolve(true);
  return chrome.permissions
    .request({ origins: [pattern] })
    .then((granted) => Boolean(granted))
    .catch(() => false);
};

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

  // A custom endpoint sits on an origin we don't hold by default — secure host
  // access now, while this click's user gesture is still active (required for
  // chrome.permissions.request). The default Fireworks host is already granted.
  const customEndpoint = $('endpoint').value.trim();
  if (customEndpoint && !(await ensureHostPermission(customEndpoint))) {
    $('distillOut').innerHTML = `<div class="card">Distill blocked: permission to reach ${
      originPattern(customEndpoint) || customEndpoint
    } was denied.</div>`;
    return;
  }

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
  ['bridge', KEYS.bridge],
  ['bridgeToken', KEYS.bridgeToken],
]) {
  $(el).addEventListener('change', () => {
    const val = $(el).value.trim();
    setLocal({ [key]: val });
    // Secure host access to a custom cloud endpoint or bridge the moment it's
    // set, from this change gesture. The bridge fetch runs in the background
    // service worker, which has no user gesture and so can't prompt — this popup
    // is the only place the grant can be requested. An already-granted origin
    // (the default localhost/Fireworks hosts) is a silent no-op.
    if ((el === 'endpoint' || el === 'bridge') && val) ensureHostPermission(val);
  });
}

getLocal({
  [KEYS.toggles]: [],
  [KEYS.apiKey]: '',
  [KEYS.endpoint]: '',
  [KEYS.model]: '',
  [KEYS.source]: 'notion',
  [KEYS.bridge]: '',
  [KEYS.bridgeToken]: '',
}).then((s) => {
  $('toggles').value = (s[KEYS.toggles] || []).join(', ');
  $('apiKey').value = s[KEYS.apiKey] || '';
  $('endpoint').value = s[KEYS.endpoint] || '';
  $('model').value = s[KEYS.model] || '';
  $('source').value = s[KEYS.source] || 'notion';
  $('bridge').value = s[KEYS.bridge] || '';
  $('bridgeToken').value = s[KEYS.bridgeToken] || '';
});
