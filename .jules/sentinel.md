## 2026-07-20 - DOM-based XSS via innerHTML in extension badge
**Vulnerability:** Unsanitized error messages from the backend or runtime were injected directly into the DOM using `.innerHTML` in `extension/content.js`.
**Learning:** Compromised upstream data or manipulated error responses can execute arbitrary JavaScript in the context of the host page (DOM-based XSS), bypassing standard extension protections.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function before injecting them into the DOM via `.innerHTML`, even for internal API responses or derived metrics.
