// Contxt app state — connect-sources onboarding + card loading.
// v1 is fixture-backed: "connecting" a source simulates ingest and unlocks its cards.
// Swap loadCards() for the real MCP get_context / pipeline output later.

import type { ContextCard, Source } from './types';
import cardsFixture from './fixtures/cards.json';

export type ConnStatus = 'idle' | 'connecting' | 'connected';

export interface SourceDef {
	id: Source;
	label: string;
	blurb: string;
	icon: string; // emoji stand-in until real brand marks are wired
}

export const SOURCES: SourceDef[] = [
	{ id: 'gmail', label: 'Gmail', blurb: 'Emails, threads, receipts', icon: '✉️' },
	{ id: 'calendar', label: 'Calendar', blurb: 'Events, meetings, invites', icon: '📅' },
	{ id: 'notion', label: 'Notion', blurb: 'Docs, notes, wikis', icon: '📓' }
];

const STORAGE_KEY = 'contxt.connected.v1';

function loadPersisted(): Source[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(STORAGE_KEY);
		return raw ? (JSON.parse(raw) as Source[]) : [];
	} catch {
		return [];
	}
}

/** Reactive map of source -> connection status. */
export const conn = $state<Record<Source, ConnStatus>>({
	gmail: 'idle',
	calendar: 'idle',
	notion: 'idle'
});

// Hydrate persisted connections on module load (client only).
for (const s of loadPersisted()) {
	if (s in conn) conn[s] = 'connected';
}

function persist() {
	if (typeof localStorage === 'undefined') return;
	const connected = (Object.keys(conn) as Source[]).filter((s) => conn[s] === 'connected');
	localStorage.setItem(STORAGE_KEY, JSON.stringify(connected));
}

export function connectedSources(): Source[] {
	return (Object.keys(conn) as Source[]).filter((s) => conn[s] === 'connected');
}

export function anyConnected(): boolean {
	return connectedSources().length > 0;
}

/** Simulate connecting + kicking off ingest for a source. */
export async function connectSource(id: Source): Promise<void> {
	if (conn[id] === 'connected') return;
	conn[id] = 'connecting';
	// Fake OAuth + first ingest pass. Real flow: OAuth redirect -> pipeline ingest.
	await new Promise((r) => setTimeout(r, 900));
	conn[id] = 'connected';
	persist();
}

export function disconnectSource(id: Source): void {
	conn[id] = 'idle';
	persist();
}

export function resetConnections(): void {
	for (const s of Object.keys(conn) as Source[]) conn[s] = 'idle';
	persist();
}

/** Cards visible in the viewer = fixtures whose source has been connected. */
export function loadCards(): ContextCard[] {
	const connected = new Set(connectedSources());
	return (cardsFixture as ContextCard[]).filter((c) => connected.has(c.source));
}

/** All fixture cards regardless of connection (used for empty-state hints/counts). */
export function allCards(): ContextCard[] {
	return cardsFixture as ContextCard[];
}
