import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// Builds the Svelte popup into ../ui as an MV3-safe bundle:
//  - base './'      → relative asset URLs (chrome-extension:// friendly)
//  - modulePreload off → no inline preload script (MV3 CSP blocks inline <script>)
//  - single external module script + css, both self-hosted.
export default defineConfig({
	plugins: [svelte()],
	base: './',
	build: {
		outDir: '../ui',
		emptyOutDir: true,
		target: 'esnext',
		modulePreload: false,
		rollupOptions: {
			input: 'popup.html',
			output: { inlineDynamicImports: true, entryFileNames: 'popup.js', assetFileNames: 'popup.[ext]' }
		}
	}
});
