## 2024-07-19 - Fast-path substring check for regex guardrails
**Learning:** When looping to search for exact-word matches using regex in Python (e.g., evaluating keyword guardrails), calling the regex engine repeatedly is a performance bottleneck for negative cases.
**Action:** Always prepend a fast-path substring check (e.g., `if kw in text_lower`) before calling `re.search` to bypass regex engine overhead for negative cases.
