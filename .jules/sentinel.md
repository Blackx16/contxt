## 2025-02-15 - Unsanitized Interpolation in Extension Content Script
**Vulnerability:** XSS vulnerability in `extension/content.js` where the error message `meta.error` was directly rendered via string interpolation into `root.innerHTML` without escaping.
**Learning:** Even internal API errors or local states should be sanitized before rendering into the DOM, especially when modifying innerHTML in content scripts that run in various environments.
**Prevention:** Always use an HTML escaping function (like the one present in `popup.js`) before injecting dynamic values into innerHTML, or prefer `textContent` / `innerText` when rendering plain text.
