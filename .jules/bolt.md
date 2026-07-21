## 2024-05-24 - Fast-path Substring Checks for Regex

**Learning:** When looping to search for exact-word matches using regex in Python (e.g., evaluating keyword guardrails), always prepend a fast-path substring check to bypass regex engine overhead for negative cases.
**Action:** Use `text.lower()` once outside the loop and `if kw in text_lower:` inside the loop before calling `re.search`.
