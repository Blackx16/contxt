## 2024-07-18 - Fast-path substring check before regex search
**Learning:** When looping to search for exact-word matches using regex in Python, evaluating the regex engine for every keyword has significant overhead for negative cases.
**Action:** Always prepend a fast-path substring check (`if kw in text_lower`) before calling `re.search` to bypass the regex engine overhead for negative cases.
