## 2023-10-27 - Svelte 5 Event Handlers & Promises
**Learning:** In Svelte 5, inline event handlers like `onclick={() => asyncFunction()}` can trigger `svelte-check` type errors ("void is not assignable to Promise<void>") if the handler signature strictly expects `() => void` but receives a `Promise`.
**Action:** When wrapping async functions in inline handlers or helpers, ensure the type signature accepts `() => Promise<void> | void` to keep Svelte's typechecker happy.
