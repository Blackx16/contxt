/**
 * Web Crypto API helpers for Contxt client-side AES-256-GCM encryption.
 *
 * The PRIVATE card key lives only in the browser (OPFS + memory).
 * The server is a blind relay — it stores and forwards ciphertext without
 * ever holding the key.
 *
 * ECDH X25519 is included for the multi-device QR key-transfer flow (CHA-22).
 * For single-device storage, we use a raw AES-256-GCM key directly.
 *
 * No external libraries — Web Crypto API only. No libsignal / AGPL code.
 */

// ── base64url helpers ─────────────────────────────────────────────────────────

export function b64urlEncode(buf: ArrayBuffer | Uint8Array): string {
	const bytes = buf instanceof Uint8Array ? buf : new Uint8Array(buf);
	let binary = '';
	for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
	return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');
}

export function b64urlDecode(s: string): Uint8Array<ArrayBuffer> {
	const rem = s.length % 4;
	const padded = rem ? s + '='.repeat(4 - rem) : s;
	const binary = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
	// Allocate an explicit ArrayBuffer so the Uint8Array generic resolves to
	// Uint8Array<ArrayBuffer> (required by Web Crypto BufferSource in TS 6+).
	const buf = new ArrayBuffer(binary.length);
	const bytes = new Uint8Array(buf);
	for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
	return bytes;
}

// ── AES-256-GCM key generation / import / export ─────────────────────────────

export function generateKey(): Promise<CryptoKey> {
	return crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, [
		'encrypt',
		'decrypt'
	]);
}

export async function exportKeyB64(key: CryptoKey): Promise<string> {
	const raw = await crypto.subtle.exportKey('raw', key);
	return b64urlEncode(raw);
}

export async function importKeyB64(b64: string): Promise<CryptoKey> {
	return crypto.subtle.importKey(
		'raw',
		b64urlDecode(b64),
		{ name: 'AES-GCM', length: 256 },
		true,
		['encrypt', 'decrypt']
	);
}

// ── AES-256-GCM encrypt / decrypt ─────────────────────────────────────────────

export interface EncryptedPayload {
	ciphertext: string; // base64url
	iv: string; // base64url 96-bit nonce
}

/** Encrypt any JSON-serializable value. Returns base64url ciphertext + iv. */
export async function encryptPayload(payload: unknown, key: CryptoKey): Promise<EncryptedPayload> {
	const iv = crypto.getRandomValues(new Uint8Array(new ArrayBuffer(12))); // 96-bit nonce
	const encoded = new TextEncoder().encode(JSON.stringify(payload));
	const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, key, encoded);
	return {
		ciphertext: b64urlEncode(ct),
		iv: b64urlEncode(iv)
	};
}

/** Decrypt a base64url ciphertext+iv pair. Returns the original JSON payload. */
export async function decryptPayload<T = unknown>(
	payload: EncryptedPayload,
	key: CryptoKey
): Promise<T> {
	const ct = b64urlDecode(payload.ciphertext);
	const nonce = b64urlDecode(payload.iv);
	const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: nonce }, key, ct);
	return JSON.parse(new TextDecoder().decode(plain)) as T;
}

// ── ECDH X25519 — for multi-device QR key-transfer (CHA-22) ──────────────────

/** Generate an X25519 key pair (exportable, for key-agreement + QR transfer). */
export function generateECDHKeyPair(): Promise<CryptoKeyPair> {
	return crypto.subtle.generateKey({ name: 'X25519' }, true, ['deriveKey', 'deriveBits']);
}

export async function exportPublicKeyB64(key: CryptoKey): Promise<string> {
	const spki = await crypto.subtle.exportKey('spki', key);
	return b64urlEncode(spki);
}

export async function importPublicKeyB64(b64: string): Promise<CryptoKey> {
	return crypto.subtle.importKey('spki', b64urlDecode(b64), { name: 'X25519' }, true, []);
}

/**
 * Derive an AES-256-GCM key from an X25519 ECDH shared secret.
 * Used in the QR key-transfer flow: sender derives AES key from their private +
 * receiver's public, encrypts the storage key, receiver reverses.
 */
export function deriveAESKey(privateKey: CryptoKey, publicKey: CryptoKey): Promise<CryptoKey> {
	return crypto.subtle.deriveKey(
		{ name: 'X25519', public: publicKey },
		privateKey,
		{ name: 'AES-GCM', length: 256 },
		true,
		['encrypt', 'decrypt']
	);
}
