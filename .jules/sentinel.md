## 2024-05-24 - Fix DOM-based XSS in Content Script
**Vulnerability:** The browser extension's content script (`extension/content.js`) used `.innerHTML` to render the on-page Contxt badge without escaping dynamic variables from API responses (such as error messages or metrics).
**Learning:** Even internal API responses or metrics can be a source of DOM-based XSS if the upstream data is compromised, especially when injecting UI elements into high-trust host pages via Shadow DOM.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) before interpolating them into HTML templates when manipulating the DOM via `.innerHTML` in vanilla JS.
