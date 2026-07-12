/**
 * MV3 service worker — Crown-Jewels Gateway relay.
 *
 * Spins up the offscreen document that runs Gemma 270M, then relays
 * classify requests to it, injecting the user's stored privacy-toggle state.
 *
 * Messages handled
 * ----------------
 *  { type: 'classify', text: string }
 *      → classify the text, returns the offscreen classification result.
 *
 *  { type: 'set:privacy', state: { privateKeywords: [], privateToggles: [] } }
 *      → persist updated privacy toggles (called from the extension popup/UI).
 *
 *  { type: 'get:privacy' }
 *      → return current privacy state (for the popup to read on open).
 */

const OFFSCREEN_URL = 'offscreen.html';

// The local HTTP bridge that fronts the MCP server's get_context / draft_reply
// (browsers can't speak MCP stdio). Overridable via chrome.storage.local.
const DEFAULT_BRIDGE = 'http://127.0.0.1:8787';

async function getBridgeConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get({ bridgeUrl: DEFAULT_BRIDGE, bridgeToken: '' }, (s) =>
      resolve({ url: s.bridgeUrl || DEFAULT_BRIDGE, token: s.bridgeToken || '' }),
    );
  });
}

// Guard against the MV3 race where two rapid classify messages both pass the
// hasDocument() check and both call createDocument → "Only a single offscreen
// document may be created". Concurrent callers await the same creation promise.
let _creating = null;

async function ensureOffscreen() {
  if (await chrome.offscreen?.hasDocument?.()) return;
  if (_creating) return _creating;

  _creating = chrome.offscreen
    .createDocument({
      url: OFFSCREEN_URL,
      reasons: ['WORKERS'],
      justification:
        'Run the on-device Gemma 3 270M privacy classifier via WebGPU.',
    })
    .catch((err) => {
      // Benign if another context created it first; re-throw anything else.
      if (!String(err).includes('single offscreen document')) throw err;
    })
    .finally(() => {
      _creating = null;
    });

  return _creating;
}

async function getPrivacyState() {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      { privateKeywords: [], privateToggles: [] },
      resolve,
    );
  });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  // ── ensure:offscreen ────────────────────────────────────────────────────────
  // The popup calls this so it can then message the offscreen doc directly,
  // keeping the ephemeral service worker out of the slow classify round-trip.
  if (msg?.type === 'ensure:offscreen') {
    ensureOffscreen()
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  // ── classify ──────────────────────────────────────────────────────────────
  if (msg?.type === 'classify') {
    Promise.all([ensureOffscreen(), getPrivacyState()])
      .then(([, privacyState]) =>
        chrome.runtime.sendMessage({
          type: 'classify:offscreen',
          text: msg.text,
          privateKeywords: privacyState.privateKeywords,
          privateToggles: privacyState.privateToggles,
        }),
      )
      .then(sendResponse)
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // async
  }

  // ── get:context ─────────────────────────────────────────────────────────────
  // The content script (on claude.ai / chatgpt.com / gemini.google.com) asks for
  // context to inject. We fetch the local bridge (get_context over HTTP). The
  // content script page is https and the bridge is http://127.0.0.1, so the fetch
  // MUST happen here in the extension origin, not in the page (mixed-content).
  // If the bridge is down, fall back to the bundled fixture so the demo always
  // injects something. Payload is SHARED-only + private counts either way.
  if (msg?.type === 'get:context') {
    const query = (msg.query || 'what am I working on').toString();
    // Resolution order — one source of truth with the popup:
    //   1) LIVE cards the popup pulled from the user's own Gmail/Calendar/Notion
    //      (cached in storage). 2) the local bridge (seeded store). 3) the bundled
    //      offline fixture. PRIVATE cards are never in any of these payloads.
    // The web dashboard asks for everything (full: true); the claude.ai injection
    // wants the capped list. Both also get the current connection status so the
    // popup and site mirror each other.
    const wantFull = msg.full === true;
    chrome.storage.local.get(
      {
        liveSharedCards: null,
        liveSharedCardsFull: null,
        livePrivateCount: 0,
        googleEmail: '',
        notionConnected: false,
        notionWorkspace: '',
      },
      (st) => {
        const connections = {
          google: !!st.googleEmail,
          googleEmail: st.googleEmail || '',
          notion: !!st.notionConnected,
          notionWorkspace: st.notionWorkspace || '',
        };
        const live = wantFull ? st.liveSharedCardsFull || st.liveSharedCards : st.liveSharedCards;
        if (Array.isArray(live) && live.length) {
          sendResponse({
            ok: true,
            source: 'live',
            query,
            cards: live,
            total: live.length,
            private_withheld: st.livePrivateCount || 0,
            private_total: st.livePrivateCount || 0,
            connections,
          });
          return;
        }
        getBridgeConfig()
          .then(({ url: base, token }) => {
            const url =
              base.replace(/\/$/, '') +
              '/get_context?query=' +
              encodeURIComponent(query) +
              (wantFull ? '&limit=50' : '&limit=6');
            const opts = token ? { headers: { 'X-Contxt-Token': token } } : undefined;
            return fetch(url, opts).then((r) => {
              if (!r.ok) throw new Error('bridge HTTP ' + r.status);
              return r.json();
            });
          })
          .then((data) => sendResponse({ ok: true, source: 'bridge', connections, ...data }))
          .catch(async (err) => {
            // Offline fallback — bundled fixture (SHARED-only, mirrors the bridge).
            try {
              const fx = await fetch(
                chrome.runtime.getURL('fixtures/get_context_response.json'),
              ).then((r) => r.json());
              sendResponse({ ok: true, source: 'fixture', note: String(err), connections, ...fx });
            } catch (e2) {
              sendResponse({ ok: false, error: 'bridge + fixture both failed: ' + err, connections });
            }
          });
      },
    );
    return true; // async
  }

  // ── set:privacy ───────────────────────────────────────────────────────────
  if (msg?.type === 'set:privacy') {
    chrome.storage.local.set(msg.state, () => sendResponse({ ok: true }));
    return true;
  }

  // ── get:privacy ───────────────────────────────────────────────────────────
  if (msg?.type === 'get:privacy') {
    getPrivacyState().then(sendResponse);
    return true;
  }
});
