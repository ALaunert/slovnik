# Grammar textbook implementation plan

> **For agentic workers:** Execute tasks inline using superpowers:executing-plans;
> Astra authors and reviews independent content. No commit/stage of pre-existing changes.

**Goal:** Deliver grammar lessons in the app and repair misleading local-practice entry.

**Architecture:** Bundle a read-only JSON book with Vue topic/chapter views; no backend or
profile dependency for reading. Keep practice API and history unchanged, with an explicit
profile-required entry and an allowlisted return route.

**Tech Stack:** Vue 3, TypeScript, Vue Router, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-01-grammar-textbook-design.md`

## Global constraints

- Preserve existing dirty files and loopback guards; no auth, schema, scheduler or grading changes.
- Textbook prose is Russian, Serbian examples are original and internally source checked.
- Self-check answers are samples, not exhaustive automatic scoring keys.
- Update `docs/product-state.md` and report actual verification and content limits.

## Review focus

- Empty browser profile must produce useful profile entry, not pilot-disabled diagnosis.
- `next` query cannot send a profile visitor to an arbitrary/external URL.
- Direct chapter navigation and browser back must keep the correct content and answer visibility.
- Search with Serbian diacritics/Russian text must leave useful clear/no-results states.
- Wide form tables must remain usable on a 390px screen.

## Task 1: Practice entry

- [x] Add failing missing-profile/recovered-availability tests in `tests/unit/practice.test.ts`.
- [x] Add profile-entry tests using real router and mocked external fetch for the return allowlist.
- [x] Observe failures; fix `PracticeView.vue`, `UserAccessView.vue`, `router.ts`, messages.
- [x] Run existing practice unit tests and browser resume tests.

## Task 2: Grammar reader

- [x] Astra creates `src/content/serbian-textbook.json` and `docs/learning/textbook-review.md`.
- [x] Add failing unit/browser tests for directory/search/direct chapter/self-check/missing chapter.
- [x] Implement typed `src/content/textbook.ts`, `TextbookView.vue`, `TextbookChapterView.vue`.
- [x] Register routes and visible entry/navigation/dashboard links; verify on mobile and desktop.
- [x] Validate content references and source/rights decisions; address reviewer findings.

## Task 3: Ship verification

- [x] Run unit suite, type/build, Chromium suite and backend suite.
- [x] Review task diff without staging/committing unrelated work.
- [x] Update audit/README with textbook location, actual coverage and remaining limits.
