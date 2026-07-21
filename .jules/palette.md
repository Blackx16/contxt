## 2024-07-21 - Visual State Toggles Require Semantic Pairing
**Learning:** Svelte's `class:active` on chips or toggle buttons must be explicitly paired with corresponding semantic accessibility attributes to be perceptible to screen readers.
**Action:** Always include `aria-pressed`, `aria-expanded`, and `role="group"` (for their container) when using visual state toggles.
