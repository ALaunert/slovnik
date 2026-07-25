# Active Recall Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace passive vocabulary review with reveal-first active recall and a persisted adaptive
review schedule.

**Architecture:** Extend each `UserWordProgress` row with current scheduling state, keep transition
rules in `learning_service.py`, and add one singular rating endpoint. The Vue review route saves each
rating before advancing and reconciles an ambiguous network failure through the precise uncapped
per-word status endpoint.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic, pytest, Vue 3, TypeScript, Vitest,
Playwright.

---

### Task 1: Persist review scheduling state

**Files:**
- Create: `backend/alembic/versions/20260725_0004_active_recall_schedule.py`
- Modify: `backend/app/models.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_migrations.py`
- Modify: `backend/tests/test_schema.py`

- [ ] **Step 1: Write failing model and migration tests**

Add schema assertions that a new `UserWordProgress` has `review_interval_days == 0`,
`review_streak == 0`, and `next_review_at is None`. Extend migration tests to assert:

```python
progress_columns = {
    column["name"]: column for column in inspector.get_columns("user_word_progress")
}
assert progress_columns["next_review_at"]["nullable"] is True
assert progress_columns["review_interval_days"]["nullable"] is False
assert progress_columns["review_streak"]["nullable"] is False
assert {index["name"] for index in inspector.get_indexes("user_word_progress")} >= {
    "ix_user_word_progress_next_review_at"
}
```

Seed a legacy progress row before upgrading to `head`, then assert its original status/counts remain,
the new counters are zero, and `next_review_at` is null. Extend downgrade assertions to confirm the
three fields and their index are removed.

- [ ] **Step 2: Run tests and verify RED**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_schema.py tests/test_migrations.py -q
```

Expected: failures because the model and migration fields do not exist.

- [ ] **Step 3: Add model and response fields**

Add to `UserWordProgress`:

```python
next_review_at: Mapped[datetime | None] = mapped_column(
    DateTime(timezone=True), index=True
)
review_interval_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
review_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

Expose the same fields from `UserWordProgressRead`, with `next_review_at: datetime | None`.

- [ ] **Step 4: Add Alembic revision**

Create revision `20260725_0004`, down revision `20260725_0003`. Add nullable
`next_review_at`, non-null integer counters with server default `0`, and the named due-time index.
Downgrade drops the index before the columns.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_schema.py tests/test_migrations.py -q
```

Expected: all selected tests pass; PostgreSQL-only tests may skip when their admin URL is unset.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/20260725_0004_active_recall_schedule.py \
  backend/app/models.py backend/app/schemas.py backend/tests/test_migrations.py \
  backend/tests/test_schema.py
git commit -m "feat: persist active recall schedule"
```

### Task 2: Schedule and grade due reviews

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/services/learning_service.py`
- Modify: `backend/app/services/quiz_service.py`
- Modify: `backend/app/routers/learning.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_learning.py`
- Modify: `backend/tests/test_quizzes.py`

- [ ] **Step 1: Write failing due-queue tests**

Cover these behaviors in `test_learning.py`:

- completing new words sets `next_review_at` about one day ahead;
- a future-scheduled word is excluded;
- an overdue word is included;
- a legacy null-schedule word keeps the old same-day exclusion;
- weak due words sort before non-weak due words.

Use broad timestamp bounds around the request instead of exact microseconds.

- [ ] **Step 2: Run due-queue tests and verify RED**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_learning.py -q
```

Expected: failures because completion and selection do not use scheduling fields.

- [ ] **Step 3: Implement due selection and first schedule**

Set `next_review_at = now + timedelta(days=1)` when completing a new word. Refactor the review
selection predicate into a focused helper:

```python
def _is_due(progress: UserWordProgress, now: datetime) -> bool:
    if progress.next_review_at is not None:
        return _as_utc(progress.next_review_at) <= now
    first_seen = _as_utc(progress.first_seen_at)
    last_seen = _as_utc(progress.last_seen_at)
    return progress.is_weak or (
        (last_seen is None or last_seen.date() < now.date())
        and (first_seen is None or first_seen.date() < now.date())
    )
```

Normalize SQLite-naive datetimes in `_as_utc`. Order by weakness, due time (null first), last seen,
then stable row id before applying the 20-card cap.

- [ ] **Step 4: Run due-queue tests and verify GREEN**

Run the Task 2 focused command again. Expected: due-selection tests pass.

- [ ] **Step 5: Write failing rating/API tests**

Add a parameterized test for the four ratings and their expected interval, streak, weak state,
status, and approximate due time:

```python
@pytest.mark.parametrize(
    ("rating", "interval_days", "streak", "is_weak"),
    [
        ("again", 0, 0, True),
        ("hard", 1, 0, True),
        ("good", 2, 1, False),
        ("easy", 4, 1, False),
    ],
)
```

