/**
 * Contxt popup — consumer surface.
 *
 *   Setup:   connect Google (Gmail+Calendar) + Notion, choose On-device vs Online.
 *   Context: pull SHARED context from the bridge and show it, tagged by source,
 *            with a live "N private kept on-device" trust count.
 *   Model:   On-device mode downloads Gemma 3 270M once, with a visible progress bar.
 *   Manual:  the old paste-and-classify dev tool, tucked into an <details>.
 *
 * OAuth: Google is a pure client-side implicit flow via chrome.identity. Notion
 * needs a server-side token exchange (its secret can't live in the browser), so
 * the auth code is POSTed to the bridge's /notion/exchange.
 */
import { distillItem } from './distill.js';

const $ = (id) => document.getElementById(id);

const KEYS = {
  toggles: 'privateToggles',
  apiKey: 'fireworksApiKey',
  endpoint: 'cloudEndpoint',
  model: 'cloudModel',
  source: 'lastSource',
  bridge: 'bridgeUrl',
  bridgeToken: 'bridgeToken',
  mode: 'contxtMode', // 'local' | 'online'
  googleClientId: 'googleClientId',
  notionClientId: 'notionClientId',
  googleToken: 'googleAccessToken',
  googleEmail: 'googleEmail',
  notionConnected: 'notionConnected',
  notionWorkspace: 'notionWorkspace',
};

const GOOGLE_SCOPES = [
  'openid', 'email', 'profile',
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/calendar.readonly',
].join(' ');

let last = null; // last manual classification (tier/source/text) for Distill

// ── message + storage helpers ──────────────────────────────────────────────
function send(msg) {
  return new Promise((resolve, reject) => {
    chrome.runtime.sendMessage(msg, (resp) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message));
      resolve(resp);
    });
  });
}
const getLocal = (d) => new Promise((r) => chrome.storage.local.get(d, r));
const setLocal = (o) => new Promise((r) => chrome.storage.local.set(o, r));
const parseToggles = (s) => s.split(',').map((x) => x.trim()).filter(Boolean);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ── least-privilege host access (endpoint / bridge / API origins) ────────────
const originPattern = (url) => {
  try { const u = new URL(url); return `${u.protocol}//${u.hostname}/*`; } catch { return null; }
};
const ensureHostPermission = (url) => {
  const p = originPattern(url);
  if (!p) return Promise.resolve(true);
  return chrome.permissions.request({ origins: [p] }).then(Boolean).catch(() => false);
};

// ══ MODE (on-device vs online) ═══════════════════════════════════════════════
async function setMode(mode) {
  await setLocal({ [KEYS.mode]: mode });
  renderMode(mode);
  if (mode === 'local') ensureModelUI(); // offer/download the model
}
function renderMode(mode) {
  $('modeLocal').classList.toggle('active', mode === 'local');
  $('modeOnline').classList.toggle('active', mode === 'online');
  if (mode === 'online') {
    $('modelWrap').innerHTML =
      '<div class="muted">☁️ Online mode — no model downloaded. Only shared context is stored; nothing private is kept.</div>';
  }
}

// ── model download + progress ───────────────────────────────────────────────
let _modelListening = false;
function listenForModelProgress() {
  if (_modelListening) return;
  _modelListening = true;
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg?.type !== 'model:progress') return;
    renderModelProgress(msg);
  });
}
function renderModelProgress(p) {
  const wrap = $('modelWrap');
  if (p.status === 'ready') {
    wrap.innerHTML = '<div class="muted">🔒 On-device model ready — private items classified locally. ✓</div>';
    return;
  }
  if (p.status === 'unavailable') {
    wrap.innerHTML =
      '<div class="muted">⚠️ WebGPU unavailable here — falling back to deterministic rules on-device (no model). Private items still stay local.</div>';
    return;
  }
  const pct = Math.round((p.progress ?? 0));
  const file = p.file ? esc(p.file.split('/').pop()) : 'model';
  wrap.innerHTML =
    `<div class="muted">Downloading on-device model — ${file} (${pct}%)</div>` +
    `<div class="bar"><i style="width:${pct}%"></i></div>`;
}
async function ensureModelUI() {
  listenForModelProgress();
  $('modelWrap').innerHTML =
    '<button id="dlModel" class="ghost">⬇︎ Download on-device model (~570MB, once)</button>' +
    '<div class="hint">Runs Gemma 3 270M in your browser via WebGPU. Weights cache after the first download.</div>';
  $('dlModel').addEventListener('click', downloadModel);
}
async function downloadModel() {
  const btn = $('dlModel');
  if (btn) btn.disabled = true;
  $('modelWrap').innerHTML = '<div class="muted">Preparing model…</div><div class="bar"><i></i></div>';
  try {
    await send({ type: 'ensure:offscreen' });
    const r = await send({ type: 'model:load:offscreen' }); // resolves when loaded
    renderModelProgress(r?.ready ? { status: 'ready' } : { status: 'unavailable' });
  } catch (e) {
    $('modelWrap').innerHTML = `<div class="muted">Model load failed: ${esc(e.message || e)} — rules fallback active.</div>`;
  }
}

