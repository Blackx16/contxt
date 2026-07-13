/**
 * Talks to the (locally-loaded) Contxt browser extension.
 *
 * The extension injects a content script (site-connect.js) on this origin which
 * relays get:context (the FULL shared list + connection status) from the
 * background and pushes fresh snapshots when the popup's state changes — so the
 * site mirrors the extension in real time. Detection is ping/pong over
 * window.postMessage, so no extension ID is needed (works for the unpacked
 * dev extension).
 */
type ExtCard = { source: string; title: string; summary?: string; body?: string };
type SealedBlob = { alg?: string; ct: string; iv: string };
type PrivateCard = {
	source: string;
	title: string;
	heldBy?: string[];
	reason?: string;
	forced?: boolean;
	blob?: SealedBlob;
};
type Conns = { google: boolean; googleEmail: string; notion: boolean; notionWorkspace: string };
export type PolicyState = Record<string, boolean>;

export const ext = $state({
	checked: false,
	present: false,
	loading: false,
	cards: [] as ExtCard[],
	privateCards: [] as PrivateCard[],
	privateTotal: 0,
	heldTotal: 0,
	source: '' as string,
	connections: { google: false, googleEmail: '', notion: false, notionWorkspace: '' } as Conns,
	policy: null as PolicyState | null,
	categoryCounts: null as Record<string, number> | null
});

const TAG_OUT = 'contxt-extension'; // extension → page
const TAG_IN = 'contxt-web'; // page → extension
let seq = 0;
const pending = new Map<number, (data: unknown) => void>();
let listening = false;

// Single place that applies a context snapshot — used for both request replies
// and the extension's unsolicited real-time pushes (reqId 0).
function applyContext(m: any) {
	ext.present = true;
	if (m.ok) {
		ext.cards = m.cards || [];
		ext.privateCards = m.privateCards || [];
		ext.privateTotal = m.private_total || 0;
		ext.heldTotal = m.heldTotal || 0;
		ext.source = m.contextSource || '';
		if (m.connections) ext.connections = m.connections;
		if (m.policy) ext.policy = m.policy;
		if (m.categoryCounts) ext.categoryCounts = m.categoryCounts;
	}
	ext.loading = false;
}

function ensureListener() {
	if (listening || typeof window === 'undefined') return;
	listening = true;
	window.addEventListener('message', (e: MessageEvent) => {
		if (e.source !== window) return;
		const m = e.data;
		if (!m || m.source !== TAG_OUT) return;
		if (m.type === 'present') ext.present = true;
		if (m.type === 'context') applyContext(m);
		if ((m.type === 'pong' || m.type === 'context' || m.type === 'policy:set') && m.reqId != null) {
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

/** Pull the FULL shared context + connections (applyContext runs on the reply). */
export async function loadExtensionContext(query = 'what am I working on') {
	ext.loading = true;
	await call('get:context', { query }, 5000);
	ext.loading = false;
}

/**
 * Flip one privacy rule in the extension. Optimistically updates the local
 * policy, tells the extension to persist + re-tier, then reloads the snapshot so
 * cards move between SHARED and PRIVATE live. (The extension also pushes an
 * unsolicited snapshot via storage.onChanged, so this is belt-and-suspenders.)
 */
export async function setPolicy(id: string, on: boolean): Promise<void> {
	if (ext.policy) ext.policy = { ...ext.policy, [id]: on };
	const res = await call('set:live:policy', { id, on }, 2000);
	if (res?.policy) ext.policy = res.policy;
	await loadExtensionContext();
}
