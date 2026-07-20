## 2026-07-20 - Fix DOM-based XSS in Contxt Badge
**Vulnerability:** DOM-based XSS via unsanitized variables injected into `.innerHTML` when rendering the Contxt badge.
**Learning:** Dynamic variables injected via template literals directly into `innerHTML` must be escaped to prevent malicious input from executing code, even if data comes from internal sources like `meta.error` or API responses.
**Prevention:** Always use an HTML escaping utility (like `esc`) on variables before interpolating them into `.innerHTML`, or prefer `.textContent`/`.innerText` when possible.
