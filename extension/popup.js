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
import { pullGmail, pullCalendar, pullNotion } from './pull.js';
import { classifyFallback, DEFAULT_PRIVATE_KEYWORDS } from './rules.js';

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
  notionToken: 'notionAccessToken',
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
const clip = (s, n = 160) => { s = String(s || ''); return s.length > n ? s.slice(0, n - 1) + '…' : s; };

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
  const file = p.file ? esc(String(p.file).split('/').pop()) : 'model';
  const hasPct = typeof p.progress === 'number' && p.progress > 0;
  if (hasPct) {
    const pct = Math.round(p.progress);
    wrap.innerHTML =
      `<div class="muted">Downloading on-device model — ${file} (${pct}%)</div>` +
      `<div class="bar"><i style="width:${pct}%"></i></div>`;
  } else {
    // HF CDN sometimes omits content-length → no % available; show an
    // indeterminate bar so the download step still reads as "working".
    wrap.innerHTML =
      `<div class="muted">Downloading on-device model — ${file}… (~570MB, one-time)</div>` +
      `<div class="bar indet"><i></i></div>`;
  }
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
// Inline brand marks (crisp at any DPI, no network, CSP-safe).
const SRC_LOGO = {
  gmail:
    '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><rect x="2" y="4" width="20" height="16" rx="2" fill="#fff"/><path fill="#EA4335" d="M4 6v12H3a1 1 0 0 1-1-1V6a2 2 0 0 1 .9-1.67L12 11l9.1-6.67A2 2 0 0 1 22 6v11a1 1 0 0 1-1 1h-1V6l-8 5.9L4 6Z"/></svg>',
  calendar:
    '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2" fill="#fff"/><path fill="#4285F4" d="M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2H3V7Z"/><rect x="6.5" y="2" width="2" height="5" rx="1" fill="#4285F4"/><rect x="15.5" y="2" width="2" height="5" rx="1" fill="#4285F4"/><text x="12" y="18" font-size="8" font-weight="700" fill="#4285F4" text-anchor="middle">31</text></svg>',
  notion:
    '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><rect x="2.5" y="2.5" width="19" height="19" rx="3" fill="#fff" stroke="#111" stroke-width="1"/><path fill="#111" d="M8 7.5h2.1l4 6.1V7.5H16v9h-2.1l-4-6.1v6.1H8v-9Z"/></svg>',
};
function srcBadge(source) {
  const s = (source || 'notion').toLowerCase();
  return `<span class="src">${SRC_LOGO[s] || ''}<span>${esc(s)}</span></span>`;
}
async function loadContext() {
  $('ctxList').innerHTML = '<div class="muted">Loading your context…</div>';
  try {
    const resp = await send({ type: 'get:context', query: 'what am I working on' });
    if (!resp || resp.ok === false) throw new Error(resp?.error || 'no response');
    const cards = Array.isArray(resp.cards) ? resp.cards : [];
    if (!cards.length) {
      $('ctxList').innerHTML = '<div class="muted">No shared context yet. Connect a source, then refresh.</div>';
    } else {
      $('ctxList').innerHTML = cards.map((c) =>
        `<div class="ctx"><div class="top">${srcBadge(c.source)}` +
        `<span class="ttl">${esc(c.title)}</span></div>` +
        `<div class="sum">${esc(c.summary || c.body || '')}</div></div>`,
      ).join('');
    }
    const priv = resp.private_total ?? resp.private_withheld ?? 0;
    const src = resp.source === 'fixture' ? ' <span class="muted">(offline demo data)</span>' : '';
    $('privLine').innerHTML = `🔒 <b>${esc(priv)}</b> private item(s) kept on-device — never sent to any AI.${src}`;
  } catch (e) {
    $('ctxList').innerHTML = `<div class="muted">Bridge unavailable: ${esc(e.message || e)}</div>`;
    $('privLine').innerHTML = '';
  }
}

// Prefer LIVE context from the user's own accounts once connected; fall back to
// the bridge (seeded/demo) when no token is present yet.
async function smartLoad() {
  const s = await getLocal({ [KEYS.googleToken]: '', [KEYS.notionToken]: '' });
  if (s[KEYS.googleToken] || s[KEYS.notionToken]) return loadLiveContext(s[KEYS.googleToken], s[KEYS.notionToken]);
  return loadContext();
}

function _srcErr(name, e) {
  const m = String(e.message || e);
  return m.includes('auth-expired') ? `${name}: session expired — reconnect` : `${name}: ${m}`;
}

