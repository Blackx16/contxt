## 2024-05-24 - DOM-based XSS in Browser Extension Content Script
**Vulnerability:** The browser extension's content script injected dynamic variables (`meta.error`, `HOST.label`, `src`) directly into the DOM using `.innerHTML` without sanitization.
**Learning:** When generating HTML strings dynamically in vanilla JavaScript, especially in extensions with broad host permissions, failure to escape variables can lead to DOM-based XSS vulnerabilities if external data is compromised or unexpected.
**Prevention:** Always sanitize dynamic string variables using an HTML escaping function before interpolating them into `.innerHTML`, or use `.textContent` for safe text insertion.
