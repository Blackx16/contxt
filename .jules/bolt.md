## 2024-05-18 - Fast-path Substring Check for Regex Optimization
**Learning:** Codebase performance pattern: When looping to search for exact-word matches using regex in Python (e.g., evaluating keyword guardrails), always prepend a fast-path substring check (e.g., `if kw in text_lower`) before calling `re.search` to bypass regex engine overhead for negative cases.
**Action:** Apply this pattern consistently across the codebase wherever iterative regex word matching over a long list of keywords is performed, drastically reducing computation time.
