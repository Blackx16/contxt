## 2024-07-23 - DOM-Based XSS in content script
**Vulnerability:** Unsanitized internal API response (`meta.error`) was injected directly into the DOM via `.innerHTML` in `extension/content.js`.
**Learning:** Even internal or derived metrics can be vectors for XSS if upstream data is compromised or maliciously formatted, especially in browser extension content scripts operating on third-party pages.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function before injecting them into `.innerHTML`.
