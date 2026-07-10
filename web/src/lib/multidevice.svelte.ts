/**
 * Multi-device demo state (CHA-22).
 *
 * Drives the /multi-device money-shot: the SAME encrypted private card is sealed
 * on Device A, moved through a blind relay as ciphertext, and decrypted on Device
 * B after the key is handed over by QR. The relay never sees the key; Device B
 * cannot read the blob until the key arrives out-of-band.
 *
 * Reactive `md` holds serializable UI state. The two CryptoKey handles (A and B)
 * live in module-local vars — a CryptoKey is not reactive-serializable, and
 * keeping B's key entirely separate from A's is the whole point: Device B decrypts
 * with the key it was *given*, not with anything the keystore already had.
 */

import type { ContextCard, Source } from './types';
import type { EncryptedPayload } from './crypto';
import { encryptPayload, decryptPayload, importKeyB64 } from './crypto';
import { init as initKeystore, exportForQR } from './keystore';
import { buildKeyEnvelope, parseKeyEnvelope, keyFingerprint } from './keyenvelope';
import { qrSvg } from './qr';
import { relay, type RelayRecord } from './relay';
import cardsFixture from './fixtures/cards.json';

// The crown-jewel we demo with: the blood-test card (health → PRIVATE). It carries
// real plaintext in the web fixture, so Device B's decrypt reveals actual content.
const DEMO_CARD_ID = 'card_9f1c2a44-0004-4a10-8b21-000000000004';

interface CardSecret {
	summary: string | null;
	body: string | null;
	entities: ContextCard['entities'];
}

export const md = $state({
	ready: false,
	error: null as string | null,
	/** 0 idle · 1 sealed · 2 pushed/pulled · 3 key transferred · 4 decrypted */
	stage: 0,

	// flow flags
	sealed: false,
	pushed: false,
	pulled: false,
	transferred: false,
	decrypted: false,

	// the card under demo
	cardId: '',
	cardTitle: '',
	cardSource: '' as Source | '',

	// Device A
	keyA: '',
	fpA: '',
	envelope: '', // what the QR encodes
	qr: '', // rendered SVG markup
	cipherPreview: '', // first chars of the ciphertext, for the locked panel

	// relay contents (ciphertext-only, for the inspector)
	relayRecords: [] as RelayRecord[],

	// Device B
	pulledRecord: null as RelayRecord | null,
	keyB: '', // '' until the QR transfer lands
	fpB: '',
	revealed: null as CardSecret | null
});

// Non-reactive key handles + the plaintext secret Device A starts with.
let _keyACrypto: CryptoKey | null = null;
let _keyBCrypto: CryptoKey | null = null;
let _blobA: EncryptedPayload | null = null;
let _demoSecret: CardSecret | null = null;
let _createdAt = '';

/** Reset the flow (and the shared relay) but keep Device A's key + QR + card. */
export function reset(): void {
	relay.clear();
	_blobA = null;
	_keyBCrypto = null;
	md.sealed = false;
	md.pushed = false;
	md.pulled = false;
	md.transferred = false;
	md.decrypted = false;
	md.stage = 0;
	md.error = null;
	md.cipherPreview = '';
	md.relayRecords = [];
	md.pulledRecord = null;
	md.keyB = '';
	md.fpB = '';
	md.revealed = null;
}

/** Initialize Device A: load its key, build the QR envelope, pick the demo card. */
export async function initDemo(): Promise<void> {
	try {
		await initKeystore();
		md.keyA = exportForQR();
		_keyACrypto = await importKeyB64(md.keyA);
		md.fpA = await keyFingerprint(md.keyA);
		md.envelope = buildKeyEnvelope(md.keyA);
		md.qr = await qrSvg(md.envelope, { size: 200, ecc: 'M' });

		const card = (cardsFixture as ContextCard[]).find((c) => c.id === DEMO_CARD_ID);
		if (!card) throw new Error('demo card not found in fixtures');
		md.cardId = card.id;
		md.cardTitle = card.title;
		md.cardSource = card.source;
		_createdAt = card.created_at;
		_demoSecret = { summary: card.summary, body: card.body, entities: card.entities };

		reset();
		md.ready = true;
	} catch (e) {
		md.error = errMsg(e);
	}
}

/** Step 1 — Device A encrypts the card locally with its key. */
export async function sealOnA(): Promise<void> {
	if (!_keyACrypto || !_demoSecret) return;
	md.error = null;
	_blobA = await encryptPayload(_demoSecret, _keyACrypto);
	md.cipherPreview = _blobA.ciphertext.slice(0, 56);
	md.sealed = true;
	md.stage = Math.max(md.stage, 1);
}

/** Step 2 — Device A pushes the ciphertext record to the blind relay. */
export function pushToRelay(): void {
	if (!_blobA) return;
	relay.pushEncrypted(md.cardId, _blobA, _createdAt);
	md.pushed = true;
	md.relayRecords = relay.list();
	md.stage = Math.max(md.stage, 2);
}

/** Step 3 — Device B pulls the ciphertext record (still unreadable without the key). */
export function pullOnB(): void {
	md.pulledRecord = relay.pull(md.cardId);
	md.pulled = md.pulledRecord !== null;
	md.stage = Math.max(md.stage, 2);
}

/**
 * Step 4 — the QR key transfer. `payload` is the scanned/pasted QR content; when
 * omitted we use Device A's own envelope (the single-screen "tap to scan" path).
 */
export async function transferKey(payload?: string): Promise<void> {
	md.error = null;
	try {
		const raw = parseKeyEnvelope(payload ?? md.envelope);
		_keyBCrypto = await importKeyB64(raw);
		md.keyB = raw;
		md.fpB = await keyFingerprint(raw);
		md.transferred = true;
		md.stage = Math.max(md.stage, 3);
	} catch (e) {
		md.error = 'Key transfer failed — ' + errMsg(e);
	}
}

/** Step 5 — Device B decrypts the pulled ciphertext with the transferred key. */
export async function decryptOnB(): Promise<void> {
	md.error = null;
	if (!md.pulledRecord) {
		md.error = 'Device B has no ciphertext yet — pull it from the relay first.';
		return;
	}
	if (!_keyBCrypto) {
		// The instructive failure: ciphertext alone is useless without the key.
		md.error = 'Device B has no key yet — the relay only carries ciphertext. Transfer the key via QR.';
		return;
	}
	try {
		md.revealed = await decryptPayload<CardSecret>(md.pulledRecord as EncryptedPayload, _keyBCrypto);
		md.decrypted = true;
		md.stage = 4;
	} catch (e) {
		md.error = 'Decrypt rejected (wrong key or tampered ciphertext) — ' + errMsg(e);
	}
}

function errMsg(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}
