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

async function ensureOffscreen() {
  const has = await chrome.offscreen?.hasDocument?.();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN_URL,
    reasons: ['WORKERS'],
    justification:
      'Run the on-device Gemma 3 270M privacy classifier via WebGPU.',
  });
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
