/**
 * Key store for the Contxt private context key.
 *
 * Persistence order (most durable first):
 *   1. OPFS  — origin private file system, survives page reloads + restarts
 *   2. localStorage — fallback for browsers without OPFS
 *   3. In-memory only — if both are unavailable
 *
 * The key is NEVER sent to any server. The MCP server holds its own copy
 * (via CONTXT_PRIVATE_KEY in .env). For multi-device sync, use the QR
 * key-transfer flow (CHA-22) which uses ECDH X25519 to wrap the key.
 */

import { generateKey, exportKeyB64, importKeyB64 } from './crypto';

const LS_KEY = 'contxt.privateKey.v1';
const OPFS_FILENAME = 'contxt-private.key';

// Session state
let _key: CryptoKey | null = null;
let _keyB64: string | null = null;
let _initialized = false;

// ── OPFS helpers ──────────────────────────────────────────────────────────────

async function readOPFS(): Promise<string | null> {
	try {
		const root = await navigator.storage.getDirectory();
		const fh = await root.getFileHandle(OPFS_FILENAME, { create: false });
		const file = await fh.getFile();
		const text = await file.text();
		return text.trim() || null;
	} catch {
		return null;
	}
}

async function writeOPFS(b64: string): Promise<void> {
	try {
		const root = await navigator.storage.getDirectory();
		const fh = await root.getFileHandle(OPFS_FILENAME, { create: true });
		const writable = await fh.createWritable();
		await writable.write(b64);
		await writable.close();
	} catch {
		// OPFS unavailable — localStorage fallback is already set
	}
}

// ── public API ────────────────────────────────────────────────────────────────

/**
 * Initialize the key store. Safe to call multiple times (idempotent).
 * Generates a fresh key on first use and persists it locally.
 */
export async function init(): Promise<void> {
	if (_initialized) return;
	_initialized = true;

	const fromOPFS = await readOPFS();
	const fromLS =
		typeof localStorage !== 'undefined' ? (localStorage.getItem(LS_KEY) ?? null) : null;
	const b64 = fromOPFS ?? fromLS;

	if (b64) {
		_key = await importKeyB64(b64);
		_keyB64 = b64;
		// Mirror to OPFS if it wasn't there
		if (!fromOPFS) await writeOPFS(b64);
	} else {
		// First-time: generate and persist
		_key = await generateKey();
		_keyB64 = await exportKeyB64(_key);
		await writeOPFS(_keyB64);
		if (typeof localStorage !== 'undefined') {
			localStorage.setItem(LS_KEY, _keyB64);
		}
	}
}

/** Return the current AES-256-GCM key. Throws if init() has not been called. */
export function getKey(): CryptoKey {
	if (!_key) throw new Error('[keystore] not initialized — await init() first');
	return _key;
}

/** Return true if the key store has been initialized. */
export function isReady(): boolean {
	return _initialized && _key !== null;
}

/**
 * Export the raw key as base64url for display / QR code / manual copy.
 * The caller is responsible for not leaking this string to any server.
 */
export function exportForQR(): string {
	if (!_keyB64) throw new Error('[keystore] not initialized');
	return _keyB64;
}

/**
 * Import a key from a QR scan or manual paste. Replaces any existing key
 * and persists the new one.
 */
export async function importFromQR(b64: string): Promise<void> {
	_key = await importKeyB64(b64);
	_keyB64 = b64;
	await writeOPFS(b64);
	if (typeof localStorage !== 'undefined') {
		localStorage.setItem(LS_KEY, b64);
	}
}
