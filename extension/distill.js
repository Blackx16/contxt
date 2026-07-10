/**
 * Cloud Gemma distillation — JS mirror of gateway/distill.py, for the popup.
 *
 * SHARED-tier items → rich context cards via cloud Gemma (Fireworks default,
 * or an AMD Dev Cloud endpoint). PRIVATE items are BLOCKED here — the same
 * belt-and-suspenders guard as the Python path, so a crown jewel can never be
 * sent to the cloud from the UI.
 *
 * The console logs mirror the Python server (`contxt:cloud_gemma` /
 * `contxt:cloud_gemma_ok`) so the AMD-hosted inference is capturable for the
 * "Best AMD-Hosted Gemma Project" prize submission.
 */

const FIREWORKS_URL = 'https://api.fireworks.ai/inference/v1/chat/completions';
const DEFAULT_MODEL = 'accounts/fireworks/models/gemma-3-27b-it';

const VALID_SOURCES = ['gmail', 'calendar', 'notion'];
const VALID_ENTITY_TYPES = [
  'person', 'org', 'date', 'money', 'location', 'email', 'phone', 'url', 'misc',
];

const DISTILL_SYSTEM = `You are a personal-context distiller. Given a raw personal data item (email, calendar event, or note), extract a structured context card for the Contxt MCP server. Output ONLY valid JSON — no markdown fences, no preamble.

Required schema:
{
  "title": "short descriptive title, max 80 chars",
  "summary": "1-2 sentence summary",
  "body": "optional longer detail, or null",
  "entities": [{"type": "person|org|date|money|location|email|phone|url|misc", "value": "string"}],
  "sensitivity_score": 0.0,
  "meta": {
    "identity": "who this is about",
    "current_projects": ["..."],
    "preferences": ["..."],
    "key_relationships": ["..."],
    "active_focus": "what needs immediate attention"
  }
}
sensitivity_score must be between 0.0 (public) and 1.0 (very sensitive).`;

// ── helpers ──────────────────────────────────────────────────────────────────

function extractJSON(raw) {
  let s = raw.trim();
  if (s.includes('```')) {
    const parts = s.split('```');
    s = parts.length > 2 ? parts[1].replace(/^json/i, '').trim() : parts.at(-1).trim();
  }
  const match = s.match(/\{[\s\S]*\}/);
  try {
    return JSON.parse(match ? match[0] : s);
  } catch {
    return null;
  }
}

function coerceEntities(raw) {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((e) => e && typeof e.value === 'string' && e.value.trim())
    .map((e) => ({
      type: VALID_ENTITY_TYPES.includes(e.type) ? e.type : 'misc',
      value: e.value.trim(),
    }));
}

function clampScore(v, def = 0.3) {
  const n = Number(v);
  return Number.isFinite(n) ? Math.min(1, Math.max(0, n)) : def;
}

/** Parse fuzzy model output into a schema-shaped context card. */
function toContextCard(data, source, text) {
  const d = data || {};
  return {
    id: `card_${crypto.randomUUID()}`,
    tier: 'shared',
    source,
    title: String(d.title || text.slice(0, 80) || 'Untitled').slice(0, 200),
    summary: typeof d.summary === 'string' ? d.summary : null,
    body: typeof d.body === 'string' ? d.body : null,
    entities: coerceEntities(d.entities),
    sensitivity_score: clampScore(d.sensitivity_score),
    created_at: new Date().toISOString(),
    embedding_ref: null,
    encryption: null,
    meta: d.meta && typeof d.meta === 'object' ? d.meta : null,
  };
}

// ── public API ────────────────────────────────────────────────────────────────

/**
 * Distill a SHARED item into a context card via cloud Gemma.
 *
 * @param {string} text  the raw item text
 * @param {object} opts  { source, tier, apiKey, endpoint, model }
 * @returns {Promise<object>} a schema-shaped context card
 * @throws if tier is PRIVATE, source is invalid, key missing, or the call fails
 */
export async function distillItem(text, opts = {}) {
  const { source = 'notion', tier = 'SHARED', apiKey, endpoint, model } = opts;

  // Privacy guard — mirrors gateway/distill.py. Crown jewels never leave.
  if (String(tier).toUpperCase() === 'PRIVATE') {
    throw new Error(
      'Refusing to distill a PRIVATE item — it stays on-device and is never ' +
        'sent to cloud Gemma.',
    );
  }
  if (!VALID_SOURCES.includes(source)) {
    throw new Error(`Unknown source "${source}" (expected ${VALID_SOURCES.join('/')}).`);
  }
  if (!apiKey) {
    throw new Error('No cloud API key set — paste your Fireworks/AMD key in the popup.');
  }

  const url = endpoint || FIREWORKS_URL;
  const chosenModel = model || DEFAULT_MODEL;

  const payload = {
    model: chosenModel,
    messages: [
      { role: 'system', content: DISTILL_SYSTEM },
      { role: 'user', content: `Source: ${source}\n\nItem:\n${text.slice(0, 2000)}` },
    ],
    max_tokens: 512,
    temperature: 0.1,
  };

  console.info('[contxt] cloud_gemma endpoint=%s model=%s', url, chosenModel);
  const resp = await fetch(url, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${apiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!resp.ok) {
    const detail = await resp.text().catch(() => '');
    throw new Error(`Cloud Gemma HTTP ${resp.status}: ${detail.slice(0, 200)}`);
  }

  const data = await resp.json();
  console.info('[contxt] cloud_gemma_ok id=%s usage=%o', data.id, data.usage);

  const content = data?.choices?.[0]?.message?.content ?? '';
  const parsed = extractJSON(content);
  return toContextCard(parsed, source, text);
}
