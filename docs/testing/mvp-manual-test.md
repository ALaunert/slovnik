# MVP Manual Test Script

## Setup

- Start Postgres with `docker compose up -d postgres`.
- Run migrations with `cd backend && alembic upgrade head`.
- Start backend with `cd backend && uvicorn app.main:app --reload`.
- Start frontend with `cd frontend && npm run dev`.

## Scenarios

1. Create or load `learner-1`.
2. Add at least 8 A1 vocabulary words through the editor.
3. Complete daily new words for `learner-1`.
4. Complete review for `learner-1`.
5. Fail one daily quiz answer and confirm the word becomes weak.
6. Create or load `learner-2` and confirm progress is separate.
7. Reopen with `learner-1` and confirm progress is still server-backed.
8. Start weekly quiz and answer the weak word correctly.
9. Confirm the weak word is removed from the weak list.
10. Check mobile width at 390px and desktop width at 1280px.

## AI Fill

1. Open `/editor`, verify the AI block is hidden, unlock with the editor password, and confirm the block appears.
2. Generate a complete draft and confirm returned fields patch the form. Generate a controlled partial draft, confirm empty required fields are highlighted, complete them manually, and save.
3. Change existing form values, apply AI fill, choose restore, and confirm all previous values return.
4. Trigger a timeout or technical error and confirm a toast appears without changing any form field.
5. Request the same controlled word twice. Confirm the stored result is reused without a second OpenAI request and the UI uses neutral copy that does not claim a fresh generation.
6. Request a word already in vocabulary. Confirm the duplicate message includes an explicit edit button, does not overwrite the form, and does not navigate until the button is selected.
7. Repeat AI fill on both `/editor` and `/editor/:id`. On edit, confirm the current word is excluded from duplicate matching while a different matching word still returns the duplicate flow.
8. Remove `OPENAI_API_KEY` from the backend environment and request an uncached word. Confirm the not-configured error is shown and browser requests, source, storage, and logs do not expose a key.

## Stress And UI

1. Manually enter aligned middle-dot syllables in Cyrillic and Latin, for example `ра·ди·ти` and `ra·di·ti`, select the stressed syllable, and confirm the full syllable is emphasized in the editor preview.
2. Save the word and confirm the same full-syllable emphasis in the vocabulary list and in both new-word and review cards.
3. Save a word with only legacy `stress_marker` data and confirm it appears as metadata without guessed syllable emphasis.
4. Run AI fill, duplicate, partial-result, error, undo, and structured-stress checks with both Russian and Serbian UI copy.
5. Repeat the editor checks at 390px width and confirm controls, required-field highlighting, messages, and stressed text remain readable without overlap or horizontal clipping.
