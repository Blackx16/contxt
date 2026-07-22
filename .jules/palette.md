## 2024-05-18 - Svelte Component Visual State Accessibility
**Learning:** Visual state toggles (e.g., `class:active`) on custom Svelte components like filtering chips must be explicitly paired with semantic accessibility attributes. Svelte does not automatically infer `aria-pressed` or `role="group"`.
**Action:** Always add `aria-pressed={condition}` to toggle buttons and wrap related toggle groups in an element with `role="group"` and an `aria-label`. Use `aria-expanded` for buttons that reveal/hide sections.
