## 2024-05-20 - [Fast-Path Substring Checks Before Regex Guardrails]
**Learning:** Running regex word-boundary searches (`re.search(r'\b...\b')`) in a loop over keyword guardrails introduces significant overhead, especially for negative matches (the common case).
**Action:** Always prepend a fast-path substring check (e.g., `if keyword in text_lower:`) to bypass the regex engine entirely when the keyword isn't even present in the string.
