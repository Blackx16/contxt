## 2024-07-18 - Svelte visual state pairing with ARIA attributes
**Learning:** In Svelte, visual state toggles (like `class:active`) lack semantic meaning for screen readers.
**Action:** Always pair visual state toggles like `class:active` on chips or toggle buttons with corresponding semantic accessibility attributes like `aria-pressed`, `aria-expanded`, and add `role="group"` + `aria-label` for their container.
