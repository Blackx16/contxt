## 2025-02-23 - XSS Vulnerability in Extension DOM Injection
**Vulnerability:** Unescaped variables (e.g., `meta.error`, `priv`, `shared`) injected directly into `innerHTML` inside `extension/content.js` and `extension/popup.js`.
**Learning:** Even internal API responses or derived metrics must be sanitized before DOM insertion, as compromised upstream data can lead to Cross-Site Scripting (XSS).
**Prevention:** Always use an HTML escaping function (like `esc`) when building HTML strings via string interpolation to prevent XSS.
