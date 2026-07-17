## 2024-05-24 - Unsanitized variable in extension DOM injection
**Vulnerability:** Found `meta.error` being directly interpolated into `.innerHTML` in `extension/content.js` without HTML escaping, posing an XSS risk if the error string is maliciously crafted upstream.
**Learning:** Content scripts using `.innerHTML` to inject UI elements must be extremely careful to escape all dynamic content, even error strings, to prevent execution in the host page's context.
**Prevention:** Always use a helper function (e.g. `esc`) to sanitize any dynamic variable before interpolating it into an HTML template string assigned to `.innerHTML`.
