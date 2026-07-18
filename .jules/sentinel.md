## 2024-07-18 - XSS Vulnerability in Extension Content Script
**Vulnerability:** XSS vulnerability in `extension/content.js` via unescaped string injection in `.innerHTML`.
**Learning:** The `renderBadge` function used `.innerHTML` to insert dynamic error strings (`meta.error`) without sanitizing HTML tags, potentially allowing arbitrary script execution on host pages like Claude, ChatGPT, or Gemini.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) before using them in DOM manipulation via `.innerHTML`.