async function loadLiveContext(gToken, nToken) {
  $('ctxList').innerHTML = '<div class="muted">Pulling your live context…</div>';
  $('privLine').innerHTML = '';
  const { [KEYS.toggles]: toggles } = await getLocal({ [KEYS.toggles]: [] });
  const kw = [...DEFAULT_PRIVATE_KEYWORDS, ...(toggles || [])];

  const items = [];
  const errors = [];
  const tasks = [];
  if (gToken) {
    tasks.push(pullGmail(gToken).then((x) => items.push(...x)).catch((e) => errors.push(_srcErr('Gmail', e))));
    tasks.push(pullCalendar(gToken).then((x) => items.push(...x)).catch((e) => errors.push(_srcErr('Calendar', e))));
  }
  if (nToken) {
    tasks.push(pullNotion(nToken).then((x) => items.push(...x)).catch((e) => errors.push(_srcErr('Notion', e))));
  }
  await Promise.all(tasks);

  // Dedupe near-identical items — EmailAgg/Firefox-Relay forwards produce both
  // "Fwd: X" and "X". Key by source + title with the reply/forward prefix stripped.
  const seen = new Set();
  const deduped = [];
  for (const it of items) {
    const key = `${it.source}:${it.title.toLowerCase().replace(/^(fwd|fw|re):\s*/i, '').trim()}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(it);
  }

  // On-device tiering (deterministic rules): the crown-jewels guardrail decides
  // SHARED vs PRIVATE locally. PRIVATE items are shown here (on-device) but never
  // sent to any AI/cloud; SHARED items are what may be injected.
  const shared = [];
  const privateItems = [];
  for (const it of deduped) {
    const d = classifyFallback(it.text, kw);
    if (d.tier === 'PRIVATE') privateItems.push({ ...it, categories: d.categories });
    else shared.push(it);
  }

  // Cache a CAPPED set of SHARED cards so the claude.ai injection serves THIS live
  // context (one source of truth) and the cloud prompt stays tight. PRIVATE never cached.
  await setLocal({
    liveSharedCards: shared.slice(0, 6).map((c) => ({
      tier: 'shared', source: c.source, title: c.title, summary: clip(c.text, 220),
    })),
    livePrivateCount: privateItems.length,
    liveUpdatedAt: Date.now(),
  });

  renderLive(shared, privateItems, deduped.length, errors);
}

function renderLive(shared, privateItems, total, errors) {
  if (!total && !errors.length) {
    $('ctxList').innerHTML = '<div class="muted">No recent items found in your connected sources.</div>';
  } else if (!shared.length && total) {
    $('ctxList').innerHTML = `<div class="muted">All ${total} recent item(s) classified PRIVATE — kept on-device. Nothing shared.</div>`;
  } else if (shared.length) {
    $('ctxList').innerHTML = shared.map((c) =>
      `<div class="ctx"><div class="top">${srcBadge(c.source)}` +
      `<span class="ttl">${esc(c.title)}</span></div>` +
      `<div class="sum">${esc(clip(c.text))}</div></div>`,
    ).join('');
  } else {
    $('ctxList').innerHTML = '<div class="muted">Couldn\'t reach your sources — see below.</div>';
  }

  // The "kept on-device" section — visibility into what the gateway protected.
  if (privateItems.length) {
    $('privList').innerHTML = privateItems.map((c) =>
      `<div class="ctx priv"><div class="top">${srcBadge(c.source)}` +
      `<span class="ttl">${esc(c.title)}</span></div>` +
      `<div class="sum">kept on-device · flagged: <span class="cats">${esc((c.categories || []).join(', ') || 'private')}</span></div></div>`,
    ).join('');
  } else if (total) {
    $('privList').innerHTML = '<div class="muted">Nothing was classified private in this batch.</div>';
  }

  const errLine = errors.length ? ` <span class="muted">· ${esc(errors.join(' · '))}</span>` : '';
  $('privLine').innerHTML =
    `🔒 <b>${esc(privateItems.length)}</b> private item(s) kept on-device — never sent to any AI.` +
    ` <span class="muted">· live from your accounts</span>${errLine}`;
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
    smartLoad();
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
    await setLocal({
      [KEYS.notionConnected]: true,
      [KEYS.notionWorkspace]: res.workspace_name || '',
      [KEYS.notionToken]: res.access_token || '',
    });
    setStatusMsg('notionStatus', res.workspace_name ? 'Connected — ' + res.workspace_name : 'Connected', true);
    smartLoad();
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
$('refresh').addEventListener('click', smartLoad);
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

smartLoad();
