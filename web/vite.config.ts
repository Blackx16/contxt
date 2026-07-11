import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';

// Kit config (adapter, paths, prerender) lives in svelte.config.js.
export default defineConfig({
	plugins: [sveltekit()]
});
