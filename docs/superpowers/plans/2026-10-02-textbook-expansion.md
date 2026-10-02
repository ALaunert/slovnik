# Textbook Expansion Implementation Plan

> **For agentic workers:** Execute the independent editorial domains in parallel, then integrate and review sequentially. The owner explicitly requested autonomous execution.

**Goal:** Expand the written Serbian grammar textbook as far as directly checked sources justify, and create an unmerged PR.

**Architecture:** Preserve the bundled JSON and stable chapter IDs. Keep source review and coverage in documentation; add only reader improvements needed for a larger book.

**Tech Stack:** Vue 3, TypeScript, JSON, Vitest, Playwright Chromium.

**Spec:** `docs/superpowers/specs/2026-10-02-textbook-expansion-design.md`

## Global Constraints

- Russian explanations; Serbian Latin/Ekavian editorial base; mark normative variants.
- Original examples and translations; exact source locators; narrow unsupported claims.
- No backend, assessment, profile, progress or curriculum changes.
- Preserve 20 existing IDs and unrelated files; PR only, no merge.

## Review Focus

- Serbian Cyrillic queries must find Latin examples and vice versa, with lossy diacritic matching limited to search.
- Full and clitic pronouns, plural paradigms and irregular stems must not be generated from false universal rules.
- Rare tenses and participles require register/recognition labels and source checks.
- Complex clauses and free sample answers must retain context and alternatives.
- Long tables and chapter navigation must work without API/profile at mobile widths.

## Tasks

- [x] Audit source access and actual initial coverage; check baseline and current main.
- [x] Independently expand names/pronouns/numerals, verbs, syntax; retain source and coverage decisions per domain.
- [x] Expand writing, adverbs/prepositions/particles and discovered gaps; integrate checked editorial batches.
- [x] Add failing search/navigation regressions, implement reader improvements, run focused tests.
- [x] Review all content, cross-links, sources, translations and rights; resolve gaps or document exclusion.
- [x] Run units, typecheck, build and Chromium e2e; visually inspect long mobile/desktop chapters.
- [x] Update durable audit/docs and inspect the verified diff for delivery as an unmerged PR.

Delivery: commit only the reviewed files, push the branch, create and attach its PR.
Merging is excluded from the user's requested completion state.

## Execution record

2026-10-02: Clean checkout; fetched origin/main and created
`codex/expanded-grammar-textbook`. Official SEELRC PDF now accessible via its
HTTP port 8080 URL; prior research's access limitation is historical. Source PDFs
are kept in `/tmp/slovnik-sources`, not distributed. Autonomous owner instruction
supersedes skill review pauses. Editorial domains use separate temporary output
files so agents do not edit the shared book concurrently.

Final edition: 79 chapters, 10 groups, 40 sources, 347 examples, 242 self-checks,
70 tables. Verification: 130 frontend unit tests, typecheck/build and 17 Chromium
e2e passed. Visual review: 1280, 390 and 320px. Important review findings (occluded
anchors and missing Vi agreement) were fixed and independently rechecked; the
coverage map records source/lexical/contextual gaps rather than a chapter cap.
