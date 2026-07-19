## 2026-07-19 - XSS Vulnerability in Extension UI
**Vulnerability:** Unsanitized dynamic variables injected via `.innerHTML` in the browser extension's content script (`extension/content.js`).
**Learning:** Browser extensions using vanilla JavaScript and `.innerHTML` for DOM manipulation are vulnerable to Cross-Site Scripting (XSS) if dynamic data (like error messages from external sources) is not HTML-escaped.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) before interpolating them into `.innerHTML` templates.
