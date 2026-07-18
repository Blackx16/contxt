## 2024-07-18 - Fix XSS Vulnerability in Extension Content Script
**Vulnerability:** extension/content.js injected unescaped values (`meta.error` and `HOST.label`) directly into the `.innerHTML` of a Shadow DOM element, leading to a potential Cross-Site Scripting (XSS) vulnerability.
**Learning:** Even within an isolated Shadow DOM, directly interpolating dynamic content into `.innerHTML` without escaping allows arbitrary script execution in the context of the host page.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) before assigning them to `.innerHTML`.
