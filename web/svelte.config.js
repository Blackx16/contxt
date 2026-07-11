import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

// GitHub Pages serves a project site under /<repo> (e.g. /contxt). The Pages
// build sets BASE_PATH=/contxt; local dev/preview leaves it empty so links work
// at the root. Everything here is a fully static, client-side app (Web Crypto,
// QR, runes state) — so we prerender every route and ship plain HTML/JS.
const base = process.env.BASE_PATH || '';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({ fallback: '404.html' }),
		paths: { base },
		prerender: { handleHttpError: 'warn' }
	}
};