Also cover interval multipliers/caps, three consecutive Good/Easy ratings becoming learned, invalid
rating validation, unseen/unknown/future-due rejection, singular response shape, and legacy batch
completion scheduling accepted words one day ahead.

- [ ] **Step 6: Run rating tests and verify RED**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_learning.py -q
```

Expected: route/schema failures because the rating contract is absent.

- [ ] **Step 7: Implement rating transition and endpoint**

Add:

```python
class ReviewAnswerPayload(BaseModel):
    word_id: int
    rating: Literal["again", "hard", "good", "easy"]


class ReviewAnswerRead(BaseModel):
    progress: UserWordProgressRead
```

Implement `grade_review(db, user_id, word_id, rating)` with constants for the 10-minute, 1-day,
Good/Easy initial intervals, multipliers, and caps. Validate ownership and `_is_due`, update the
progress atomically, commit, refresh, and return it. Add
`POST /{user_id}/review/answers`.

Update legacy `complete_review` to set a one-day due time and reset `review_streak`, while preserving
its request/response and existing status/weak handling.

- [ ] **Step 8: Run rating tests and verify GREEN**

Run the Task 2 focused command again. Expected: all learning tests pass.

- [ ] **Step 9: Write failing quiz integration test**

Create a progress row with future `next_review_at`, submit an incorrect quiz answer for that word,
and assert `next_review_at is None`.

- [ ] **Step 10: Run quiz integration test and verify RED**

Run:

```bash
cd backend
.venv/bin/pytest tests/test_quizzes.py -q
```

Expected: the future timestamp is still present.

- [ ] **Step 11: Reset scheduling after a quiz failure**

In the incorrect branch of `submit_answer`, set `progress.next_review_at = None` so quiz failures
join the due queue immediately. Leave correct quiz scheduling unchanged.

- [ ] **Step 12: Run backend focused and full verification**

Run:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -q
```

Expected: Ruff clean; all backend tests pass with only configured environment skips.

- [ ] **Step 13: Commit**

```bash
git add backend/app/schemas.py backend/app/services/learning_service.py \
  backend/app/services/quiz_service.py backend/app/routers/learning.py \
  backend/tests/conftest.py backend/tests/test_learning.py backend/tests/test_quizzes.py
git commit -m "feat: schedule active recall answers"
```

### Task 3: Build the reveal-and-rate review flow

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/views/ReviewView.vue`
- Modify: `frontend/src/i18n/messages.ts`
- Modify: `frontend/src/styles.css`
- Create: `frontend/tests/unit/review.test.ts`

- [ ] **Step 1: Write failing API and view tests**

Mock `getReviewWords` and `submitReviewAnswer`. Verify:

- only the Russian prompt, level, and theme render initially;
- Serbian Cyrillic/Latin, stress, details, and rating buttons are absent before reveal;
- Show answer reveals `WordCard` and all four localized ratings;
- clicking a rating posts `{word_id, rating}`, disables duplicate submission, then advances;
- the last successful rating shows the completion state;
- a rejected POST followed by `GET /review/status/{word_id}` returning `is_due: true` keeps the
  revealed card and error in place, including when a capped review queue could omit the word;
- a rejected POST followed by `GET /review/status/{word_id}` returning `is_due: false` advances as a
  reconciled success;
- a rejected POST followed by a rejected status request clears the saving state, keeps the revealed
  card, and permits a retry;
- initial loading does not flash an empty state, and focus moves to the revealed answer, next reveal
  button, and final completion status;
- Serbian UI uses localized prompt, reveal, rating, and error copy.

- [ ] **Step 2: Run the unit test and verify RED**

Run:

```bash
cd frontend
npm run test:unit -- tests/unit/review.test.ts
```

Expected: failure because the singular API call and active-recall UI do not exist.

- [ ] **Step 3: Add typed frontend API contracts**

Add:

```typescript
export type ReviewRating = "again" | "hard" | "good" | "easy";
export type LearningProgress = {
  id: number;
  user_id: string;
  word_id: number;
  status: string;
  correct_count: number;
  incorrect_count: number;
  is_weak: boolean;
  next_review_at: string | null;
  review_interval_days: number;
  review_streak: number;
};
```

Implement `submitReviewAnswer(userId, { word_id, rating })` against `/review/answers` and
`getReviewStatus(userId, wordId)` against `/review/status/{word_id}`. Keep the legacy
`completeReview` wrapper available.

- [ ] **Step 4: Implement reveal, rating, persistence, and reconciliation**

In `ReviewView.vue`, add `revealed`, `saving`, and per-card error state. Render a cue-only article
before reveal and the existing `WordCard` afterward. On rating:

1. post the rating;
2. advance only after success;
3. on failure, request the precise status of that word;
4. advance when `is_due` is false, otherwise retain the revealed card and show the error;
5. if the status request also fails, retain the same revealed card, show the save error, and clear
   `saving` in a `finally` path so the learner can retry.

Reset reveal/error state when advancing. Disable reveal/rating controls during save. Show an
announced loading state until the initial queue settles, avoid a premature empty state, and move
focus to the answer region, next reveal button, or completion status as the flow advances.

- [ ] **Step 5: Add localized copy and focused styles**

Add concise Russian and Serbian strings for the recall instruction, reveal, Again/Hard/Good/Easy
labels, rating guidance, save failure, and saving state. Add responsive `.recall-*` styles without
changing unrelated components.

- [ ] **Step 6: Run unit test and verify GREEN**

Run:

```bash
cd frontend
npm run test:unit -- tests/unit/review.test.ts
```

Expected: all review tests pass.

- [ ] **Step 7: Run complete frontend unit/build verification**

Run:

```bash
cd frontend
npm run test:unit
npm run build
```

Expected: all unit tests and TypeScript/Vite production build pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/views/ReviewView.vue \
  frontend/src/i18n/messages.ts frontend/src/styles.css frontend/tests/unit/review.test.ts
git commit -m "feat: add active recall review flow"
```

