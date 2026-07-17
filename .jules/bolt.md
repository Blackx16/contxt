## 2024-05-24 - Keyword Matching Regex Overhead
**Learning:** Looping to search for exact-word matches using regex (`re.search(r"\b" + kw + r"\b")`) incurs significant regex engine overhead for negative cases.
**Action:** Always prepend a fast-path substring check (`if kw in text_lower`) before calling `re.search` to bypass regex engine overhead.
