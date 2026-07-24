## 2024-07-24 - Semantic Accessibility for Visual Toggles
**Learning:** Visual state toggles (`class:active`) in Svelte components need to be explicitly paired with corresponding semantic accessibility attributes (like `aria-pressed`, `aria-expanded`, and `role="group"`) to ensure screen readers receive the same state information as visual users.
**Action:** Always couple visual state bindings with semantic ARIA state bindings for custom interactive components.