// ══ CONTEXT VIEW ═════════════════════════════════════════════════════════════
const SRC_ICON = { gmail: '📧', calendar: '📅', notion: '📝' };
async function loadContext() {
  $('ctxList').innerHTML = '<div class="muted">Loading your context…</div>';
  try {
    const resp = await send({ type: 'get:context', query: 'what am I working on' });
    if (!resp || resp.ok === false) throw new Error(resp?.error || 'no response');
    const cards = Array.isArray(resp.cards) ? resp.cards : [];
    if (!cards.length) {
      $('ctxList').innerHTML = '<div class="muted">No shared context yet. Connect a source, then refresh.</div>';
    } else {
      $('ctxList').innerHTML = cards.map((c) => {
        const s = (c.source || 'notion').toLowerCase();
        const ico = SRC_ICON[s] || '•';
        return `<div class="ctx"><div class="top"><span class="src ${esc(s)}">${ico} ${esc(s)}</span>` +
          `<span class="ttl">${esc(c.title)}</span></div>` +
          `<div class="sum">${esc(c.summary || c.body || '')}</div></div>`;
      }).join('');
    }
    const priv = resp.private_total ?? resp.private_withheld ?? 0;
    const src = resp.source === 'fixture' ? ' <span class="muted">(offline demo data)</span>' : '';
    $('privLine').innerHTML = `🔒 <b>${priv}</b> private item(s) kept on-device — never sent to any AI.${src}`;
  } catch (e) {
    $('ctxList').innerHTML = `<div class="muted">Bridge unavailable: ${esc(e.message || e)}</div>`;
    $('privLine').innerHTML = '';
  }
}

// ══ OAUTH ════════════════════════════════════════════════════════════════════
const REDIRECT = () => chrome.identity.getRedirectURL();

function launchAuth(url) {
  return new Promise((resolve, reject) => {
    chrome.identity.launchWebAuthFlow({ url, interactive: true }, (redirect) => {
      const err = chrome.runtime.lastError;
      if (err) return reject(new Error(err.message));
      if (!redirect) return reject(new Error('auth cancelled'));
      resolve(redirect);
    });
  });
}

async function connectGoogle() {
  const { [KEYS.googleClientId]: cid } = await getLocal({ [KEYS.googleClientId]: '' });
  if (!cid) return setStatusMsg('googleStatus', 'Add a Google client ID in Connection setup first', false);
  const url =
    'https://accounts.google.com/o/oauth2/v2/auth?client_id=' + encodeURIComponent(cid) +
    '&response_type=token&redirect_uri=' + encodeURIComponent(REDIRECT()) +
    '&scope=' + encodeURIComponent(GOOGLE_SCOPES) + '&prompt=consent';
  try {
    const redirect = await launchAuth(url);
    const frag = new URLSearchParams(new URL(redirect).hash.slice(1));
    const token = frag.get('access_token');
    if (!token) throw new Error('no access_token in redirect');
    // Prove the token: fetch the account email.
    await ensureHostPermission('https://www.googleapis.com/');
    const info = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', {
      headers: { Authorization: 'Bearer ' + token },
    }).then((r) => (r.ok ? r.json() : {}));
    await setLocal({ [KEYS.googleToken]: token, [KEYS.googleEmail]: info.email || '' });
    setStatusMsg('googleStatus', info.email ? 'Connected as ' + info.email : 'Connected', true);
    loadContext();
  } catch (e) {
    setStatusMsg('googleStatus', 'Connect failed: ' + (e.message || e), false);
  }
}

