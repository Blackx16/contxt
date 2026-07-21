## 2024-05-24 - Fast-path substring checks before regex
**Learning:** When looping to search for exact-word matches using regex in Python (e.g., evaluating keyword guardrails), the regex engine overhead is significant for negative cases.
**Action:** Always prepend a fast-path substring check (e.g., `if kw in text_lower`) before calling `re.search` to bypass regex overhead for negative cases.
