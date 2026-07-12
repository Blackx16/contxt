## 2024-05-24 - [CORS origin prefix matching vulnerability]
**Vulnerability:** CORS origin validation in `server/http_bridge.py` used `origin.startswith(_ALLOWED_ORIGIN_PREFIXES)` where `_ALLOWED_ORIGIN_PREFIXES` included `http://localhost`. This allowed malicious origins like `http://localhost.evil.com` to bypass CORS.
**Learning:** Using `startswith` for origins matching without a trailing slash or port allows subdomains or domains starting with the prefix to bypass the check.
**Prevention:** Use `urllib.parse.urlparse` to parse the origin and exactly match `parsed.hostname` against allowed hosts (`localhost`, `127.0.0.1`), and catch `ValueError` during parsing to fail closed.
