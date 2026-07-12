/**
 * Talks to the (locally-loaded) Contxt browser extension.
 *
 * The extension injects a content script (site-connect.js) on this origin which
 * relays get:context from the background. We detect it by ping/pong over
 * window.postMessage — no extension ID needed, so it works for the unpacked/dev
 * extension that isn't on the Web Store.
 */
type ExtCard = { source: string; title: string; summary?: string; body?: string };

export const ext = $state({
	checked: false,
	present: false,
	loading: false,
	cards: [] as ExtCard[],
	privateTotal: 0,
	source: '' as string
});

const TAG_OUT = 'contxt-extension'; // extension → page
const TAG_IN = 'contxt-web'; // page → extension
let seq = 0;
const pending = new Map<number, (data: unknown) => void>();
let listening = false;

function ensureListener() {
	if (listening || typeof window === 'undefined') return;
	listening = true;
	window.addEventListener('message', (e: MessageEvent) => {
		if (e.source !== window) return;
		const m = e.data;
		if (!m || m.source !== TAG_OUT) return;
		if (m.type === 'present') ext.present = true;
		if ((m.type === 'pong' || m.type === 'context') && m.reqId != null) {
			const cb = pending.get(m.reqId);
			if (cb) {
				pending.delete(m.reqId);
				cb(m);
			}
		}
	});
}

function call(type: string, payload: Record<string, unknown> = {}, timeout = 900): Promise<any> {
	return new Promise((resolve) => {
		if (typeof window === 'undefined') return resolve(null);
		const reqId = ++seq;
		pending.set(reqId, resolve);
		window.postMessage({ source: TAG_IN, type, reqId, ...payload }, window.location.origin);
		setTimeout(() => {
			if (pending.has(reqId)) {
				pending.delete(reqId);
				resolve(null);
			}
		}, timeout);
	});
}

/** Ping the extension; resolves true if its content script answers. */
export async function detectExtension(): Promise<boolean> {
	ensureListener();
	const pong = await call('ping');
	ext.checked = true;
	ext.present = !!pong || ext.present;
	return ext.present;
}

/** Pull the SHARED context the extension exposes (live → bridge → fixture). */
export async function loadExtensionContext(query = 'what am I working on') {
	ext.loading = true;
	const r = await call('get:context', { query }, 5000);
	ext.loading = false;
	if (r && r.ok) {
		ext.cards = r.cards || [];
		ext.privateTotal = r.private_total || 0;
		ext.source = r.contextSource || '';
	}
	return r;
}