### Task 4: End-to-end coverage and durable product documentation

**Files:**
- Create: `frontend/tests/e2e/active-recall.spec.ts`
- Modify: `docs/product-state.md`
- Modify: `docs/testing/mvp-manual-test.md`
- Modify: `docs/superpowers/specs/2026-07-25-active-recall-review-design.md`
- Modify: `docs/superpowers/plans/2026-07-25-active-recall-review.md`

- [ ] **Step 1: Write a failing mocked Playwright scenario**

Seed the established localStorage user session, then mock review GET and review answer POST. At
desktop and mobile widths verify:

- Serbian answer text is absent before reveal;
- answer and rating controls appear after reveal;
- the posted rating has the expected shape;
- the next Russian prompt appears only after the response;
- loading does not flash an empty state and focus follows reveal, advance, and completion;
- maximum bounded unbroken cue/answer content at 390x844 produces no actual document-level
  horizontal overflow before reveal, after reveal, or around rating controls.

- [ ] **Step 2: Run the E2E test and verify RED**

Run:

```bash
cd frontend
npx playwright test tests/e2e/active-recall.spec.ts
```

Expected: failure until the route selectors/mocks match the completed flow.

- [ ] **Step 3: Finish the E2E fixture and verify GREEN**

Use stable accessible roles/text and the existing Vite Playwright configuration. Avoid production
test hooks.

- [ ] **Step 4: Update product-state and manual testing docs**

Document:

- reveal-first review and per-card ratings;
- the three scheduling fields, transition rules, due selection, and quiz-failure reset;
- new endpoint and migration;
- test coverage and fresh verification counts;
- full event history/FSRS as deferred scope.

Update the manual flow with hidden-answer, one Again and one Good rating, reload/due-queue, precise
lost-response reconciliation, focus, and mobile overflow checks. Align this plan and the reviewed
design with the final status endpoint and acceptance criteria.

- [ ] **Step 5: Run complete fresh verification**

Run backend and frontend checks:

```bash
cd backend
.venv/bin/ruff check .
.venv/bin/pytest -q

cd ../frontend
npm run test:unit
npm run build
npm run test:e2e
```

Expected: every command exits 0; only documented environment-dependent backend skips remain.

- [ ] **Step 6: Commit**

```bash
git add frontend/tests/e2e/active-recall.spec.ts docs/product-state.md \
  docs/testing/mvp-manual-test.md \
  docs/superpowers/specs/2026-07-25-active-recall-review-design.md \
  docs/superpowers/plans/2026-07-25-active-recall-review.md
git commit -m "test: cover active recall journey"
```

### Task 5: Final review and PR readiness

**Files:**
- Review all files changed from `origin/main`.

- [ ] **Step 1: Compare implementation to the design**

Read `docs/superpowers/specs/2026-07-25-active-recall-review-design.md`, inspect
`git diff origin/main...HEAD`, and check every behavior and deferred item.

- [ ] **Step 2: Run an independent code review**

Review migration safety, timezone handling, due-queue ordering, rating validation, lost-response
reconciliation, keyboard/screen-reader semantics, localized copy, and test fidelity. Fix Critical
and Important findings using a failing regression test first.

- [ ] **Step 3: Re-run the complete verification suite**

Use Task 4 Step 5 commands and record exact test counts in `docs/product-state.md`.

- [ ] **Step 4: Confirm a clean, intentional diff**

Run:

```bash
git status -sb
git diff --check origin/main...HEAD
git diff --stat origin/main...HEAD
```

Expected: clean worktree, no whitespace errors, and only active-recall design/plan/product files.
