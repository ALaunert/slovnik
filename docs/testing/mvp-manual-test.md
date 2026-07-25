# MVP Manual Test Script

## Setup

- Start Postgres with `docker compose up -d postgres`.
- Run migrations with `cd backend && alembic upgrade head`.
- Start backend with `cd backend && uvicorn app.main:app --reload`.
- Start frontend with `cd frontend && npm run dev`.
- Set `OPENAI_API_KEY` only in the backend environment for live generation. Restart the backend
  after adding, removing, or changing the key.

## Scenarios

1. Create or load `learner-1`.
2. Add at least 8 A1 vocabulary words through the editor.
3. Complete daily new words for `learner-1`.
4. Complete the active-recall review checks below for `learner-1`.
5. Fail one daily quiz answer and confirm the word becomes weak.
6. Create or load `learner-2` and confirm progress is separate.
7. Reopen with `learner-1` and confirm progress is still server-backed.
8. Start weekly quiz and answer the weak word correctly.
9. Confirm the weak word is removed from the weak list.
10. Check mobile width at 390px and desktop width at 1280px.

## Active Recall Review

Prepare at least two due words for `learner-1` (wait until their scheduled time or use existing
legacy/due progress), keep the second word at interval `0`, then open `/review`.

1. Confirm loading appears while the queue is fetched and the empty state does not flash.
2. On the first card, confirm the Russian cue, level, and theme are visible while both Serbian
   spellings, stress, notes, examples, and all rating buttons are absent.
3. Select **Показать ответ**. Confirm the full answer and four ratings appear, and keyboard focus
   moves to the answer before the rating group.
4. Rate the first card **Не вспомнил** (Again). Confirm the next Russian cue appears only after the
   request completes.
5. Reveal the second card and rate it **Вспомнил** (Good). Confirm the localized completion state is
   announced and focused.
6. Reload `/review`. With the required interval-`0` setup, the Good card must be absent until its
   initial two-day interval expires. The Again card is weak but must remain absent until its
   ten-minute relearning delay expires; reload after that delay and confirm it returns.
7. Repeat at 390px width with long unbroken cue/answer metadata if available. Confirm the document
   has no horizontal scrolling before reveal, after reveal, or around the rating controls.

Optional lost-response check: with a due card revealed, use browser DevTools to wrap `window.fetch`
for one `/review/answers` request so it awaits the real successful response, restores the original
function, and then throws a simulated network error:

```js
const realFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const response = await realFetch(...args);
  if (String(args[0]).endsWith("/review/answers")) {
    window.fetch = realFetch;
    throw new TypeError("simulated lost response");
  }
  return response;
};
```

Rate the card and confirm the UI calls
`GET /api/learning/{user_id}/review/status/{word_id}` and advances when `is_due` is `false`. If the
status request also fails, the revealed card must remain retryable.

## AI Fill

Controlled partial, stored, duplicate, and timeout responses are covered without API spend by
`cd frontend && npm run test:e2e -- ai-editor-flow.spec.ts`. Use the steps below for a live smoke
test where the required data or failure condition is available.

1. Open `/editor`, verify the AI block is hidden, unlock with the editor password, and confirm the block appears.
2. Generate a complete draft and confirm returned fields patch the form. Generate a controlled partial draft, confirm empty required fields are highlighted, complete them manually, and save.
3. Change existing form values, apply AI fill, choose restore, and confirm all previous values return.
4. Trigger a timeout or technical error and confirm a toast appears without changing any form field.
5. Request the same controlled word twice. Confirm the stored result is reused without a second OpenAI request and the UI uses neutral copy that does not claim a fresh generation.
6. Request a word already in vocabulary. Confirm the duplicate message includes an explicit edit button, does not overwrite the form, and does not navigate until the button is selected.
7. Repeat AI fill on both `/editor` and `/editor/:id`. On edit, confirm the current word is excluded from duplicate matching while a different matching word still returns the duplicate flow.
8. Remove `OPENAI_API_KEY`, restart the backend, and request an uncached word. Confirm the
   not-configured error is shown and browser requests, source, storage, and logs do not expose a key.

## Stress And UI

1. Manually enter aligned middle-dot syllables in Cyrillic and Latin, for example `ра·ди·ти` and `ra·di·ti`, select the stressed syllable, and confirm the full syllable is emphasized in the editor preview.
2. Save the word and confirm the same full-syllable emphasis in the vocabulary list and in both new-word and review cards.
3. Save a word with only legacy `stress_marker` data and confirm it appears as metadata without guessed syllable emphasis.
4. Run AI fill, duplicate, partial-result, error, undo, and structured-stress checks with both Russian and Serbian UI copy.
5. Repeat the editor checks at 390px width and confirm controls, required-field highlighting, messages, and stressed text remain readable without overlap or horizontal clipping.
