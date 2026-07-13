## 2024-07-13 - Explicit ARIA attributes for filter chips
**Learning:** For filter chips styled with `.active` classes, screen readers miss the state change unless explicit `aria-pressed` or `aria-current` attributes are used. A `.filters` grouping also needs `role="group"` and an `aria-label` to provide context.
**Action:** Always map visual `.active` or selected state classes to explicit ARIA attributes (e.g., `aria-pressed={isActive}`) on custom UI controls like filter chips.
