<script>
  import { onMount } from 'svelte';
  import { pullGmail, pullCalendar, pullNotion } from '../pull.js';
  import { classifyFallback, DEFAULT_PRIVATE_KEYWORDS } from '../rules.js';
  import { distillItem } from '../distill.js';

  const KEYS = {
    toggles: 'privateToggles', apiKey: 'fireworksApiKey', endpoint: 'cloudEndpoint',
    model: 'cloudModel', source: 'lastSource', bridge: 'bridgeUrl', bridgeToken: 'bridgeToken',
    mode: 'contxtMode', googleClientId: 'googleClientId', notionClientId: 'notionClientId',
    googleToken: 'googleAccessToken', googleEmail: 'googleEmail',
    notionConnected: 'notionConnected', notionWorkspace: 'notionWorkspace', notionToken: 'notionAccessToken'
  };
  const GOOGLE_SCOPES = [
    'openid', 'email', 'profile',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/calendar.readonly'
  ].join(' ');
  const SRC_LOGO = {
    gmail: '<svg viewBox="0 0 24 24" width="13" height="13"><rect x="2" y="4" width="20" height="16" rx="2" fill="#fff"/><path fill="#EA4335" d="M4 6v12H3a1 1 0 0 1-1-1V6a2 2 0 0 1 .9-1.67L12 11l9.1-6.67A2 2 0 0 1 22 6v11a1 1 0 0 1-1 1h-1V6l-8 5.9L4 6Z"/></svg>',
    calendar: '<svg viewBox="0 0 24 24" width="13" height="13"><rect x="3" y="5" width="18" height="16" rx="2" fill="#fff"/><path fill="#4285F4" d="M3 7a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2H3V7Z"/><rect x="6.5" y="2" width="2" height="5" rx="1" fill="#4285F4"/><rect x="15.5" y="2" width="2" height="5" rx="1" fill="#4285F4"/><text x="12" y="18" font-size="8" font-weight="700" fill="#4285F4" text-anchor="middle">31</text></svg>',
    notion: '<svg viewBox="0 0 24 24" width="13" height="13"><rect x="2.5" y="2.5" width="19" height="19" rx="3" fill="#fff" stroke="#111" stroke-width="1"/><path fill="#111" d="M8 7.5h2.1l4 6.1V7.5H16v9h-2.1l-4-6.1v6.1H8v-9Z"/></svg>'
  };

  // ── reactive state ──────────────────────────────────────────────────────
  let mode = $state('');
  let googleStatus = $state('Not connected');
  let googleOk = $state(false);
  let notionStatus = $state('Not connected');
  let notionOk = $state(false);
  let model = $state({ status: 'idle' }); // idle | prompt | downloading | ready | unavailable | error

  let ctxMsg = $state('No context yet — connect a source or refresh.');
  let shared = $state([]);
  let priv = $state([]);
  let privCount = $state(0);
  let ctxSource = $state('');
  let ctxErrors = $state([]);

  let cfg = $state({
    toggles: '', apiKey: '', endpoint: '', model: '', source: 'notion',
    bridge: '', bridgeToken: '', googleClientId: '', notionClientId: ''
  });
  let redirectUri = $state('—');

  let manualText = $state('');
  let manualStatus = $state('');
  let manualResult = $state(null);
  let distillOut = $state(null);
  let last = null;

  // ── helpers ─────────────────────────────────────────────────────────────
  const send = (msg) => new Promise((res, rej) => chrome.runtime.sendMessage(msg, (r) => {
    const e = chrome.runtime.lastError; e ? rej(new Error(e.message)) : res(r);
  }));
  const getLocal = (d) => new Promise((r) => chrome.storage.local.get(d, r));
  const setLocal = (o) => new Promise((r) => chrome.storage.local.set(o, r));
  const parseToggles = (str) => str.split(',').map((x) => x.trim()).filter(Boolean);
  const clip = (str, n = 160) => { str = String(str || ''); return str.length > n ? str.slice(0, n - 1) + '…' : str; };
  const originPattern = (url) => { try { const u = new URL(url); return `${u.protocol}//${u.hostname}/*`; } catch { return null; } };
  const ensureHostPermission = (url) => { const p = originPattern(url); if (!p) return Promise.resolve(true); return chrome.permissions.request({ origins: [p] }).then(Boolean).catch(() => false); };
  const REDIRECT = () => chrome.identity.getRedirectURL();
  const keywords = () => [...DEFAULT_PRIVATE_KEYWORDS, ...parseToggles(cfg.toggles)];

  function persist(key, val) {
    setLocal({ [key]: val });
    if ((key === KEYS.endpoint || key === KEYS.bridge) && val) ensureHostPermission(val);
  }

  // ── mode + model ──────────────────────────────────────────────────────────
  async function setMode(m) { mode = m; await setLocal({ [KEYS.mode]: m }); if (m === 'local') offerModel(); }
  function offerModel() { if (model.status !== 'ready') model = { status: 'prompt' }; }
  async function downloadModel() {
    model = { status: 'downloading', file: 'model', pct: null };
    try {
      await send({ type: 'ensure:offscreen' });
      const r = await send({ type: 'model:load:offscreen' });
      model = r?.ready ? { status: 'ready' } : { status: 'unavailable' };
    } catch (e) { model = { status: 'error', msg: String(e.message || e) }; }
  }
  function applyProgress(p) {
    if (p.status === 'ready') { model = { status: 'ready' }; return; }
    if (p.status === 'unavailable') { model = { status: 'unavailable' }; return; }
    const file = p.file ? String(p.file).split('/').pop() : 'model';
    const hasPct = typeof p.progress === 'number' && p.progress > 0;
    model = { status: 'downloading', file, pct: hasPct ? Math.round(p.progress) : null };
  }

  // ── context ─────────────────────────────────────────────────────────────
  const SRC_ORDER = ['calendar', 'gmail', 'notion'];
  async function smartLoad() {
    const st = await getLocal({ [KEYS.googleToken]: '', [KEYS.notionToken]: '' });
    if (st[KEYS.googleToken] || st[KEYS.notionToken]) return loadLive(st[KEYS.googleToken], st[KEYS.notionToken]);
    return loadBridge();
  }
  async function loadBridge() {
    ctxMsg = 'Loading your context…'; ctxErrors = [];
    try {
      const resp = await send({ type: 'get:context', query: 'what am I working on' });
      if (!resp || resp.ok === false) throw new Error(resp?.error || 'no response');
      shared = (resp.cards || []).map((c) => ({ source: c.source, title: c.title, sum: c.summary || c.body || '' }));
      priv = []; privCount = resp.private_total ?? resp.private_withheld ?? 0; ctxSource = resp.source || 'bridge';
      ctxMsg = shared.length ? '' : 'No shared context yet. Connect a source, then refresh.';
    } catch (e) { ctxMsg = 'Bridge unavailable: ' + (e.message || e); shared = []; }
  }
  function srcErr(name, e) { const m = String(e.message || e); return m.includes('auth-expired') ? `${name}: session expired — reconnect` : `${name}: ${m}`; }
  async function loadLive(gToken, nToken) {
    ctxMsg = 'Pulling your live context…'; ctxErrors = []; ctxSource = 'live';
    const kw = keywords();
    const items = []; const errors = []; const tasks = [];
    if (gToken) {
      tasks.push(pullGmail(gToken).then((x) => items.push(...x)).catch((e) => errors.push(srcErr('Gmail', e))));
      tasks.push(pullCalendar(gToken).then((x) => items.push(...x)).catch((e) => errors.push(srcErr('Calendar', e))));
    }
    if (nToken) tasks.push(pullNotion(nToken).then((x) => items.push(...x)).catch((e) => errors.push(srcErr('Notion', e))));
    await Promise.all(tasks);
    // dedupe Fwd:/Re:
    const seen = new Set(); const deduped = [];
    for (const it of items) {
      const key = `${it.source}:${it.title.toLowerCase().replace(/^(fwd|fw|re):\s*/i, '').trim()}`;
      if (seen.has(key)) continue; seen.add(key); deduped.push(it);
    }
    const sh = []; const pv = [];
    for (const it of deduped) {
      const d = classifyFallback(it.text, kw);
      if (d.tier === 'PRIVATE') pv.push({ source: it.source, title: it.title, categories: d.categories });
      else sh.push({ source: it.source, title: it.title, sum: clip(it.text) });
    }
    const toCard = (c) => ({ tier: 'shared', source: c.source, title: c.title, summary: clip(c.sum, 220) });
    // Raw items (extension-only) — the background re-tiers these against the live
    // privacy policy so the site's toggles re-classify in real time. Plaintext
    // stays in extension storage; only sealed blobs cross the bridge.
    const liveItems = deduped.map((it, i) => ({
      id: `live_${i}`, source: it.source, title: it.title, text: clip(it.text, 600),
    }));
    await setLocal({
      liveItems,
      liveSharedCards: sh.slice(0, 6).map(toCard),  // legacy fallback — tight injection
      liveSharedCardsFull: sh.map(toCard),           // legacy fallback — full list
      livePrivateCount: pv.length, liveUpdatedAt: Date.now()
    });
    shared = sh; priv = pv; privCount = pv.length; ctxErrors = errors;
    ctxMsg = deduped.length ? (sh.length ? '' : `All ${deduped.length} recent item(s) classified PRIVATE — kept on-device.`) : (errors.length ? '' : 'No recent items found.');
  }

  // ── oauth ───────────────────────────────────────────────────────────────
  function launchAuth(url) {
    return new Promise((res, rej) => chrome.identity.launchWebAuthFlow({ url, interactive: true }, (redirect) => {
      const e = chrome.runtime.lastError; if (e) return rej(new Error(e.message));
      if (!redirect) return rej(new Error('auth cancelled')); res(redirect);
    }));
  }
  async function connectGoogle() {
    if (!cfg.googleClientId) { googleStatus = 'Add a Google client ID in Connection setup first'; googleOk = false; return; }
    const url = 'https://accounts.google.com/o/oauth2/v2/auth?client_id=' + encodeURIComponent(cfg.googleClientId) +
      '&response_type=token&redirect_uri=' + encodeURIComponent(REDIRECT()) +
      '&scope=' + encodeURIComponent(GOOGLE_SCOPES) + '&prompt=consent';
    try {
      const redirect = await launchAuth(url);
      const token = new URLSearchParams(new URL(redirect).hash.slice(1)).get('access_token');
      if (!token) throw new Error('no access_token');
      await ensureHostPermission('https://www.googleapis.com/');
      const info = await fetch('https://www.googleapis.com/oauth2/v3/userinfo', { headers: { Authorization: 'Bearer ' + token } }).then((r) => (r.ok ? r.json() : {}));
      await setLocal({ [KEYS.googleToken]: token, [KEYS.googleEmail]: info.email || '' });
      googleOk = true; googleStatus = info.email ? 'Connected as ' + info.email : 'Connected'; smartLoad();
    } catch (e) { googleOk = false; googleStatus = 'Connect failed: ' + (e.message || e); }
  }
  async function connectNotion() {
    if (!cfg.notionClientId) { notionStatus = 'Add a Notion client ID in Connection setup first'; notionOk = false; return; }
    const url = 'https://api.notion.com/v1/oauth/authorize?client_id=' + encodeURIComponent(cfg.notionClientId) +
      '&response_type=code&owner=user&redirect_uri=' + encodeURIComponent(REDIRECT());
    try {
      const redirect = await launchAuth(url);
      const code = new URL(redirect).searchParams.get('code');
      if (!code) throw new Error('no code');
      const bridge = (cfg.bridge || 'http://127.0.0.1:8787').replace(/\/$/, '');
      await ensureHostPermission(bridge);
      const res = await fetch(bridge + '/notion/exchange', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ code, redirect_uri: REDIRECT() })
      }).then((r) => r.json());
      if (res.error) throw new Error(res.error);
      await setLocal({ [KEYS.notionConnected]: true, [KEYS.notionWorkspace]: res.workspace_name || '', [KEYS.notionToken]: res.access_token || '' });
      notionOk = true; notionStatus = res.workspace_name ? 'Connected — ' + res.workspace_name : 'Connected'; smartLoad();
    } catch (e) { notionOk = false; notionStatus = 'Connect failed: ' + (e.message || e); }
  }

  // ── manual classify / distill ─────────────────────────────────────────────
  async function classifyManual() {
    const text = manualText.trim(); if (!text) return;
    const toggles = parseToggles(cfg.toggles);
    await setLocal({ [KEYS.toggles]: toggles, [KEYS.source]: cfg.source });
    manualStatus = 'Classifying on-device…'; manualResult = null; distillOut = null;
    try {
      await send({ type: 'ensure:offscreen' });
      const r = await send({ type: 'classify:offscreen', text, privateToggles: toggles });
      last = { text, source: cfg.source, tier: r?.tier };
      manualResult = r; manualStatus = 'Done.';
    } catch (e) { manualStatus = ''; manualResult = { ok: false, error: String(e.message || e) }; }
  }
  async function runDistill() {
    if (!last) return;
    if (cfg.endpoint && !(await ensureHostPermission(cfg.endpoint))) { distillOut = { error: 'permission to reach ' + (originPattern(cfg.endpoint) || cfg.endpoint) + ' denied' }; return; }
    manualStatus = 'Distilling via cloud LLM…';
    try {
      const card = await distillItem(last.text, { source: last.source, tier: last.tier, apiKey: cfg.apiKey, endpoint: cfg.endpoint || undefined, model: cfg.model || undefined });
      distillOut = { card }; manualStatus = 'Context card ready.';
    } catch (e) { distillOut = { error: String(e.message || e) }; manualStatus = ''; }
  }

  onMount(async () => {
    chrome.runtime.onMessage.addListener((msg) => { if (msg?.type === 'model:progress') applyProgress(msg); });
    const st = await getLocal({
      [KEYS.toggles]: [], [KEYS.apiKey]: '', [KEYS.endpoint]: '', [KEYS.model]: '', [KEYS.source]: 'notion',
      [KEYS.bridge]: '', [KEYS.bridgeToken]: '', [KEYS.mode]: '', [KEYS.googleClientId]: '', [KEYS.notionClientId]: '',
      [KEYS.googleEmail]: '', [KEYS.notionConnected]: false, [KEYS.notionWorkspace]: ''
    });
    cfg.toggles = (st[KEYS.toggles] || []).join(', ');
    cfg.apiKey = st[KEYS.apiKey] || ''; cfg.endpoint = st[KEYS.endpoint] || ''; cfg.model = st[KEYS.model] || '';
    cfg.source = st[KEYS.source] || 'notion'; cfg.bridge = st[KEYS.bridge] || ''; cfg.bridgeToken = st[KEYS.bridgeToken] || '';
    cfg.googleClientId = st[KEYS.googleClientId] || ''; cfg.notionClientId = st[KEYS.notionClientId] || '';
    try { redirectUri = REDIRECT(); } catch { /* identity perm */ }
    if (st[KEYS.googleEmail]) { googleOk = true; googleStatus = 'Connected as ' + st[KEYS.googleEmail]; }
    if (st[KEYS.notionConnected]) { notionOk = true; notionStatus = st[KEYS.notionWorkspace] ? 'Connected — ' + st[KEYS.notionWorkspace] : 'Connected'; }
    mode = st[KEYS.mode] || '';
    if (mode === 'local') offerModel();
    smartLoad();
  });
