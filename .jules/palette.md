## 2024-05-18 - Svelte Toggle Button Accessibility
**Learning:** Toggle button groups relying on `class:active` for visual styling lack screen reader support for their active state.
**Action:** Always pair `class:active` with `aria-pressed` (or similar) on the buttons, and wrap them in a container with `role="group"` and a descriptive `aria-label`.
