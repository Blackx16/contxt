## 2024-07-24 - Fast-path substring checks for regex rules
**Learning:** Evaluating keyword guardrails with regex word boundaries (`re.search`) introduces significant overhead for negative matches.
**Action:** Always prepend a fast-path substring check (`if kw in text_lower:`) before executing the regex engine for exact-word match lookups.
