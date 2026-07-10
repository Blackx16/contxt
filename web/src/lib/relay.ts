/**
 * Blind relay (CHA-22) — the browser twin of the cloud store's PRIVATE tier.
 *
 * This models the cloud in the multi-device demo. It holds nothing but
 * ciphertext records: {id, ciphertext, iv, created_at}. There is no field for a
 * key and no code path that accepts one — push() copies out only those four
 * fields and hard-rejects anything that smells like key material. That makes
 * "the cloud never held the key" a structural property you can read off the code,
 * not a promise. Device B pulls a record and decrypts locally with the key it got
 * over the QR channel — the relay is never in the loop for that.
 */

import type { EncryptedPayload } from './crypto';

export interface RelayRecord {
	id: string;
	ciphertext: string; // base64url
	iv: string; // base64url 96-bit nonce
	created_at: string; // ISO 8601
}

/** Property names we refuse to store — a tripwire against leaking key material. */
const FORBIDDEN_KEYS = ['key', 'k', 'secret', 'privatekey', 'private_key', 'aeskey'];

export class BlindRelay {
	#records = new Map<string, RelayRecord>();

	/**
	 * Store one ciphertext record. Only {id, ciphertext, iv, created_at} are kept;
	 * any extra property (especially anything key-shaped) is rejected outright.
	 */
	push(rec: RelayRecord): void {
		for (const prop of Object.keys(rec)) {
			if (FORBIDDEN_KEYS.includes(prop.toLowerCase())) {
				throw new Error(`[relay] refused: record carries forbidden field "${prop}"`);
			}
		}
		if (!rec.id || !rec.ciphertext || !rec.iv) {
			throw new Error('[relay] record must have id, ciphertext and iv');
		}
		// Copy out ONLY the blind fields — never trust the caller's object wholesale.
		this.#records.set(rec.id, {
			id: rec.id,
			ciphertext: rec.ciphertext,
			iv: rec.iv,
			created_at: rec.created_at
		});
	}

	/** Convenience: push from an {id} + EncryptedPayload produced by crypto.ts. */
	pushEncrypted(id: string, payload: EncryptedPayload, created_at: string): void {
		this.push({ id, ciphertext: payload.ciphertext, iv: payload.iv, created_at });
	}

	/** Fetch a ciphertext record — the only thing the relay can ever return. */
	pull(id: string): RelayRecord | null {
		const rec = this.#records.get(id);
		return rec ? { ...rec } : null;
	}

	list(): RelayRecord[] {
		return [...this.#records.values()].map((r) => ({ ...r }));
	}

	clear(): void {
		this.#records.clear();
	}

	/**
	 * Structural self-report for the demo's relay inspector. `holdsKey` is always
	 * false by construction — there is no key field to hold.
	 */
	inspect(): { count: number; fields: string[]; holdsKey: false } {
		return {
			count: this.#records.size,
			fields: ['id', 'ciphertext', 'iv', 'created_at'],
			holdsKey: false
		};
	}
}

/** Shared relay instance for the multi-device demo (both device panels use it). */
export const relay = new BlindRelay();
