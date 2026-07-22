## 2024-07-22 - Prevent DOM-based XSS in Extension Content Script
**Vulnerability:** Untrusted API error messages (`meta.error`) were directly injected into `innerHTML` within `extension/content.js`, exposing a DOM-based XSS vulnerability.
**Learning:** Even internal API responses or error strings can be vectors for XSS if the upstream data is compromised or manipulated.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) before inserting them into the DOM via `.innerHTML` in vanilla JavaScript.
