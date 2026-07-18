## 2024-05-24 - Fast-path substring checks before regex
**Learning:** When evaluating keyword guardrails with regex in a loop, the regex engine overhead can be significant, especially for negative cases.
**Action:** Always prepend a fast-path substring check (e.g., `if kw in text_lower`) before calling `re.search` to bypass regex overhead for negative cases.
