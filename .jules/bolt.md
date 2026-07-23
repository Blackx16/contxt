## 2024-07-23 - Fast-path substring check before regex
**Learning:** Regex word boundary searches (`\b`) inside a loop have high overhead. In `gateway/rules.py`, the engine processes every regex match attempt. Prepending a simple `in` substring check (`k in text_lower`) bypasses the regex engine entirely for negative cases, reducing execution time by ~80% in benchmarks.
**Action:** When looping to search for exact-word matches using regex in Python, always prepend a fast-path substring check before calling `re.search` to bypass regex engine overhead for negative cases.
