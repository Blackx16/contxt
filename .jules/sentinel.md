## 2024-07-18 - Prevent XSS in extension content script via innerHTML
**Vulnerability:** Unsanitized error messages (`meta.error`) were being injected into the DOM via `.innerHTML` in the browser extension's content script, creating a Cross-Site Scripting (XSS) vector on AI surfaces (e.g. ChatGPT, Claude).
**Learning:** Dynamic variables injected via `.innerHTML` even in seemingly isolated environments like a shadow DOM must be sanitized.
**Prevention:** Always use an HTML escaping function to sanitize dynamic strings before using them in `.innerHTML` within browser extensions.
