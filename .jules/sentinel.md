## 2024-07-19 - Missing Input Sanitization in Content Script
**Vulnerability:** XSS vulnerability in extension/content.js where meta.error was injected into the DOM via .innerHTML without being sanitized.
**Learning:** Even internal error messages passing between extension components (background to content script) can be a vector if they contain unsanitized user-influenced text or dynamic host URLs.
**Prevention:** Always sanitize any dynamic variables using an HTML escaping function (like esc) before interpolating them into HTML strings for .innerHTML, regardless of the data immediate source.
