# Active Recall Review Design

## Problem

Slovnik's review screen currently exposes the Serbian word and Russian translation at the same
time. Moving through every card and pressing Finish marks the whole batch reviewed, even when the
learner did not retrieve an answer. The product therefore records exposure rather than recall and
shows most eligible words again on a coarse daily cadence.

The strongest adjacent product pattern is a due queue paired with an explicit recall outcome:

- Anki schedules the next appearance from Again, Hard, Good, and Easy ratings.
- Busuu assigns vocabulary strength and predicts which words need practice.
- Babbel schedules vocabulary at expanding intervals.
- Duolingo provides focused mistake review instead of treating all material equally.

Spacing research supports distributed vocabulary practice, while retrieval and interleaving make
the learner reconstruct an answer instead of merely recognizing it. Slovnik can capture most of
this value with a transparent scheduler before it has enough review history to justify FSRS or
another fitted model.

## Considered Approaches

### 1. Active recall with a lightweight adaptive scheduler — selected

Show the Russian meaning first, reveal the Serbian answer only on request, then persist one of four
ratings. A deterministic interval rule provides immediate value, is explainable, and fits the
existing progress model.

### 2. Full FSRS scheduling

Store every review event and calculate retrievability, stability, and difficulty. This is more
powerful after a learner has substantial history, but it introduces algorithm and migration
complexity without enough current data to tune or validate it.

### 3. Mistake-only drill

Build a session from weak words and recent quiz errors. This is smaller, but it leaves correctly
recalled words on the existing daily cadence and does not solve passive review completion.

## Learner Experience

The `/review` route becomes an active recall flow:

1. The learner sees the Russian translation plus level and theme, but no Serbian spelling,
   stress, notes, or examples.
2. The learner attempts to recall the Serbian word and selects **Show answer**.
3. The full existing word card appears with Cyrillic, Latin, stress, notes, and examples.
4. The learner grades the attempt:
   - **Again**: the answer was not recalled.
   - **Hard**: recalled with serious effort.
   - **Good**: recalled correctly.
   - **Easy**: recalled immediately.
5. The rating is saved before the next card appears. Buttons remain disabled while saving; an API
   failure keeps the revealed card in place and offers the same ratings again.
6. After the final saved rating, the existing localized completion state appears.

The queue remains capped at 20 cards. Weak cards keep priority, then overdue/unscheduled cards are
ordered by due time and last exposure. Answer details are deliberately hidden until reveal so they
cannot become accidental cues.

## Scheduling Rules

`user_word_progress` gains:

- `next_review_at`: nullable UTC timestamp.
- `review_interval_days`: non-negative integer, default `0`.
- `review_streak`: non-negative integer, default `0`.

Newly completed words receive their first due time one day after the learning session. Existing
progress rows keep `next_review_at = NULL`; the current same-day exclusion remains the compatibility
fallback, so old words become due without a destructive data backfill.

Each saved rating updates `last_seen_at`, interval, due time, streak, weak state, and learning
status:

| Rating | Next interval | Streak | Weak state |
| --- | --- | --- | --- |
| Again | 10 minutes (`interval = 0`) | Reset to 0 | Mark weak |
| Hard | 1 day | Reset to 0 | Unchanged |
| Good | 2 days initially, then `interval × 2`, capped at 180 days | +1 | Clear weak |
| Easy | 4 days initially, then `interval × 3`, capped at 365 days | +1 | Clear weak |

Three consecutive Good/Easy ratings set status to `learned`; Again or Hard breaks that consecutive
streak and other reviewed words remain `reviewing`. A wrong quiz answer marks a word weak and clears
its `next_review_at`, making it reviewable immediately. A self-rated Again answer remains scheduled
for its ten-minute relearning delay because weakness alone does not override a future due time.

The constants and transition function live in the learning service and are directly unit tested.
This version intentionally stores only current scheduling state, not a complete review-event log.

## API and Data Flow

`GET /api/learning/{user_id}/review` keeps its response shape and returns only currently due words.

`POST /api/learning/{user_id}/review/answers` accepts:

```json
{
  "word_id": 42,
  "rating": "good"
}
```

It verifies that the word belongs to the learner's current due progress, applies one scheduling
transition, commits it, and returns `{"progress": <updated progress row>}` including scheduling
fields. Unknown, unseen, or not-yet-due words return `400`.

If the rating request fails, the frontend reconciles with a fresh review GET before it offers a
retry. If the current word is absent from the refreshed due queue, the committed rating is treated
as successful and the UI advances; if it remains present, the revealed card stays in place and the
learner can retry. This makes a lost success response recoverable without adding an event table or
idempotency column. If reconciliation also fails, the card stays in place and the next retry repeats
the same POST-then-GET logic.

The existing batch completion endpoint remains available for compatibility, but the web client no
longer uses it. It preserves its request and response shapes while scheduling each accepted word
one day ahead, resetting its recall streak, and otherwise retaining the previous status/weak-state
behavior. This prevents legacy clients from creating an immediately recurring due queue.

The frontend API wrapper adds typed rating and scheduling contracts. `ReviewView.vue` owns reveal,
save, error, and progress state; the existing `WordCard` remains the single full-answer renderer.

## Migration and Compatibility

Alembic revision `20260725_0004` adds the three nullable/defaulted columns and an index on
`next_review_at`. Downgrade removes them. SQLite migration tests cover round-trip schema and legacy
row preservation; model-level tests cover defaults.

No new dependency or provider is required. Existing profiles, word progress, quiz selection, and
weak-word behavior remain valid.

## Verification

Backend tests cover:

- new-word first scheduling;
- legacy due selection and future due exclusion;
- weak-word priority;
- all four interval transitions;
- weak-state and learned-status transitions;
- quiz failures resetting a future review schedule;
- invalid, unseen, and future-due rating rejection;
- legacy batch scheduling;
- response schema and migration round trip.

Frontend tests cover:

- the Serbian answer being absent before reveal;
- reveal showing the existing word card;
- ratings being persisted one card at a time;
- navigation only after successful persistence;
- retry behavior after a failed save;
- lost-response reconciliation;
- localized rating copy and completion state.

The final gate is backend Ruff and pytest, frontend unit tests and production build, then Playwright
coverage of the review path at desktop and mobile widths.

## Deferred Scope

- Fitted FSRS scheduling and desired-retention controls.
- Review-event history, retention analytics, and workload forecasting.
- Audio or speech grading.
- Typed-answer normalization and automatic correctness grading.
- Mixing new cards and due reviews into one unified session.