async function connectNotion() {
  const { [KEYS.notionClientId]: cid } = await getLocal({ [KEYS.notionClientId]: '' });
  if (!cid) return setStatusMsg('notionStatus', 'Add a Notion client ID in Connection setup first', false);
  const url =
    'https://api.notion.com/v1/oauth/authorize?client_id=' + encodeURIComponent(cid) +
    '&response_type=code&owner=user&redirect_uri=' + encodeURIComponent(REDIRECT());
  try {
    const redirect = await launchAuth(url);
    const code = new URL(redirect).searchParams.get('code');
    if (!code) throw new Error('no code in redirect');
    // Notion's token exchange needs the client secret → do it on the bridge.
    const { [KEYS.bridge]: base } = await getLocal({ [KEYS.bridge]: '' });
    const bridge = (base || 'http://127.0.0.1:8787').replace(/\/$/, '');
    await ensureHostPermission(bridge);
    const res = await fetch(bridge + '/notion/exchange', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code, redirect_uri: REDIRECT() }),
    }).then((r) => r.json());
    if (res.error) throw new Error(res.error);
    await setLocal({ [KEYS.notionConnected]: true, [KEYS.notionWorkspace]: res.workspace_name || '' });
    setStatusMsg('notionStatus', res.workspace_name ? 'Connected — ' + res.workspace_name : 'Connected', true);
    loadContext();
  } catch (e) {
    setStatusMsg('notionStatus', 'Connect failed: ' + (e.message || e), false);
  }
}

function setStatusMsg(id, text, on) {
  const el = $(id);
  el.textContent = text;
  el.classList.toggle('on', !!on);
}

// ══ MANUAL classify / distill (advanced, preserved) ══════════════════════════
function renderTier(r) {
  if (!r || r.ok === false) { $('result').innerHTML = `<div class="ctx">Error: ${esc(r?.error ?? 'no response')}</div>`; return; }
  const cats = (r.categories || []).join(', ') || '—';
  $('result').innerHTML =
    `<div class="ctx"><span class="badge ${r.tier}">${r.tier}</span>` +
    `<div class="row"><span class="k">sensitivity:</span> ${esc(r.sensitivity)}</div>` +
    `<div class="row"><span class="k">categories:</span> ${esc(cats)}</div>` +
    `<div class="row"><span class="k">reason:</span> ${esc(r.reason || '—')}</div></div>`;
}
function renderDistillAffordance(tier) {
  if (tier === 'PRIVATE') { $('distill').innerHTML = '<div class="row" style="color:#b91c1c">🔒 PRIVATE — kept on-device. Not sent to cloud Gemma.</div>'; return; }
  $('distill').innerHTML = '<button id="distillBtn" class="secondary">☁️ Distill to context card (cloud Gemma)</button><div id="distillOut"></div>';
  $('distillBtn').addEventListener('click', runDistill);
}
function renderCard(card) {
  $('distillOut').innerHTML = `<div class="ctx"><span class="badge SHARED">CONTEXT CARD</span>` +
    `<div class="row"><span class="k">title:</span> ${esc(card.title)}</div>` +
    `<div class="row"><span class="k">summary:</span> ${esc(card.summary ?? '—')}</div>` +
    `<pre>${esc(JSON.stringify(card, null, 2))}</pre></div>`;
}
async function classifyManual() {
  const text = $('text').value.trim();
  if (!text) return;
  const toggles = parseToggles($('toggles').value);
  const source = $('source').value;
  await setLocal({ [KEYS.toggles]: toggles, [KEYS.source]: source });
  $('go').disabled = true; $('status').textContent = 'Classifying on-device…';
  $('result').innerHTML = ''; $('distill').innerHTML = '';
  try {
    await send({ type: 'ensure:offscreen' });
    const r = await send({ type: 'classify:offscreen', text, privateToggles: toggles });
    last = { text, source, tier: r?.tier };
    renderTier(r);
    if (r && r.ok !== false) renderDistillAffordance(r.tier);
    $('status').textContent = 'Done.';
  } catch (e) {
    $('status').textContent = ''; renderTier({ ok: false, error: String(e.message || e) });
  } finally { $('go').disabled = false; }
}
async function runDistill() {
  if (!last) return;
  const btn = $('distillBtn');
  const customEndpoint = $('endpoint').value.trim();
  if (customEndpoint && !(await ensureHostPermission(customEndpoint))) {
    $('distillOut').innerHTML = `<div class="ctx">Distill blocked: permission to reach ${esc(originPattern(customEndpoint) || customEndpoint)} was denied.</div>`;
    return;
  }
  btn.disabled = true; $('status').textContent = 'Distilling via cloud Gemma…';
  const { [KEYS.apiKey]: apiKey, [KEYS.endpoint]: endpoint, [KEYS.model]: model } =
    await getLocal({ [KEYS.apiKey]: '', [KEYS.endpoint]: '', [KEYS.model]: '' });
  try {
    const card = await distillItem(last.text, { source: last.source, tier: last.tier, apiKey, endpoint: endpoint || undefined, model: model || undefined });
    renderCard(card); $('status').textContent = 'Context card ready.';
  } catch (e) {
    console.error('[contxt] distill failed:', e);
    $('distillOut').innerHTML = `<div class="ctx">Distill error: ${esc(e.message || e)}</div>`;
    $('status').textContent = '';
  } finally { btn.disabled = false; }
}

