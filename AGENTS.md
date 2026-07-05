# Agent Instructions

- Start every session by reading `docs/product-state.md`, `README.md`, and any docs relevant to the task.
- Treat `docs/product-state.md` as the canonical current-state audit for Slovnik.
- When changing product behavior, architecture, setup, caveats, verification steps, or deferred scope, update `docs/product-state.md` in the same PR/commit.
- Keep the audit high-signal: summarize durable product facts and avoid dumping transient implementation logs.
- Verify claims against code, docs, and git/PR artifacts where useful. Do not invent capabilities.
- Before claiming completion, run relevant tests or sanity checks and document verification when the product state changes.
- Preserve unrelated untracked or user-made files; stage and commit only the files intentionally changed for the task.
