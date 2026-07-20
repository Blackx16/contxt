## 2024-07-20 - Prevent DOM-based XSS in vanilla JS
**Vulnerability:** Unsanitized upstream data (`meta.error`) was directly injected into the DOM via `.innerHTML` in `extension/content.js`.
**Learning:** Even if data originates from the backend, it must be treated as untrusted in the frontend. Compromised upstream data can lead to DOM-based XSS.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) when manipulating DOM elements via `.innerHTML` in vanilla JavaScript.
