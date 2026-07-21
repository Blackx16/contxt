## 2024-05-24 - XSS via unsanitized DOM manipulation
**Vulnerability:** DOM-based Cross-Site Scripting (XSS) via unsanitized dynamic variables in `.innerHTML`.
**Learning:** When generating UI with string templates and `.innerHTML` in a vanilla JS browser extension, even internal or derived metrics must be sanitized, as compromised upstream data can inject malicious scripts into the host page.
**Prevention:** Always use an HTML escaping function for any dynamic data interpolated into an `.innerHTML` string, or prefer `.textContent` where possible.
