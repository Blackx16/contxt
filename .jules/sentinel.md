## 2024-05-24 - DOM-based XSS in Extension Content Script
**Vulnerability:** The browser extension (`extension/content.js`) was inserting unsanitized API error responses directly into the DOM using `.innerHTML`, creating a DOM-based Cross-Site Scripting (XSS) vulnerability.
**Learning:** Even internal API responses or error strings can be manipulated by compromised upstream data. Trusting these implicitly when manipulating `.innerHTML` can lead to XSS execution in the context of the host page.
**Prevention:** Always sanitize dynamic variables using an HTML escaping function (like `esc`) before injecting them into the DOM via `.innerHTML`, even if the data seems safe or originates internally.
