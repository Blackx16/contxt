/**
 * Key-transfer envelope for the multi-device QR flow (CHA-22).
 *
 * The QR code carries this envelope — a versioned wrapper around the raw
 * AES-256-GCM key — out-of-band from device A to device B. It travels only
 * between the user's own devices (shown on one screen, scanned/pasted on the
 * other). It NEVER goes to the relay; the cloud only ever sees ciphertext.
 *
 * `parse` also accepts a bare base64url key so older exports (and hand-pasted
 * keys) keep working. Both paths validate that the key decodes to 32 bytes.
 */

import { b64urlDecode } from './crypto';

export const ENVELOPE_VERSION = 1;
const ALG = 'AES-256-GCM';
const KEY_BYTES = 32; // 256-bit

export interface KeyEnvelope {
	v: number;
	alg: string;
	k: string; // base64url raw key
}

function isValidKeyB64(b64: string): boolean {
	try {
		return b64urlDecode(b64).length === KEY_BYTES;
	} catch {
		return false;
	}
}

/** Wrap a base64url key into the versioned envelope string a QR will carry. */
export function buildKeyEnvelope(keyB64: string): string {
	if (!isValidKeyB64(keyB64)) {
		throw new Error('[keyenvelope] refusing to wrap a non-32-byte key');
	}
	const env: KeyEnvelope = { v: ENVELOPE_VERSION, alg: ALG, k: keyB64 };
	return JSON.stringify(env);
}

/**
 * Parse a scanned/pasted QR payload back to a base64url key.
 * Accepts either the JSON envelope or a bare base64url key. Throws on anything
 * that does not yield a valid 32-byte key.
 */
export function parseKeyEnvelope(payload: string): string {
	const text = payload.trim();
	if (!text) throw new Error('[keyenvelope] empty payload');

	// Envelope form
	if (text.startsWith('{')) {
		let env: Partial<KeyEnvelope>;
		try {
			env = JSON.parse(text) as Partial<KeyEnvelope>;
		} catch {
			throw new Error('[keyenvelope] malformed envelope JSON');
		}
		if (env.alg && env.alg !== ALG) {
			throw new Error(`[keyenvelope] unsupported alg: ${env.alg}`);
		}
		if (typeof env.k !== 'string' || !isValidKeyB64(env.k)) {
			throw new Error('[keyenvelope] envelope has no valid key');
		}
		return env.k;
	}

	// Bare base64url key (backward compatible)
	if (!isValidKeyB64(text)) {
		throw new Error('[keyenvelope] not a valid 32-byte base64url key');
	}
	return text;
}

/**
 * Short, non-secret fingerprint of a key for the UI — SHA-256 → first 4 bytes,
 * hex, grouped. Lets both device panels show the SAME id after a transfer to
 * confirm "yes, this is the same key" without ever displaying the key itself.
 */
export async function keyFingerprint(keyB64: string): Promise<string> {
	const digest = await crypto.subtle.digest('SHA-256', b64urlDecode(keyB64));
	const bytes = new Uint8Array(digest).slice(0, 4);
	const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
	return `${hex.slice(0, 4)} ${hex.slice(4)}`.toUpperCase();
}
