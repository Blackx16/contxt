## 2025-02-27 - Insecure CORS Origin Validation via startswith
**Vulnerability:** The HTTP bridge `server/http_bridge.py` used `startswith(("http://localhost", "http://127.0.0.1"))` to validate the CORS `Origin` header. This allowed malicious sites like `http://localhost.evil.com` to bypass restrictions and access sensitive API endpoints cross-origin.
**Learning:** Checking origins using basic string prefixes (`startswith`) is inherently insecure because subdomains can easily be registered to match the prefix string.
**Prevention:** Always use a URL parser (like `urllib.parse.urlparse`) to extract the exact `hostname` and validate against strict allowed hostnames, instead of using prefix-based string matching for Origins.
