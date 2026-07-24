## 2024-05-24 - DOM-based XSS in Extension Badge
**Vulnerability:** DOM-based Cross-Site Scripting (XSS) vulnerability in `extension/content.js`.
**Learning:** Dynamic variables from upstream (like `meta.error` or API responses) were injected directly into `innerHTML` without sanitization.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function before injecting them into the DOM via `.innerHTML`.