// ══ WIRE-UP ══════════════════════════════════════════════════════════════════
$('modeLocal').addEventListener('click', () => setMode('local'));
$('modeOnline').addEventListener('click', () => setMode('online'));
$('connectGoogle').addEventListener('click', connectGoogle);
$('connectNotion').addEventListener('click', connectNotion);
$('refresh').addEventListener('click', loadContext);
$('go').addEventListener('click', classifyManual);

for (const [el, key] of [
  ['apiKey', KEYS.apiKey], ['endpoint', KEYS.endpoint], ['model', KEYS.model],
  ['bridge', KEYS.bridge], ['bridgeToken', KEYS.bridgeToken],
  ['googleClientId', KEYS.googleClientId], ['notionClientId', KEYS.notionClientId],
]) {
  $(el).addEventListener('change', () => {
    const val = $(el).value.trim();
    setLocal({ [key]: val });
    if ((el === 'endpoint' || el === 'bridge') && val) ensureHostPermission(val);
  });
}

// restore persisted state + first render
getLocal({
  [KEYS.toggles]: [], [KEYS.apiKey]: '', [KEYS.endpoint]: '', [KEYS.model]: '', [KEYS.source]: 'notion',
  [KEYS.bridge]: '', [KEYS.bridgeToken]: '', [KEYS.mode]: '',
  [KEYS.googleClientId]: '', [KEYS.notionClientId]: '',
  [KEYS.googleEmail]: '', [KEYS.notionConnected]: false, [KEYS.notionWorkspace]: '',
}).then((s) => {
  $('toggles').value = (s[KEYS.toggles] || []).join(', ');
  $('apiKey').value = s[KEYS.apiKey] || '';
  $('endpoint').value = s[KEYS.endpoint] || '';
  $('model').value = s[KEYS.model] || '';
  $('source').value = s[KEYS.source] || 'notion';
  $('bridge').value = s[KEYS.bridge] || '';
  $('bridgeToken').value = s[KEYS.bridgeToken] || '';
  $('googleClientId').value = s[KEYS.googleClientId] || '';
  $('notionClientId').value = s[KEYS.notionClientId] || '';
  try { $('redirectHint').textContent = 'Redirect URI to register: ' + REDIRECT(); } catch { /* identity perm */ }
  if (s[KEYS.googleEmail]) setStatusMsg('googleStatus', 'Connected as ' + s[KEYS.googleEmail], true);
  if (s[KEYS.notionConnected]) setStatusMsg('notionStatus', s[KEYS.notionWorkspace] ? 'Connected — ' + s[KEYS.notionWorkspace] : 'Connected', true);
  if (s[KEYS.mode]) renderMode(s[KEYS.mode]);
  if (s[KEYS.mode] === 'local') { listenForModelProgress(); ensureModelUI(); }
});

loadContext();
