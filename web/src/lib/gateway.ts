// Crown-Jewels Gateway — browser override layer (CHA-24).
//
// This is the client-side twin of `gateway/rules.py`. The canonical gateway runs
// two passes at ingest: (1) deterministic guardrails, (2) Gemma nuance. The tier it
// lands is baked into each card (`card.tier`). What this module adds is the third
// input the ticket calls for: the user's own privacy policy, applied as HARD
// OVERRIDES on top of whatever the gateway decided.
//
// Contract (matches rules.py):
//   - GUARDRAIL_PATTERNS  ≡ rules.py `_PATTERNS`   — always-on safety floor.
//   - PRIVACY_CATEGORIES  bundle keywords into plain-language toggles. Their union
//     is the `private_keywords` list rules.py already accepts ("Populated from the
//     UI privacy toggles.").
//
// A toggle only ever TIGHTENS: an active category can force a SHARED item to
// PRIVATE, never the reverse. Turning it off reverts the item to the gateway's
// own decision. This is why crown jewels can never leak from a UI mistake.

import type { Tier } from './types';

export type PrivacyCategoryId = 'financials' | 'family' | 'clients' | 'health';

export interface PrivacyCategory {
	id: PrivacyCategoryId;
	/** Plain-language name a non-technical user understands at a glance. */
	label: string;
	/** One line describing what it keeps on-device. */
	blurb: string;
	icon: string;
	/** Whole-word keywords that trip this category. */
	keywords: string[];
	/** Structural patterns (mirrored from the gateway guardrails) this category also owns. */
	patterns: RegExp[];
}

// Always-on deterministic guardrails — identical to gateway/rules.py `_PATTERNS`.
// These force PRIVATE regardless of any toggle; they are the safety floor, not a
// user setting. Exported so the viewer can explain WHY a card was auto-protected.
export const GUARDRAIL_PATTERNS: Record<string, RegExp> = {
	money: /(?:₹|rs\.?|inr|usd|eur|gbp|\$|€|£)\s?\d[\d,.]*|\b\d[\d,.]*\s?(?:k|m|bn|dollars?|rupees?|euros?|pounds?|lakhs?|crores?)\b|\b(?:millions?|billions?|trillions?|lakhs?|crores?)\b/i,
	finance: /\b(?:revenue|sales|profit|turnover|salary|payroll|invoice|earnings|valuation|funding|acquisition|net\s?worth)\b/i,
	card: /\b(?:\d[ -]?){13,16}\b/,
	account: /\b(?:a\/c|acct|account)\b.*\d{4,}/i,
	phone: /\b(?:\+?91[- ]?)?[6-9]\d{9}\b/,
	health: /\b(?:diagnos|prescription|medical|blood\s?test|report)\b/i
};

// The toggle surface. Keyword sets are a superset of the extension's
// DEFAULT_PRIVATE_KEYWORDS (salary/loan/emi/family/school/client), distributed
// into categories a person recognises. Financials + Health also own the matching
// guardrail patterns so "never share money/health" is genuinely comprehensive.
export const PRIVACY_CATEGORIES: PrivacyCategory[] = [
	{
		id: 'financials',
		label: 'Money & finances',
		blurb: 'Salaries, loans, invoices, budgets, bank details',
		icon: '₹',
		keywords: [
			'salary', 'loan', 'emi', 'invoice', 'budget', 'expense', 'bank',
			'mortgage', 'payroll', 'revenue', 'net worth', 'bonus'
		],
		patterns: [GUARDRAIL_PATTERNS.money, GUARDRAIL_PATTERNS.finance, GUARDRAIL_PATTERNS.card, GUARDRAIL_PATTERNS.account]
	},
	{
		id: 'family',
		label: 'Family & home',
		blurb: 'Kids, school, family plans, anything about home',
		icon: '⌂',
		keywords: [
			'family', 'kids', 'child', 'children', 'school', 'spouse', 'wife',
			'husband', 'daughter', 'parents', 'home', 'anniversary'
		],
		patterns: []
	},
	{
		id: 'clients',
		label: 'Clients & deals',
		blurb: 'Client names, deals, contracts, customer work',
		icon: '⛨',
		keywords: [
			'client', 'customer', 'deal', 'contract', 'proposal', 'onboarding', 'vendor'
		],
		patterns: []
	},
	{
		id: 'health',
		label: 'Health',
		blurb: 'Appointments, diagnoses, prescriptions, reports',
		icon: '✚',
		keywords: ['doctor', 'clinic', 'appointment', 'therapy', 'pharmacy', 'vaccine'],
		patterns: [GUARDRAIL_PATTERNS.health]
	}
];

