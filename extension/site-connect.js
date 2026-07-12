/**
 * Contxt site connector — bridges the Contxt website to the (unpublished,
 * locally-loaded) extension.
 *
 * The deployed site can't know an unpacked extension's ID, so we skip
 * externally_connectable. This content script runs on the Contxt site origin
 * and:
 *   1. announces the extension's presence to the page,
 *   2. relays the page's context request to the background (get:context, FULL
 *      list + connection status), and
 *   3. pushes a fresh snapshot whenever the popup's storage changes, so the
 *      site and the extension stay in sync in real time.
 *
 * Transport is window.postMessage with a tagged envelope. PRIVATE data never
 * crosses this bridge — get:context returns SHARED-only cards plus a count.
 */
const TAG_IN = 'contxt-web'; // page → extension
const TAG_OUT = 'contxt-extension'; // extension → page
const VERSION = chrome.runtime.getManifest().version;

function post(type, payload = {}) {
  window.postMessage({ source: TAG_OUT, type, version: VERSION, ...payload }, window.location.origin);
}

// Fetch the full SHARED context + connection status and post it to the page.
// reqId matches a page request; reqId 0 is an unsolicited real-time push.
function fetchAndPost(reqId) {
  chrome.runtime.sendMessage(
    { type: 'get:context', query: 'what am I working on', full: true },
    (resp) => {
      const err = chrome.runtime.lastError;
      post('context', {
        reqId,
        ok: !err && resp?.ok !== false,
        error: err ? err.message : resp?.error,
        cards: resp?.cards || [],
        private_total: resp?.private_total ?? resp?.private_withheld ?? 0,
        contextSource: resp?.source,
        connections: resp?.connections || null,
      });
    },
  );
}

// Announce on load; the page may also ping (handles the load-order race).
post('present');

window.addEventListener('message', (event) => {
  if (event.source !== window) return;
  const msg = event.data;
  if (!msg || msg.source !== TAG_IN) return;
  if (msg.type === 'ping') {
    post('pong', { reqId: msg.reqId });
    return;
  }
  if (msg.type === 'get:context') {
    fetchAndPost(msg.reqId);
    return;
  }
});

// Real-time sync: when the popup connects/disconnects a source or re-pulls, its
// storage changes → push a fresh context + connections snapshot to the page.
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'local') return;
  const keys = [
    'liveSharedCardsFull', 'liveSharedCards', 'googleEmail',
    'notionConnected', 'notionWorkspace', 'livePrivateCount',
  ];
  if (keys.some((k) => k in changes)) fetchAndPost(0);
});
