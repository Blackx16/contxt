## 2025-02-23 - Keyword matching regex overhead
**Learning:** Evaluating keyword guardrails by running `re.search` repeatedly inside a loop is extremely slow for negative cases because of the regex engine overhead.
**Action:** Always prepend a fast-path substring check (e.g., `if kw in text_lower`) before calling `re.search` to bypass regex overhead for negative cases, reducing execution time significantly.
