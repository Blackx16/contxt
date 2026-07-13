/**
 * Demo mode.
 *
 *  ON  (default) — the site is a self-contained explainer: shows the built-in
 *                  two-tier demo (fixtures + crypto). Never touches the extension.
 *  OFF           — real-product mode: checks for the installed Contxt extension
 *                  and shows the user's own live context (or an install prompt).
 *
 * Default ON so a first-time visitor / judge without the extension always lands
 * on the polished demo. Persisted in localStorage.
 */
import { browser } from '$app/environment';

const KEY = 'contxt:demoMode';

export const demo = $state({ on: true });

if (browser) {
	const saved = localStorage.getItem(KEY);
	if (saved != null) demo.on = saved === '1';
}

export function setDemo(on: boolean) {
	demo.on = on;
	if (browser) localStorage.setItem(KEY, on ? '1' : '0');
}
