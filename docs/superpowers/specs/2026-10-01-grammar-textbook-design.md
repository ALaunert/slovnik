# Grammar textbook and practice entry

## User correction

The requested product is learning material organised by grammar topic. Four written pilot
tasks and a research folder do not satisfy that requirement. The 2026-10-01 correction
authorises implementing a readable textbook in the app; ordinary design decisions are
made autonomously, with Astra content/review assistance instead of another owner gate.

## Reader

A bundled, versioned JSON book contains independently authored Russian explanations,
Serbian examples and separate Russian translations. Chapters belong to named topic groups.
Each chapter includes concrete rules, examples, pitfalls, self-check prompts with expandable
sample answers, source locators and links to related chapters. It is a reading resource,
not a scored assessment, CEFR certificate or replacement practice scheduler.

`/textbook` shows a searchable grouped directory; `/textbook/:chapterId` shows a chapter.
Both work without a profile and without a running backend. Navigation, the entry page and
dashboard expose the textbook. Direct links, nonexistent chapters, mobile tables and changing
chapters must work. Explanations remain Russian when surrounding controls use Serbian.

Only internally checked original material is bundled. Research drafts are not imported.
The review journal records exact source pages, authorship, rights by layer and remaining
language limits. The book covers the core grammar actually provided; it does not claim
exhaustive A1–B1 coverage. No reserved pilot assessment material is reused.

## Practice entry defect

The live dedicated backend currently reports availability=true. PracticeView incorrectly
uses the same unavailable message for an absent profile and a disabled pilot. Separate
those states. An absent profile receives a clear entry link to `/?next=practice`; successful
profile entry returns to `/practice`. The return destination is an allowlisted route name,
never an arbitrary URL. A disabled backend retains the loopback safety gate and offers
retry and textbook reading. Failed availability requests offer retry without losing history.

## Constraints

Preserve all existing dirty/user files, immutable practice attempts, old API/data semantics,
loopback restrictions and daily allocation. Authentication stays outside scope. Do not
fabricate learners, language efficacy or research outcomes. No database schema changes.

## Verification

Reproduce missing-profile misdiagnosis before fixing it. Test profile return allowlist,
disabled/recovered availability and existing resume. Test book references and meaningful
chapter coverage, search, direct links, missing chapters and self-check answer isolation.
Run frontend unit/type/build/browser checks and the backend suite. Review the diff and
update product-state with durable shipped behaviour and limits.
