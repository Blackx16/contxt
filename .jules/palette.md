## 2024-07-16 - Svelte Toggle Button Attributes
**Learning:** Visual active state toggles (like `class:active`) on chips or toggle buttons must be explicitly paired with corresponding semantic accessibility attributes for keyboard/screen reader users.
**Action:** Always add `aria-pressed`, `aria-expanded`, and `role="group"` (for their container) to UI elements mimicking these interactive states, regardless of Svelte visual class bindings.
