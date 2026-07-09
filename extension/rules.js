/**
 * Deterministic privacy classifier — JS port of gateway/rules.py.
 *
 * Runs as pass 1 in the offscreen classifier (before Gemma 270M).
 * Any hit here forces PRIVATE unconditionally — a model misjudgment
 * can never leak a crown jewel (belt-and-suspenders).
 */

const PATTERNS = {
  money:   /(?:₹|rs\.?|inr|\$)\s?\d[\d,]*/i,
  card:    /\b(?:\d[ -]?){13,16}\b/,
  account: /\b(?:a\/c|acct|account)\b.*\d{4,}/i,
  phone:   /\b(?:\+?91[- ]?)?[6-9]\d{9}\b/,
  health:  /\b(?:diagnos|prescription|medical|blood\s?test|report)\b/i,
};

export const DEFAULT_PRIVATE_KEYWORDS = [
  'salary', 'loan', 'emi', 'family', 'school', 'client',
];

/**
 * Return the category names that force this text PRIVATE.
 * @param {string} text
 * @param {string[]} privateKeywords - user-configured extra keywords
 * @returns {string[]}
 */
export function ruleHits(text, privateKeywords = DEFAULT_PRIVATE_KEYWORDS) {
  const hits = [];
  for (const [name, pat] of Object.entries(PATTERNS)) {
    if (pat.test(text)) hits.push(name);
  }
  const lower = (text || '').toLowerCase();
  for (const kw of privateKeywords) {
    if (lower.includes(kw.toLowerCase())) hits.push(`kw:${kw}`);
  }
  return hits;
}

/**
 * Full deterministic classification — used when WebGPU / Gemma is unavailable.
 * @param {string} text
 * @param {string[]} privateKeywords
 * @returns {{ tier: 'PRIVATE'|'SHARED', sensitivity: number, categories: string[], reason: string }}
 */
export function classifyFallback(text, privateKeywords = DEFAULT_PRIVATE_KEYWORDS) {
  const hits = ruleHits(text, privateKeywords);
  if (hits.length > 0) {
    return {
      tier: 'PRIVATE',
      sensitivity: 1.0,
      categories: hits,
      reason: 'matched deterministic rule(s)',
    };
  }
  return {
    tier: 'SHARED',
    sensitivity: 0.1,
    categories: [],
    reason: 'no rule hit (deterministic fallback)',
  };
}
