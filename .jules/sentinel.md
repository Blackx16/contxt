## 2025-03-05 - XSS in Browser Extension Badges
**Vulnerability:** Found unescaped user-controlled or external data (`meta.error`) being injected via `innerHTML` into the Contxt shadow DOM badge (`extension/content.js`).
**Learning:** Even within a Shadow DOM, unescaped dynamic properties assigned to `innerHTML` expose the extension to Cross-Site Scripting (XSS) risks.
**Prevention:** Always sanitize any dynamic variables using an HTML escaping function (like `esc`) before interpolating them into HTML strings for `.innerHTML`.
