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

const OFFSCREEN_URL = "offscreen.html";

// ── Local defaults (API keys, OAuth client IDs) ────────────────────────────
// Loaded from local-config.js (gitignored). Sets storage values only if not
// already set, so a user-entered value always takes precedence. The try/catch
// means the extension works fine even if the file doesn't exist.
(async () => {
  try {
    const { LOCAL_DEFAULTS } = await import("./local-config.js");
    chrome.storage.local.get(Object.keys(LOCAL_DEFAULTS), (existing) => {
      const toSet = {};
      for (const [k, v] of Object.entries(LOCAL_DEFAULTS)) {
        if (!existing[k] && v) toSet[k] = v;
      }
      if (Object.keys(toSet).length) chrome.storage.local.set(toSet);
    });
  } catch {
    /* local-config.js not present — no defaults injected */
  }
})();

// The local HTTP bridge that fronts the MCP server's get_context / draft_reply
// (browsers can't speak MCP stdio). Overridable via chrome.storage.local.
const DEFAULT_BRIDGE = "http://127.0.0.1:8787";

async function getBridgeConfig() {
  return new Promise((resolve) => {
    chrome.storage.local.get(
      { bridgeUrl: DEFAULT_BRIDGE, bridgeToken: "" },
      (s) =>
        resolve({
          url: s.bridgeUrl || DEFAULT_BRIDGE,
          token: s.bridgeToken || "",
        }),
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
      reasons: ["WORKERS"],
      justification:
        "Run the on-device Gemma 3 270M privacy classifier via WASM.",
    })
    .catch((err) => {
      // Benign if another context created it first; re-throw anything else.
      if (!String(err).includes("single offscreen document")) throw err;
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

// ── Live on-device tiering + privacy policy (website parity) ──────────────────
// Single source of truth for LIVE mode: the popup stores the raw pulled items
// (`liveItems`, extension-only) and this worker decides SHARED vs PRIVATE from
// them + the user's `livePolicy`. PRIVATE bodies are SEALED (AES-256-GCM) before
// they cross the bridge to the site — plaintext never leaves the extension.

// Always-on guardrails — mirror gateway/rules.py `_PATTERNS`. A hit forces
// PRIVATE regardless of any toggle (non-negotiable safety floor).
const GUARD = {
  money:
    /(?:₹|rs\.?|inr|usd|eur|gbp|\$|€|£)\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:k|m|bn|dollars?|rupees?|euros?|pounds?|lakhs?|crores?)\b|\b(?:millions?|billions?|trillions?|lakhs?|crores?)\b/i,
  finance:
    /\b(?:revenue|sales|profit|turnover|salary|payroll|invoice|earnings|valuation|funding|acquisition|net\s?worth)\b/i,
  card: /\b(?:\d[ -]?){13,16}\b/,
  account: /\b(?:a\/c|acct|account)\b.*\d{4,}/i,
  phone: /\b(?:\+?91[- ]?)?[6-9]\d{9}\b/,
  health: /\b(?:diagnos|prescription|medical|blood\s?test|report)\b/i,
};
const GUARD_LABEL = {
  money: "Money & finances",
  finance: "Money & finances",
  card: "Money & finances",
  account: "Money & finances",
  phone: "Contact number",
  health: "Health",
};

// Plain-language toggle categories — MUST match web/src/lib/gateway.ts ids so the
// site can render its labels/icons against this state.
const LIVE_CATEGORIES = [
  {
    id: "financials",
    label: "Money & finances",
    keywords: [
      "salary",
      "loan",
      "emi",
      "invoice",
      "budget",
      "expense",
      "bank",
      "mortgage",
      "payroll",
      "revenue",
      "net worth",
      "bonus",
    ],
    patterns: [GUARD.money, GUARD.finance, GUARD.card, GUARD.account],
  },
  {
    id: "family",
    label: "Family & home",
    keywords: [
      "family",
      "kids",
      "child",
      "children",
      "school",
      "spouse",
      "wife",
      "husband",
      "daughter",
      "parents",
      "home",
      "anniversary",
    ],
    patterns: [],
  },
  {
    id: "clients",
    label: "Clients & deals",
    keywords: [
      "client",
      "customer",
      "deal",
      "contract",
      "proposal",
      "onboarding",
      "vendor",
    ],
    patterns: [],
  },
  {
    id: "health",
    label: "Health",
    keywords: [
      "doctor",
      "clinic",
      "appointment",
      "therapy",
      "pharmacy",
      "vaccine",
    ],
    patterns: [GUARD.health],
  },
];
const _esc = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const CAT_KW_RE = Object.fromEntries(
  LIVE_CATEGORIES.map((c) => [
    c.id,
    new RegExp(`\\b(?:${c.keywords.map(_esc).join("|")})\\b`, "i"),
  ]),
);
const CAT_BY_ID = Object.fromEntries(LIVE_CATEGORIES.map((c) => [c.id, c]));
const DEFAULT_LIVE_POLICY = Object.fromEntries(
  LIVE_CATEGORIES.map((c) => [c.id, true]),
);

function catMatches(id, text) {
  const c = CAT_BY_ID[id];
  if (!c) return false;
  return CAT_KW_RE[id].test(text) || c.patterns.some((p) => p.test(text));
}

function heldReason(labels) {
  const q = labels.map((l) => `“${l}”`);
  return labels.length === 1
    ? `Held on-device by your ${q[0]} rule`
    : `Held on-device by your ${q.join(" + ")} rules`;
}

// Decide a single item's live tier. Guardrail hit → PRIVATE (not toggleable).
// Else an ACTIVE category match → PRIVATE (toggle-forced). Else SHARED.
function tierItem(text, activeIds) {
  const t = text == null ? "" : String(text);
  const gHits = Object.keys(GUARD).filter((k) => GUARD[k].test(t));
  if (gHits.length) {
    const labels = [...new Set(gHits.map((g) => GUARD_LABEL[g]))];
    return {
      tier: "private",
      forced: false,
      categories: gHits,
      labels,
      reason: heldReason(labels),
    };
  }
  const hits = activeIds.filter((id) => catMatches(id, t));
  if (hits.length) {
    const labels = hits.map((id) => CAT_BY_ID[id].label);
    return {
      tier: "private",
      forced: true,
      categories: hits,
      labels,
      reason: heldReason(labels),
    };
  }
  return {
    tier: "shared",
    forced: false,
    categories: [],
    labels: [],
    reason: "",
  };
}

const _clip = (s, n = 220) => {
  const x = (s == null ? "" : String(s)).replace(/\s+/g, " ").trim();
  return x.length > n ? x.slice(0, n - 1) + "…" : x;
};
const _b64 = (u8) => btoa(String.fromCharCode(...u8));

async function getSealKey() {
  const { liveSealKey } = await chrome.storage.local.get({ liveSealKey: "" });
  let raw;
  if (liveSealKey) {
    raw = Uint8Array.from(atob(liveSealKey), (c) => c.charCodeAt(0));
  } else {
    raw = crypto.getRandomValues(new Uint8Array(32));
    await chrome.storage.local.set({ liveSealKey: _b64(raw) });
  }
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt"]);
}

// Real AES-256-GCM seal so the site shows an authentic ciphertext blob. The key
// never leaves the extension, so the site cannot decrypt — locked display only.
async function sealText(text) {
  try {
    const key = await getSealKey();
    const iv = crypto.getRandomValues(new Uint8Array(12));
    const ct = new Uint8Array(
      await crypto.subtle.encrypt(
        { name: "AES-GCM", iv },
        key,
        new TextEncoder().encode(text || ""),
      ),
    );
    return { alg: "AES-256-GCM", ct: _b64(ct), iv: _b64(iv) };
  } catch {
    return { alg: "AES-256-GCM", ct: "", iv: "" };
  }
}

async function getLivePolicy() {
  const { livePolicy } = await chrome.storage.local.get({ livePolicy: null });
  return {
    ...DEFAULT_LIVE_POLICY,
    ...(livePolicy && typeof livePolicy === "object" ? livePolicy : {}),
  };
}

// Build the full LIVE snapshot from stored raw items + the current policy.
// Returns SHARED cards (plaintext summaries), PRIVATE cards (SEALED bodies +
// title + which rule held them), the policy state, and per-category counts.
async function computeLiveSnapshot(wantFull) {
  const { liveItems } = await chrome.storage.local.get({ liveItems: null });
  if (!Array.isArray(liveItems) || !liveItems.length) return null;
  const policy = await getLivePolicy();
  const activeIds = LIVE_CATEGORIES.map((c) => c.id).filter((id) => policy[id]);

  const shared = [];
  let privCount = 0;
  let heldTotal = 0;
  const categoryCounts = Object.fromEntries(
    LIVE_CATEGORIES.map((c) => [c.id, 0]),
  );

  for (const it of liveItems) {
    const text = it.text || it.summary || "";
    for (const c of LIVE_CATEGORIES)
      if (catMatches(c.id, text)) categoryCounts[c.id] += 1;
    const d = tierItem(text, activeIds);
    if (d.tier === "shared") {
      shared.push({
        tier: "shared",
        source: it.source,
        title: it.title,
        summary: _clip(it.summary || it.text),
      });
    } else {
      // PRIVATE items are NEVER sent to the site — only a count + which rules held
      // them (via categoryCounts). Their titles/bodies stay in the extension.
      privCount += 1;
      if (d.forced) heldTotal += 1;
    }
  }

  const sharedOut = wantFull ? shared : shared.slice(0, 6);
  return {
    shared: sharedOut,
    cards: sharedOut, // back-compat name
    privateCards: [], // never expose private card content to the web page
    private_total: privCount,
    private_withheld: privCount,
    heldTotal,
    total: shared.length,
    policy,
    categoryCounts,
  };
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  // ── ensure:offscreen ────────────────────────────────────────────────────────
  // The popup calls this so it can then message the offscreen doc directly,
  // keeping the ephemeral service worker out of the slow classify round-trip.
  if (msg?.type === "ensure:offscreen") {
    ensureOffscreen()
      .then(() => sendResponse({ ok: true }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  // ── classify ──────────────────────────────────────────────────────────────
  if (msg?.type === "classify") {
    Promise.all([ensureOffscreen(), getPrivacyState()])
      .then(([, privacyState]) =>
        chrome.runtime.sendMessage({
          type: "classify:offscreen",
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
  if (msg?.type === "get:context") {
    const query = (msg.query || "what am I working on").toString();
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
        liveItems: null,
        liveSharedCards: null,
        liveSharedCardsFull: null,
        livePrivateCount: 0,
        googleEmail: "",
        notionConnected: false,
        notionWorkspace: "",
      },
      async (st) => {
        const connections = {
          google: !!st.googleEmail,
          googleEmail: st.googleEmail || "",
          notion: !!st.notionConnected,
          notionWorkspace: st.notionWorkspace || "",
        };
        // Preferred path: recompute the split from raw items + current policy, so
        // toggling a rule re-tiers live (and changes what gets injected).
        if (Array.isArray(st.liveItems) && st.liveItems.length) {
          const snap = await computeLiveSnapshot(wantFull);
          if (snap) {
            sendResponse({
              ok: true,
              source: "live",
              query,
              connections,
              ...snap,
            });
            return;
          }
        }
        // Legacy path: pre-split cards the popup cached (no policy re-tiering).
        const live = wantFull
          ? st.liveSharedCardsFull || st.liveSharedCards
          : st.liveSharedCards;
        if (Array.isArray(live) && live.length) {
          sendResponse({
            ok: true,
            source: "live",
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
              base.replace(/\/$/, "") +
              "/get_context?query=" +
              encodeURIComponent(query) +
              (wantFull ? "&limit=50" : "&limit=6");
            const opts = token
              ? { headers: { "X-Contxt-Token": token } }
              : undefined;
            return fetch(url, opts).then((r) => {
              if (!r.ok) throw new Error("bridge HTTP " + r.status);
              return r.json();
            });
          })
          .then((data) =>
            sendResponse({ ok: true, source: "bridge", connections, ...data }),
          )
          .catch(async (err) => {
            // Offline fallback — bundled fixture (SHARED-only, mirrors the bridge).
            try {
              const fx = await fetch(
                chrome.runtime.getURL("fixtures/get_context_response.json"),
              ).then((r) => r.json());
              sendResponse({
                ok: true,
                source: "fixture",
                note: String(err),
                connections,
                ...fx,
              });
            } catch (e2) {
              sendResponse({
                ok: false,
                error: "bridge + fixture both failed: " + err,
                connections,
              });
            }
          });
      },
    );
    return true; // async
  }

  // ── set:privacy ───────────────────────────────────────────────────────────
  if (msg?.type === "set:privacy") {
    chrome.storage.local.set(msg.state, () => sendResponse({ ok: true }));
    return true;
  }

  // ── set:live:policy ─────────────────────────────────────────────────────────
  // The website's privacy toggles call this. Persisting livePolicy re-tiers every
  // LIVE item on the next get:context and (via storage.onChanged) pushes a fresh
  // snapshot to the site in real time.
  if (msg?.type === "set:live:policy") {
    getLivePolicy().then((cur) => {
      const next =
        msg.policy && typeof msg.policy === "object"
          ? { ...cur, ...msg.policy }
          : { ...cur, [msg.id]: !!msg.on };
      chrome.storage.local.set({ livePolicy: next }, () =>
        sendResponse({ ok: true, policy: next }),
      );
    });
    return true;
  }

  // ── get:live:policy ─────────────────────────────────────────────────────────
  if (msg?.type === "get:live:policy") {
    getLivePolicy().then((policy) => sendResponse({ ok: true, policy }));
    return true;
  }

  // ── get:privacy ───────────────────────────────────────────────────────────
  if (msg?.type === "get:privacy") {
    getPrivacyState().then(sendResponse);
    return true;
  }
});
