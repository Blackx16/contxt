// Contxt app state — connect-sources onboarding + card loading + client-side crypto.
//
// Crypto flow (CHA-19):
//   On initCrypto(), the keystore is initialized and each PRIVATE card's content
//   is encrypted in-browser using the local AES-256-GCM key. The viewer shows
//   PRIVATE cards as locked (no summary / body). The user decrypts them one at a
//   time by clicking "Decrypt locally" — which runs the actual AES-GCM decrypt
//   via Web Crypto API and stores the result in decryptedSecrets.
//
//   Crucially: the decrypted content shown in the viewer comes FROM the output of
//   crypto.subtle.decrypt(), not from reading the fixture JSON directly. This proves
//   the round-trip: encrypt → opaque ciphertext → local decrypt → readable text.

import type { ContextCard, Source } from './types';
import type { EncryptedPayload } from './crypto';
import { encryptPayload, decryptPayload } from './crypto';
import { init as initKeystore, getKey, isReady, exportForQR } from './keystore';
import cardsFixture from './fixtures/cards.json';

export type ConnStatus = 'idle' | 'connecting' | 'connected';

export interface SourceDef {
	id: Source;
	label: string;
	blurb: string;
	icon: string;
}

export const SOURCES: SourceDef[] = [
	{ id: 'gmail', label: 'Gmail', blurb: 'Emails, threads, receipts', icon: '✉️' },
	{ id: 'calendar', label: 'Calendar', blurb: 'Events, meetings, invites', icon: '📅' },
	{ id: 'notion', label: 'Notion', blurb: 'Docs, notes, wikis', icon: '📓' }
];

const CONN_STORAGE_KEY = 'contxt.connected.v1';

function loadPersisted(): Source[] {
	if (typeof localStorage === 'undefined') return [];
	try {
		const raw = localStorage.getItem(CONN_STORAGE_KEY);
		return raw ? (JSON.parse(raw) as Source[]) : [];
	} catch {
		return [];
	}
}

export const conn = $state<Record<Source, ConnStatus>>({
	gmail: 'idle',
	calendar: 'idle',
	notion: 'idle'
});

for (const s of loadPersisted()) {
	if (s in conn) conn[s] = 'connected';
}

function persistConn() {
	if (typeof localStorage === 'undefined') return;
	const connected = (Object.keys(conn) as Source[]).filter((s) => conn[s] === 'connected');
	localStorage.setItem(CONN_STORAGE_KEY, JSON.stringify(connected));
}

export function connectedSources(): Source[] {
	return (Object.keys(conn) as Source[]).filter((s) => conn[s] === 'connected');
}

export function anyConnected(): boolean {
	return connectedSources().length > 0;
}

export async function connectSource(id: Source): Promise<void> {
	if (conn[id] === 'connected') return;
	conn[id] = 'connecting';
	await new Promise((r) => setTimeout(r, 900));
	conn[id] = 'connected';
	persistConn();
}

export function disconnectSource(id: Source): void {
	conn[id] = 'idle';
	persistConn();
}

export function resetConnections(): void {
	for (const s of Object.keys(conn) as Source[]) conn[s] = 'idle';
	persistConn();
}

// ── crypto state (CHA-19) ─────────────────────────────────────────────────────

interface CardSecret {
	summary: string | null;
	body: string | null;
	entities: ContextCard['entities'];
}

// Browser-side encrypted blobs (simulates what the cloud SQLite store holds).
// Key: card id, Value: {ciphertext, iv} base64url — opaque without the local key.
const encryptedBlobs = $state<Record<string, EncryptedPayload>>({});

// Decrypted card content — populated by decryptCard(). Content comes from
// the output of crypto.subtle.decrypt(), not from reading fixture JSON directly.
const decryptedSecrets = $state<Record<string, CardSecret>>({});

// True once the keystore is ready and PRIVATE cards have been sealed in-browser.
export const cryptoReady = $state({ value: false });

/**
 * Initialize the keystore and encrypt all PRIVATE fixture cards in-browser.
 * Call from +layout.svelte or viewer onMount.
 */
export async function initCrypto(): Promise<void> {
	if (cryptoReady.value) return;
	await initKeystore();
	const key = getKey();

	for (const card of cardsFixture as ContextCard[]) {
		if (card.tier !== 'private' || card.id in encryptedBlobs) continue;
		const secret: CardSecret = {
			summary: card.summary,
			body: card.body,
			entities: card.entities as ContextCard['entities']
		};
		encryptedBlobs[card.id] = await encryptPayload(secret, key);
	}

	cryptoReady.value = true;
}

/**
 * Decrypt a PRIVATE card using the browser's local key.
 * The revealed content comes directly from crypto.subtle.decrypt() output.
 * After this call, loadCards() will return the card with its plaintext content.
 */
export async function decryptCard(cardId: string): Promise<void> {
	if (cardId in decryptedSecrets) return;
	const blob = encryptedBlobs[cardId];
	if (!blob) return;
	const key = getKey();
	// Actual AES-256-GCM decrypt — proves the round-trip works end-to-end.
	const secret = await decryptPayload<CardSecret>(blob, key);
	decryptedSecrets[cardId] = secret;
}

/** Lock a PRIVATE card — hides content until decryptCard() is called again. */
export function lockCard(cardId: string): void {
	delete decryptedSecrets[cardId];
}

/** True if a card's content has been decrypted this session. */
export function isDecrypted(cardId: string): boolean {
	return cardId in decryptedSecrets;
}

/** The ciphertext blob for a PRIVATE card (for display in the locked UI). */
export function getEncryptedBlob(cardId: string): EncryptedPayload | null {
	return encryptedBlobs[cardId] ?? null;
}

/** The base64url key for manual copy / QR (user sees this in key-sync dialog). */
export function getKeyForDisplay(): string {
	return isReady() ? exportForQR() : '';
}

// ── card loading ──────────────────────────────────────────────────────────────

export function loadCards(): ContextCard[] {
	const connected = new Set(connectedSources());
	return (cardsFixture as ContextCard[])
		.filter((c) => connected.has(c.source))
		.map((c): ContextCard => {
			if (c.tier === 'private' && cryptoReady.value) {
				const secret = decryptedSecrets[c.id];
				if (!secret) {
					// Locked: return card shell with no content
					return { ...c, summary: null, body: null, entities: [] };
				}
				// Revealed: content comes FROM the actual decrypt output (not fixture)
				return { ...c, summary: secret.summary, body: secret.body, entities: secret.entities };
			}
			return c;
		});
}

export function allCards(): ContextCard[] {
	return cardsFixture as ContextCard[];
}
