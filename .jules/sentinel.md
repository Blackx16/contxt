## 2025-05-24 - CORS origin validation bypass via startswith
**Vulnerability:** CORS origin validation using `startswith` (e.g., `origin.startswith("http://localhost")`) allows bypass via subdomains (e.g., `http://localhost.attacker.com`).
**Learning:** Origin headers must be parsed using a URL parser (like `urlparse`) to exactly match the hostname and scheme, rather than matching a prefix string.
**Prevention:** Always use `urlparse` or exact string matching (for fixed origins) when validating CORS headers.
