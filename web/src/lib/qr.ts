/**
 * QR rendering for the multi-device key transfer (CHA-22).
 *
 * The QR is only a *transport* for the key envelope — a real, scannable code so a
 * second device (or a phone) can pick the key up out-of-band. It carries ciphertext's
 * key, never touches the blind relay. Rendering is deliberately isolated here so the
 * one third-party dependency (`qrcode`, MIT) stays swappable and out of the crypto path.
 *
 * We dynamic-import `qrcode` so it never loads during SSR (the demo is client-only) and
 * Vite resolves the browser build (its `browser` field stubs Node `fs`).
 *
 * Scannability over aesthetics: dark modules on a warm off-white chip with a quiet zone.
 * Inverted (light-on-dark) codes fail on many scanners, so the chip stays light and we
 * frame it with gold in the surrounding panel instead.
 */

// Warm, near-black modules + warm off-white field — high contrast, still on-brand.
const MODULE_DARK = '#17140f';
const MODULE_LIGHT = '#f4efe6';

export interface QrOptions {
	/** Rendered pixel size (width == height). Default 220. */
	size?: number;
	/** Quiet-zone modules around the code. Default 2. */
	margin?: number;
	/**
	 * Error-correction level. 'M' (~15%) balances density vs. resilience for a
	 * ~90-char key envelope. Higher = more robust but denser.
	 */
	ecc?: 'L' | 'M' | 'Q' | 'H';
}

/**
 * Encode `text` as an SVG QR code string.
 * Returns ready-to-inject SVG markup (use with Svelte `{@html}`), or throws if
 * the payload is too large for a QR symbol.
 */
export async function qrSvg(text: string, opts: QrOptions = {}): Promise<string> {
	const { size = 220, margin = 2, ecc = 'M' } = opts;
	const { default: QRCode } = await import('qrcode');
	const svg = await QRCode.toString(text, {
		type: 'svg',
		errorCorrectionLevel: ecc,
		margin,
		width: size,
		color: { dark: MODULE_DARK, light: MODULE_LIGHT }
	});
	// Crisp module edges when the SVG is scaled by CSS.
	return svg.replace('<svg ', '<svg shape-rendering="crispEdges" ');
}
