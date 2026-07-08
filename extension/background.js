// MV3 service worker. Spins up the offscreen document that runs the local
// Gemma model, and relays classify requests to it.
const OFFSCREEN = 'offscreen.html';

async function ensureOffscreen() {
  const has = await chrome.offscreen?.hasDocument?.();
  if (has) return;
  await chrome.offscreen.createDocument({
    url: OFFSCREEN,
    reasons: ['WORKERS'],
    justification: 'Run the on-device Gemma privacy classifier (WebGPU).'
  });
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg?.type === 'classify') {
    ensureOffscreen()
      .then(() => chrome.runtime.sendMessage({ type: 'classify:offscreen', text: msg.text }))
      .then(sendResponse);
    return true; // async
  }
});
