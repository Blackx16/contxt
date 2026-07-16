/**
 * Contxt content script — the inject-into-any-AI bridge (CHA-26).
 *
 * Runs on Claude / ChatGPT / Gemini web. When the chat composer appears it:
 *   1. asks the background worker for context (get_context via the local HTTP
 *      bridge → the Contxt MCP server; falls back to a bundled fixture offline),
 *   2. auto-injects the SHARED context cards into the composer, and
 *   3. shows a small on-brand badge stating exactly what was shared with this
 *      AI and how many PRIVATE crown-jewel cards were kept on-device.
 *
 * The privacy guarantee is enforced upstream: the bridge's /get_context serves
 * SHARED cards only. PRIVATE plaintext never reaches this page. This script only
 * ever sees — and can only ever inject — what the user consented to share.
 *
 * Injection is non-destructive (prepended above any existing draft) and fires
 * once per page load. Click the badge to re-inject; ✕ dismisses it.
 */
(() => {
  'use strict';

  if (window.__contxtBridgeLoaded) return;
  window.__contxtBridgeLoaded = true;

  // ── Per-host composer detection ──────────────────────────────────────────────
  // Selectors are ordered most-specific → most-generic. UIs churn, so every host
  // ends with a resilient generic fallback (largest visible editable element).
  const HOSTS = [
    {
      id: 'claude',
      label: 'Claude',
      match: (h) => h.endsWith('claude.ai'),
      selectors: [
        'div[contenteditable="true"].ProseMirror',
        'fieldset div[contenteditable="true"]',
        'div[contenteditable="true"]',
      ],
    },
    {
      id: 'chatgpt',
      label: 'ChatGPT',
      match: (h) => h.endsWith('chatgpt.com') || h.endsWith('chat.openai.com'),
      selectors: [
        '#prompt-textarea',
        'div[contenteditable="true"]#prompt-textarea',
        'textarea[data-testid="prompt-textarea"]',
        'main form div[contenteditable="true"]',
        'main form textarea',
      ],
    },
    {
      id: 'gemini',
      label: 'Gemini',
      match: (h) => h.endsWith('gemini.google.com'),
      selectors: [
        'rich-textarea div.ql-editor[contenteditable="true"]',
        'div.ql-editor[contenteditable="true"]',
        'div[contenteditable="true"]',
      ],
    },
  ];

  const HOST = HOSTS.find((h) => h.match(location.hostname));
  if (!HOST) return; // not one of our AI surfaces

  // ── Utilities ────────────────────────────────────────────────────────────────

  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  const isVisible = (el) => {
    if (!el) return false;
    const r = el.getBoundingClientRect();
    if (r.width < 40 || r.height < 12) return false;
    const s = getComputedStyle(el);
    return s.visibility !== 'hidden' && s.display !== 'none';
  };

  function findComposer() {
    for (const sel of HOST.selectors) {
      const els = [...document.querySelectorAll(sel)].filter(isVisible);
      if (els.length) {
        // Prefer the largest visible match (the real composer, not a stray field).
        return els.sort(
          (a, b) =>
            b.getBoundingClientRect().width * b.getBoundingClientRect().height -
            a.getBoundingClientRect().width * a.getBoundingClientRect().height,
        )[0];
      }
    }
    // Last-ditch generic fallback across the whole page.
    const generic = [...document.querySelectorAll('textarea, [contenteditable="true"]')]
      .filter(isVisible);
    return generic.length ? generic[0] : null;
  }

  function waitForComposer(onReady, timeoutMs = 20000) {
    const found = findComposer();
    if (found) return onReady(found);

    const obs = new MutationObserver(() => {
      const el = findComposer();
      if (el) {
        obs.disconnect();
        onReady(el);
      }
    });
    obs.observe(document.documentElement, { childList: true, subtree: true });
    setTimeout(() => obs.disconnect(), timeoutMs);
  }

  // ── Fetch context (routed through the background worker) ──────────────────────
  // The composer page is https; the bridge is http://127.0.0.1 — a direct fetch
  // would be blocked as mixed content. The background service worker fetches it
  // (extension origin + host_permissions) and hands back the result.
  function fetchContext(query) {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ type: 'get:context', query }, (resp) => {
        if (chrome.runtime.lastError || !resp) {
          resolve({ ok: false, error: chrome.runtime.lastError?.message || 'no response' });
        } else {
          resolve(resp);
        }
      });
    });
  }

  // ── Build the injected context block ─────────────────────────────────────────

  const clip = (s, n) => {
    s = (s || '').replace(/\s+/g, ' ').trim();
    return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s;
  };

  function buildContextText(cards, meta) {
    const lines = ['My context (via Contxt — portable, privacy-first):'];
    for (const c of cards) {
      const desc = clip(c.summary || c.body || '', 180);
      lines.push(`• ${clip(c.title, 80)}${desc ? ' — ' + desc : ''}`);
    }
    const priv = meta.private_total ?? meta.private_withheld ?? 0;
    lines.push(
      `— Contxt shared ${cards.length} context card${cards.length === 1 ? '' : 's'} with this AI. ` +
        `${priv} private card${priv === 1 ? ' is' : 's are'} kept on-device and were never sent. —`,
    );
    return lines.join('\n') + '\n\n';
  }

  // ── Inject into the composer (non-destructive prepend) ────────────────────────

  function injectIntoComposer(el, text) {
    el.focus();

    // Plain <textarea> / <input>: use the native value setter so the host
    // framework (React/Svelte) actually registers the change.
    if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {
      const proto =
        el.tagName === 'TEXTAREA' ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
      const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
      const existing = el.value || '';
      const next = text + existing;
      setter ? setter.call(el, next) : (el.value = next);
      el.dispatchEvent(new Event('input', { bubbles: true }));
      return true;
    }

    // contenteditable (Claude ProseMirror, ChatGPT, Gemini Quill):
    // move the caret to the very start, then insertText so the editor builds its
    // own nodes and fires a real input event. insertText does NOT submit — Enter
    // submits via keydown, which we never dispatch.
    try {
      const sel = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(el);
      range.collapse(true); // caret at start
      sel.removeAllRanges();
      sel.addRange(range);
    } catch (_) {
      /* selection may be unavailable; insertText still targets the focused el */
    }

    let ok = false;
    try {
      ok = document.execCommand('insertText', false, text);
    } catch (_) {
      ok = false;
    }
    if (!ok) {
      // Fallback: prepend as text content and fire input.
      el.textContent = text + el.textContent;
      el.dispatchEvent(new InputEvent('input', { bubbles: true }));
    }
    return true;
  }

  // ── On-brand badge (Shadow DOM, Neo-Kinpaku) ──────────────────────────────────
  // gold = PRIVATE (crown jewels, on-device) · patina = SHARED (given to this AI).

  let badgeHost = null;

  function renderBadge(meta) {
    if (badgeHost) badgeHost.remove();
    badgeHost = document.createElement('div');
    badgeHost.id = 'contxt-badge-host';
    badgeHost.style.cssText =
      'position:fixed;right:16px;bottom:16px;z-index:2147483647;';
    const root = badgeHost.attachShadow({ mode: 'open' });

    const shared = meta.sharedCount ?? 0;
    const priv = meta.private_total ?? meta.private_withheld ?? 0;
    const src = meta.source === 'fixture' ? ' · demo data' : '';
    const errored = meta.error ? true : false;

    root.innerHTML = `
      <style>
        :host { all: initial; }
        .wrap {
          font: 12px/1.45 -apple-system, system-ui, "Albert Sans", sans-serif;
          color: #e0ded6;
          background: #0d0d0b;
          border: 1px solid rgba(230,226,214,0.14);
          border-radius: 8px;
          box-shadow: 0 6px 24px rgba(0,0,0,0.45);
          width: 288px;
          overflow: hidden;
        }
        .head {
          display: flex; align-items: center; gap: 8px;
          padding: 10px 12px; cursor: pointer;
          border-bottom: 1px solid rgba(230,226,214,0.10);
        }
        .mark { color: #e8b93a; font-weight: 700; letter-spacing: 0.02em; }
        .mark .dot { color: #45b0ab; }
        .spacer { flex: 1; }
        .x {
          color: #9a978c; cursor: pointer; font-size: 14px; line-height: 1;
          padding: 2px 4px; border-radius: 4px;
        }
        .x:hover { color: #e0ded6; background: rgba(230,226,214,0.08); }
        .body { padding: 10px 12px; }
        .row { display: flex; align-items: baseline; gap: 8px; margin: 3px 0; }
        .k { font: 10px/1.4 ui-monospace, monospace; text-transform: uppercase;
             letter-spacing: 0.06em; color: #9a978c; min-width: 96px; }
        .v { color: #e0ded6; }
        .v.shared { color: #45b0ab; font-weight: 600; }
        .v.gold   { color: #e8b93a; font-weight: 600; }
        .note { margin-top: 8px; color: #9a978c; font-size: 11px; }
        .err  { color: #d98b6a; }
        .re {
          margin-top: 10px; width: 100%; padding: 7px 8px;
          font: 600 12px/1 -apple-system, system-ui, sans-serif;
          color: #0d0d0b; background: #e8b93a;
          border: 0; border-radius: 6px; cursor: pointer;
        }
        .re:hover { filter: brightness(1.05); }
      </style>
      <div class="wrap">
        <div class="head" id="head" title="Contxt">
          <span class="mark">◆ Contxt<span class="dot"> ·</span></span>
          <span class="spacer"></span>
          <span class="x" id="close" title="Dismiss">✕</span>
        </div>
        <div class="body">
          ${
            errored
              ? `<div class="err">Couldn't reach Contxt (${esc(clip(meta.error, 60))}).</div>`
              : `
            <div class="row"><span class="k">→ this AI</span>
              <span class="v shared">${shared} shared card${shared === 1 ? '' : 's'} injected</span></div>
            <div class="row"><span class="k">🔒 on-device</span>
              <span class="v gold">${priv} private kept private</span></div>
            <div class="note">Injected into ${esc(HOST.label)}${src}. Crown jewels never left your device.</div>`
          }
          <button class="re" id="reinject">${errored ? 'Retry' : 'Re-inject'}</button>
        </div>
      </div>`;

    root.getElementById('close').addEventListener('click', (e) => {
      e.stopPropagation();
      badgeHost.remove();
      badgeHost = null;
    });
    const rerun = () => run(true);
    root.getElementById('reinject').addEventListener('click', rerun);
    root.getElementById('head').addEventListener('click', rerun);

    document.documentElement.appendChild(badgeHost);
  }

  // ── Orchestration ─────────────────────────────────────────────────────────────

  let injectedThisSession = false;

  async function run(force = false) {
    if (injectedThisSession && !force) return;

    const composer = findComposer();
    if (!composer) {
      renderBadge({ error: 'no chat composer found' });
      return;
    }

    // Auto-inject query: broad enough to surface the user's working context.
    const resp = await fetchContext('what am I working on');
    if (!resp || resp.ok === false) {
      renderBadge({ error: resp?.error || 'context fetch failed' });
      return;
    }

    const cards = Array.isArray(resp.cards) ? resp.cards : [];
    if (cards.length) {
      injectIntoComposer(composer, buildContextText(cards, resp));
    }
    injectedThisSession = true;

    renderBadge({
      sharedCount: cards.length,
      private_total: resp.private_total,
      private_withheld: resp.private_withheld,
      source: resp.source,
    });
  }

  // Kick off once the composer is present (SPAs mount it after load).
  waitForComposer(() => run(false));

  // Expose a manual trigger for demos / DevTools:  __contxtInject()
  window.__contxtInject = () => run(true);
})();
