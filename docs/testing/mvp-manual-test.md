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
