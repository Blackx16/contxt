## 2024-05-24 - Keyword Regex Search Fast Path
**Learning:** In Python, searching for exact-word matches using `re.search` with a word boundary (`\b`) inside a loop over many keywords on long text introduces significant regex engine overhead. A fast-path substring check (e.g. `if kw in text_lower`) can bypass the expensive regex for negative cases, speeding up execution by >95% when there are few matches.
**Action:** When looping to evaluate keyword guardrails via exact-word regex, always prepend a substring check before calling `re.search` to rapidly skip missing keywords.