</script>

<main>
  <h1>CONTXT</h1>
  <p class="sub">Your private context, in every AI — crown jewels stay on-device.</p>

  <!-- ① Sources + ② Mode -->
  <div class="panel">
    <div class="hd">① Connect your sources</div>
    <div class="conn">
      <div class="who"><span class="ico">◈</span><div><div>Google — Gmail + Calendar</div><div class="st" class:on={googleOk}>{googleStatus}</div></div></div>
      <button class="ghost sm" onclick={connectGoogle}>Connect</button>
    </div>
    <div class="conn">
      <div class="who"><span class="ico">◈</span><div><div>Notion</div><div class="st" class:on={notionOk}>{notionStatus}</div></div></div>
      <button class="ghost sm" onclick={connectNotion}>Connect</button>
    </div>

    <div class="hd" style="margin-top:14px;">② Choose how Contxt runs</div>
    <div class="modes">
      <button class="m" class:active={mode === 'local'} onclick={() => setMode('local')}>
        <span class="t">🔒 On-device</span><span class="d">Private tier classified locally. ~570MB model once.</span>
      </button>
      <button class="m" class:active={mode === 'online'} onclick={() => setMode('online')}>
        <span class="t">☁️ Online only</span><span class="d">No model. Nothing private stored — all shared.</span>
      </button>
    </div>

    {#if mode === 'online'}
      <div class="modelwrap muted">☁️ Online mode — no model downloaded. Only shared context is stored.</div>
    {:else if model.status === 'prompt'}
      <div class="modelwrap">
        <button class="ghost" onclick={downloadModel}>⬇︎ Download on-device model (~570MB, once)</button>
        <div class="hint">Runs Gemma 3 270M in your browser via WebGPU. Cached after first download.</div>
      </div>
    {:else if model.status === 'downloading'}
      <div class="modelwrap">
        {#if model.pct != null}
          <div class="muted">Downloading model — {model.file} ({model.pct}%)</div>
          <div class="bar"><i style="width:{model.pct}%"></i></div>
        {:else}
          <div class="muted">Downloading on-device model — {model.file}… (~570MB, one-time)</div>
          <div class="bar indet"><i></i></div>
        {/if}
      </div>
    {:else if model.status === 'ready'}
      <div class="modelwrap muted">🔒 On-device model ready — private items classified locally. ✓</div>
    {:else if model.status === 'unavailable'}
      <div class="modelwrap muted">⚠️ WebGPU unavailable — using deterministic rules on-device. Private items still stay local.</div>
    {:else if model.status === 'error'}
      <div class="modelwrap muted">Model load failed: {model.msg} — rules fallback active.</div>
    {/if}
  </div>

  <!-- Context -->
  <div class="panel">
    <div class="hd">Your context <button class="ghost sm push" onclick={smartLoad}>↻ Refresh</button></div>
    {#if shared.length}
      {#each shared as c (c.source + c.title)}
        <div class="ctx"><div class="top"><span class="src">{@html SRC_LOGO[c.source] || ''}<span>{c.source}</span></span><span class="ttl">{c.title}</span></div>{#if c.sum}<div class="sum">{c.sum}</div>{/if}</div>
      {/each}
    {:else}
      <div class="muted">{ctxMsg}</div>
    {/if}
    {#if privCount || ctxSource}
      <div class="privline">🔒 <b>{privCount}</b> private item(s) kept on-device — never sent to any AI.{#if ctxSource === 'live'} <span class="muted">· live from your accounts</span>{:else if ctxSource === 'fixture'} <span class="muted">· offline demo data</span>{/if}{#if ctxErrors.length} <span class="muted">· {ctxErrors.join(' · ')}</span>{/if}</div>
    {/if}
  </div>

  <!-- Private (on-device) -->
  <div class="panel">
    <div class="hd">🔒 Kept on-device (private)</div>
    {#if priv.length}
      {#each priv as c (c.source + c.title)}
        <div class="ctx priv"><div class="top"><span class="src">{@html SRC_LOGO[c.source] || ''}<span>{c.source}</span></span><span class="ttl">{c.title}</span></div><div class="sum">kept on-device · flagged: <span class="cats">{(c.categories || []).join(', ') || 'private'}</span></div></div>
      {/each}
    {:else}
      <div class="muted">Nothing classified private yet.</div>
    {/if}
    <div class="hint">These never leave your device — not sent to any AI, not to the cloud.</div>
  </div>

  <!-- Manual (advanced) -->
  <details>
    <summary>＋ Add something manually (advanced)</summary>
    <div class="settings">
      <label>Item text
        <textarea bind:value={manualText} placeholder="Paste an email, note, or event to classify on-device…"></textarea>
      </label>
      <label>Source
        <select bind:value={cfg.source} onchange={() => persist(KEYS.source, cfg.source)}>
          <option value="notion">notion</option><option value="calendar">calendar</option><option value="gmail">gmail</option>
        </select>
      </label>
      <label>Force-private keywords (comma-separated)
        <input bind:value={cfg.toggles} onchange={() => persist(KEYS.toggles, parseToggles(cfg.toggles))} placeholder="e.g. standup, financials" />
      </label>
      <button class="btn-primary" onclick={classifyManual}>Classify (on-device)</button>
      <div class="status muted">{manualStatus}</div>
      {#if manualResult}
        {#if manualResult.ok === false}
          <div class="ctx">Error: {manualResult.error}</div>
        {:else}
          <div class="ctx">
            <span class="badge {manualResult.tier}">{manualResult.tier}</span>
            <div class="row"><span class="k">sensitivity:</span> {manualResult.sensitivity}</div>
            <div class="row"><span class="k">categories:</span> {(manualResult.categories || []).join(', ') || '—'}</div>
            <div class="row"><span class="k">reason:</span> {manualResult.reason || '—'}</div>
          </div>
          {#if manualResult.tier === 'PRIVATE'}
            <div class="row" style="color:var(--gold)">🔒 PRIVATE — kept on-device. Not sent to the cloud.</div>
          {:else}
            <button class="secondary" onclick={runDistill}>☁️ Distill to context card (cloud LLM)</button>
          {/if}
        {/if}
      {/if}
      {#if distillOut?.error}
        <div class="ctx">Distill error: {distillOut.error}</div>
      {:else if distillOut?.card}
        <div class="ctx"><span class="badge SHARED">CONTEXT CARD</span>
          <div class="row"><span class="k">title:</span> {distillOut.card.title}</div>
          <div class="row"><span class="k">summary:</span> {distillOut.card.summary ?? '—'}</div>
          <pre>{JSON.stringify(distillOut.card, null, 2)}</pre>
        </div>
      {/if}
    </div>
  </details>

  <details>
    <summary>☁️ Cloud LLM settings (Fireworks AI)</summary>
    <div class="settings">
      <label>API key<input type="password" bind:value={cfg.apiKey} onchange={() => persist(KEYS.apiKey, cfg.apiKey)} placeholder="Fireworks API key" /></label>
      <label>Endpoint (optional)<input bind:value={cfg.endpoint} onchange={() => persist(KEYS.endpoint, cfg.endpoint)} placeholder="blank = Fireworks; or a custom OpenAI-compatible URL" /></label>
      <label>Model (optional)<input bind:value={cfg.model} onchange={() => persist(KEYS.model, cfg.model)} placeholder="accounts/fireworks/models/gpt-oss-120b" /></label>
    </div>
  </details>

  <details>
    <summary>🔑 Connection setup (OAuth client IDs)</summary>
    <div class="settings">
      <label>Google OAuth client ID<input bind:value={cfg.googleClientId} onchange={() => persist(KEYS.googleClientId, cfg.googleClientId)} placeholder="xxxxx.apps.googleusercontent.com" /></label>
      <label>Notion OAuth client ID<input bind:value={cfg.notionClientId} onchange={() => persist(KEYS.notionClientId, cfg.notionClientId)} placeholder="Notion public integration client id" /></label>
      <div class="hint">Redirect URI to register: {redirectUri}</div>
      <label>Bridge URL (optional)<input bind:value={cfg.bridge} onchange={() => persist(KEYS.bridge, cfg.bridge)} placeholder="blank = http://127.0.0.1:8787" /></label>
      <label>Bridge token (optional)<input type="password" bind:value={cfg.bridgeToken} onchange={() => persist(KEYS.bridgeToken, cfg.bridgeToken)} placeholder="only if your bridge sets CONTXT_BRIDGE_TOKEN" /></label>
    </div>
  </details>

  <a class="site-link" href="https://blackx16.github.io/contxt/viewer" target="_blank" rel="noreferrer">
    ↗ Open your Contxt dashboard on the web
  </a>
</main>

<style>
  main { width: 384px; padding: 16px; font-size: 13px; line-height: 1.5; }
  h1 { font-size: 15px; margin: 0 0 2px; color: var(--champagne); letter-spacing: 0.06em; font-weight: 600; }
  .sub { color: var(--text-faint); font-size: 11px; margin: 0 0 14px; }
  .panel { border: 1px solid var(--rule); border-radius: var(--r-lg); padding: 12px; margin-top: 12px; background: var(--raised); }
  .hd { font-weight: 700; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--text-muted); margin-bottom: 8px; display: flex; align-items: center; gap: 6px; }
  .push { margin-left: auto; }
  button.sm { width: auto; margin: 0; padding: 5px 11px; font-size: 12px; }
  button { width: 100%; margin-top: 8px; padding: 9px; font-size: 13px; }
  label { display: block; font-weight: 600; margin: 10px 0 4px; color: var(--text-muted); font-size: 12px; }
  textarea, input, select { width: 100%; font: inherit; padding: 7px 9px; margin-top: 4px; color: var(--text); background: var(--graphite); border: 1px solid var(--rule); border-radius: var(--r-sm); }
  textarea { resize: vertical; min-height: 52px; }
  textarea:focus, input:focus, select:focus { outline: none; border-color: var(--rule-strong); }
  .conn { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin: 8px 0; }
  .who { display: flex; align-items: center; gap: 9px; }
  .ico { width: 18px; text-align: center; color: var(--gold); }
  .st { font-size: 11px; color: var(--text-faint); }
  .st.on { color: var(--patina-text); font-weight: 600; }
  .modes { display: flex; gap: 8px; margin-top: 6px; }
  .m { flex: 1; margin: 0; border: 1px solid var(--rule); border-radius: var(--r-md); padding: 9px; text-align: left; display: flex; flex-direction: column; gap: 3px; }
  .m.active { border-color: var(--rule-strong); background: var(--gold-soft); }
  .m .t { font-weight: 700; color: var(--champagne); font-size: 12px; }
  .m .d { color: var(--text-faint); font-size: 10px; line-height: 1.4; }
  .modelwrap { margin-top: 10px; font-size: 12px; }
  .bar { height: 7px; border-radius: var(--r-pill); background: var(--graphite-2); overflow: hidden; margin-top: 6px; }
  .bar > i { display: block; height: 100%; width: 0%; background: var(--gold); transition: width 0.2s; }
  .bar.indet > i { width: 40%; background: var(--patina); animation: indet 1.1s ease-in-out infinite; }
  @keyframes indet { 0% { margin-left: -40%; } 100% { margin-left: 100%; } }
  .muted { color: var(--text-faint); font-size: 11px; }
  .ctx { border: 1px solid var(--rule); border-radius: var(--r-md); padding: 9px 11px; margin-top: 8px; background: var(--graphite); }
  .ctx .top { display: flex; align-items: center; gap: 7px; }
  .src { display: inline-flex; align-items: center; gap: 4px; font-family: var(--font-mono); font-size: 10px; font-weight: 600; padding: 2px 7px 2px 4px; border-radius: var(--r-pill); background: var(--graphite-2); color: var(--text-muted); text-transform: uppercase; }
  .src :global(svg) { display: block; border-radius: 3px; }
  .ttl { font-weight: 600; font-size: 12px; color: var(--champagne); }
  .sum { color: var(--text-faint); font-size: 11px; margin-top: 4px; line-height: 1.45; }
  .ctx.priv { border-color: var(--rule-strong); background: var(--gold-soft); }
  .cats { color: var(--gold); font-family: var(--font-mono); font-size: 10px; }
  .privline { margin-top: 10px; font-size: 12px; color: var(--gold-rich); }
  .privline b { color: var(--gold); }
  .row { margin-top: 6px; font-size: 12px; } .k { color: var(--text-faint); }
  details { margin-top: 12px; } summary { cursor: pointer; font-weight: 600; font-size: 12px; color: var(--text-faint); }
  summary:hover { color: var(--gold); }
  pre { margin: 6px 0 0; padding: 9px; background: var(--lacquer-deep); border: 1px solid var(--rule); border-radius: var(--r-sm); font-size: 10px; white-space: pre-wrap; word-break: break-word; max-height: 160px; overflow: auto; color: var(--text-muted); }
  .hint { font-size: 10px; color: var(--text-faint); margin-top: 4px; }
  .status { min-height: 14px; margin-top: 8px; }
  .site-link { display: block; text-align: center; margin-top: 14px; padding: 8px; border: 1px solid var(--rule); border-radius: var(--r-sm); color: var(--gold); font-size: 11px; text-decoration: none; }
  .site-link:hover { border-color: var(--rule-strong); color: var(--gold-pale); background: var(--gold-soft); }
</style>
