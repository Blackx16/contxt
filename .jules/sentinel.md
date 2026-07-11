## 2024-05-18 - Overly Permissive CORS Configuration
**Vulnerability:** CORS origin validation using `startswith` (e.g. `origin.startswith("http://localhost")`) allowed bypasses via malicious subdomains like `http://localhost.evil.com`.
**Learning:** `startswith` checks for URLs are inherently insecure and can easily be bypassed by attackers crafting specific domain names.
**Prevention:** Always use a robust URL parser (like `urllib.parse.urlparse`) to extract the scheme and hostname, and then validate them explicitly against an allowlist, preserving any existing trusted specific origins.
