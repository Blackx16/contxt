/**
 * Contxt site connector — bridges the Contxt website to the (unpublished,
 * locally-loaded) extension.
 *
 * The deployed site can't know an unpacked extension's ID, so we skip
 * externally_connectable. This content script runs on the Contxt site origin
 * and:
 *   1. announces the extension's presence to the page, and
 *   2. relays the page's context request to the background (get:context),
 *      posting the SHARED cards back.
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
    chrome.runtime.sendMessage(
      { type: 'get:context', query: msg.query || 'what am I working on' },
      (resp) => {
        const err = chrome.runtime.lastError;
        post('context', {
          reqId: msg.reqId,
          ok: !err && resp?.ok !== false,
          error: err ? err.message : resp?.error,
          cards: resp?.cards || [],
          private_total: resp?.private_total ?? resp?.private_withheld ?? 0,
          contextSource: resp?.source,
        });
      },
    );
    return;
  }
});