const CATEGORY_BY_ID = new Map(PRIVACY_CATEGORIES.map((c) => [c.id, c]));

function escapeRe(s: string): string {
	return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// One whole-word matcher per category, built once. Whole-word (not substring) so
// "son" can't match "person" and "client" can't match unrelated text.
const CATEGORY_KEYWORD_RE = new Map<PrivacyCategoryId, RegExp>(
	PRIVACY_CATEGORIES.map((c) => [
		c.id,
		new RegExp(`\\b(?:${c.keywords.map(escapeRe).join('|')})\\b`, 'i')
	])
);

/** The text the gateway sees for an item: title + summary + body + entity values. */
export function cardText(card: {
	title?: string | null;
	summary?: string | null;
	body?: string | null;
	entities?: { value: string }[];
}): string {
	return [
		card.title ?? '',
		card.summary ?? '',
		card.body ?? '',
		...(card.entities ?? []).map((e) => e.value)
	].join(' ');
}

/** Guardrail categories that fire on this text (always-on; mirrors rules.py). */
export function guardrailHits(text: string): string[] {
	return Object.entries(GUARDRAIL_PATTERNS)
		.filter(([, pat]) => pat.test(text))
		.map(([name]) => name);
}

/** Which of the ACTIVE toggle categories match this text. */
export function matchedCategories(text: string, activeIds: PrivacyCategoryId[]): PrivacyCategoryId[] {
	return activeIds.filter((id) => {
		const cat = CATEGORY_BY_ID.get(id);
		if (!cat) return false;
		if (CATEGORY_KEYWORD_RE.get(id)!.test(text)) return true;
		return cat.patterns.some((p) => p.test(text));
	});
}

export interface EffectiveTier {
	tier: Tier;
	/** True when a user toggle (not the base decision) is what forced PRIVATE. */
	forced: boolean;
	/** Active categories that forced this item private. */
	categories: PrivacyCategoryId[];
	/** Human-readable "why", for the card note. */
	reason: string;
}

/**
 * Apply the user's active privacy policy to an item's base tier.
 *
 * base === 'private'  → stays private (the gateway/guardrails already decided).
 * base === 'shared'   → forced private iff an active category matches; else shared.
 */
export function effectiveTier(
	base: Tier,
	text: string,
	activeIds: PrivacyCategoryId[]
): EffectiveTier {
	if (base === 'private') {
		return { tier: 'private', forced: false, categories: [], reason: '' };
	}
	const hit = matchedCategories(text, activeIds);
	if (hit.length > 0) {
		const labels = hit.map((id) => CATEGORY_BY_ID.get(id)!.label);
		const reason =
			labels.length === 1
				? `Held on-device by your “${labels[0]}” rule`
				: `Held on-device by your ${labels.map((l) => `“${l}”`).join(' + ')} rules`;
		return { tier: 'private', forced: true, categories: hit, reason };
	}
	return { tier: 'shared', forced: false, categories: [], reason: '' };
}

export function categoryLabel(id: PrivacyCategoryId): string {
	return CATEGORY_BY_ID.get(id)?.label ?? id;
}
