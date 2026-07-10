/**
 * Contxt popup — the demo-facing test surface for the Crown-Jewels Gateway.
 *
 * Flow (keeps the ephemeral service worker OUT of the classify path):
 *   1. Ask the background SW to ensure the offscreen document exists (fast).
 *   2. Send `classify:offscreen` DIRECTLY to the offscreen doc and await the
 *      result. The SW's listener ignores this type, so it never holds the
 *      port — no "message port closed" during the slow first model load.
 */

const $ = (id) => document.getElementById(id);

const TOGGLES_KEY = 'privateToggles';

// ── message helpers ─────────────────────────────────────────────────────────

function send(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message));
      resolve(resp);
    });
  });
}

// ── persistence of the force-private toggles ──────────────────────────────────

function loadToggles() {
  return new Promise((resolve) => {
    chrome.storage.local.get({ [TOGGLES_KEY]: [] }, (s) =>
      resolve(s[TOGGLES_KEY] || []),
    );
  });
}

function parseToggles(str) {
  return str
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
}

// ── render ─────────────────────────────────────────────────────────────────

function renderResult(r) {
  if (!r || r.ok === false) {
    $('result').innerHTML = `<div class="card">Error: ${
      r?.error ?? 'no response'
    }</div>`;
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

// ── main ─────────────────────────────────────────────────────────────────────

async function classify() {
  const text = $('text').value.trim();
  if (!text) return;

  const toggles = parseToggles($('toggles').value);
  chrome.storage.local.set({ [TOGGLES_KEY]: toggles });

  $('go').disabled = true;
  $('status').textContent = 'Ensuring classifier…';
  $('result').innerHTML = '';

  try {
    await send({ type: 'ensure:offscreen' });
    $('status').textContent =
      'Classifying (first run downloads the Gemma model — may take a moment)…';

    const resp = await send({
      type: 'classify:offscreen',
      text,
      privateToggles: toggles,
    });

    renderResult(resp);
    $('status').textContent = 'Done.';
  } catch (e) {
    $('status').textContent = '';
    renderResult({ ok: false, error: String(e.message || e) });
  } finally {
    $('go').disabled = false;
  }
}

// ── wire up ────────────────────────────────────────────────────────────────

$('go').addEventListener('click', classify);

loadToggles().then((t) => {
  $('toggles').value = t.join(', ');
});
