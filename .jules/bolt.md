## 2024-07-16 - Fast-path substring check before regex

**Learning:** When looping to search for exact-word matches using regex in Python (e.g., evaluating keyword guardrails), the regex engine overhead is significant, especially for negative cases where the word doesn't appear at all.

**Action:** Always prepend a fast-path substring check (e.g., `if kw in text_lower`) before calling `re.search` to bypass regex engine overhead for negative cases.
