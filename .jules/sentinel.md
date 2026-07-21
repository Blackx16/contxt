## 2024-05-30 - Prevent DOM-based XSS in Extension Content Scripts
**Vulnerability:** Unsanitized dynamic variables (e.g. `meta.error`) were directly interpolated into `innerHTML` inside `extension/content.js`, creating a DOM-based Cross-Site Scripting (XSS) risk.
**Learning:** Even internal API responses and derived metrics can be compromised upstream, meaning any data inserted into the DOM via `.innerHTML` without escaping can be exploited for XSS.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (e.g., replacing special characters like `<, >, &, ", '`) before interpolating them into `.innerHTML`.
