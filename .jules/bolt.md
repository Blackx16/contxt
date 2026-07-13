## 2025-02-28 - Fast-path text concatenation in TS

**Learning:** Array allocations and mapping operations inside functions that run on every context card (like `cardText`) can create a noticeable CPU and garbage collection bottleneck. Specifically, replacing `.map().join()` with direct string concatenation yielded a 3x speedup in JS performance tests for text generation, which is heavily used in the privacy checks.
**Action:** When a function runs repeatedly inside a loop per-card (e.g. mapping entities to text for rules evaluation), avoid allocating intermediate arrays and map loops if a simple string concatenation or manual loop achieves the exact same thing with drastically less overhead.
