## 2025-02-28 - Fast regex evaluation by replacing regex string match allocation

**Learning:** `re.findall()` allocates a string array, copying the underlying text, which scales poorly and creates garbage collection overhead when scanning large strings for matches. Searching within the list via string matches `t in words` adds an O(N) memory requirement.
**Action:** When you only need to confirm the presence of some exact, pre-validated tokens bounded by word boundaries, use a bounded `re.search()` inside a loop. `re.search` is highly optimized in C and early exits as soon as it matches without allocating the rest of the matches into strings.
