## 2024-05-18 - Fast-path substring check before regex

**Learning:** When looping to check for keyword matches using a regex in Python (like `re.search(r"\b" + re.escape(k) + r"\b", text)`), the overhead of compiling and running the regex engine is entirely unnecessary if the keyword doesn't even exist as a substring. This is highly relevant when testing lists of words against texts.

**Action:** Before running expensive word-boundary checks in loops, always perform a fast-path substring check using the `in` operator (e.g., `if k in text_lower`). Since checking `k in text_lower` is heavily optimized in C within Python, it provides a measurable speed boost by skipping the regex engine for negative cases.
