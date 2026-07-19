## 2025-02-26 - Regex Fast-Path Substring Check
**Learning:** Codebase performance pattern: When looping to search for exact-word matches using regex in Python (e.g., evaluating keyword guardrails), the regex engine overhead can be significant for negative cases.
**Action:** Always prepend a fast-path substring check (e.g., `if kw in text_lower`) before calling `re.search` to bypass regex engine overhead for negative cases.
