## 2024-11-02 - DOM XSS via Unsanitized Internal API Errors in Content Script
**Vulnerability:** The browser extension's content script (`extension/content.js`) was vulnerable to DOM-based Cross-Site Scripting (XSS). It injected the `meta.error` string from the background script's response directly into the DOM using `.innerHTML` without sanitization.
**Learning:** Even internal API responses and derived metrics can be compromised or contain malicious data. Trusting upstream data when manipulating the DOM in a vanilla JS extension is a dangerous pattern that can lead to XSS on host pages.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) when using `.innerHTML` in vanilla JavaScript, regardless of the data source.
