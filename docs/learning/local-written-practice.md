# Local written practice

The optional backend uses the reviewed `slovnik-written-a1` revision already published
in the local database. It does not publish or activate content on startup.

## Start the backend

Start PostgreSQL, run the existing Alembic migrations, then from `backend/`:

```sh
ENVIRONMENT=development LOCAL_PILOT_ENABLED=true .venv/bin/python -m app.local_pilot --port 8000
```

The launcher binds a real listening socket to `127.0.0.1` and gives that same socket
to Uvicorn and the practice guard. Ordinary `uvicorn app.main:app` and the current
Compose backend do not supply this evidence, so their practice routes return 404.
The flag is independent of all shadow and production release flags. All new practice
reads and writes fail closed outside explicit local environments, for non-loopback
requests/binds, forwarding headers, a missing/closed listener or unapproved origins.
macOS can expose SO_ACCEPTCONN while rejecting the query; the successful `listen()`
on the verified socket is recorded as a fallback, with the live descriptor and bind
still checked on every request.

## Contract

- `GET /api/practice/availability`: local route availability.
- `PUT /api/practice/{learner_id}/runs/{run_uuid}`: create/resume a run for an existing profile.
- `GET /api/practice/{learner_id}/runs/{run_uuid}`: resume with issued public activities/results.
- `POST /api/practice/{learner_id}/runs/{run_uuid}/next`, body `{"kind":"exercise"}`
  or `{"kind":"exposure"}`: issue next activity, or return the pending one.
- `POST /api/practice/{learner_id}/activities/{activity_uuid}/responses`, body
  `{"idempotency_key":"client-token","response":"text"}`: save once; exposure omits response.
- `POST /api/practice/{learner_id}/activities/{parent_uuid}/repair`, body
  `{"retry_id":"client-uuid","support":"cue"}` (or `reveal`/`correction`): reserve one linked
  supported retry. Preserve the UUID and support across uncertain network responses.
- `GET /api/practice/{learner_id}/activities/{activity_uuid}/feedback`: reviewed example after
  a saved response. After an error/unresolved root, first reserve revealed support; before that,
  and while a cue child is pending, answer-bearing feedback returns conflict.

The run UUID and submission token must be retained by the client across network retries.
The snapshot contains private reviewed keys; the response DTO does not. An accepted
activity is terminal. Unknown phrasing returns `unresolved`; it is retained without
scored evidence, competence or schedule credit. Exposure has no score or elicited answer.
Stopping the browser leaves the run available for later resume.

The frontend dashboard shows **Письменная практика / Pisana praksa** only when the
backend availability guard accepts its request. Direct `/practice` entry remains readable:
without a browser profile it offers `/?next=practice`, and successful profile selection
returns to practice. With a profile it checks availability before creating/resuming a run;
a disabled pilot explains the state and offers retry and textbook reading. Backend API
guards still reject every disabled or unsafe practice request. The view saves a separate versioned per-learner run pointer and an
uncertain first submission in sessionStorage; old quiz-result storage is untouched.
After a network failure, reload or retry sends the same answer and idempotency token.
Stopping returns to the dashboard; reopening resumes the last issued activity/result.
Task instructions remain the reviewed Russian text; controls support Russian and Serbian.

The first result remains visible separately from assisted practice. Showing an example after an
error reserves a reveal child before disclosing the answer, including across reload. An unresolved
parent is not relabeled by its child's result. A shown answer alone has no success event. The
existing v1 projection/memory weighting remains unchanged; use the evidence diagnostic when
separating supported repairs from independent recurrence.

## Workload and sessions

New runs use `local-written-selector-v2` and `written-local-budget-v2`. The fixed defaults allow
at most eight issuances/allocation period: six root tasks, two previously unseen targets and two linked repairs.
Only four reviewed practice contexts exist, so these ceilings do not promise eight tasks. Heldout
probes are disabled. Profiles default explicitly to UTC; settings accept an IANA timezone.
Legacy word batch size does not set pilot limits.
Issuance, including pending tasks and exposure, consumes capacity across every local run of the
profile. Prior-period pending tasks can still be answered; they do not consume the new period's issuance cap.
Same-context additional practice is labeled as familiar rather than new, and does not prove transfer.

Use **Новая сессия / Nova sesija** after a no-activity reason to receive a new run UUID. This preserves
the old history and does not reset daily caps. Old v1 runs remain readable and their issued answers
can be submitted, but new issuance returns `policy_retired`; already-issued retries remain valid.
Successful selection reasons and allocation are pinned in snapshots; stopped selection records a
bounded reason in diagnostics without learner answers. Review these default ceilings in usability
sessions rather than interpreting them as validated learning or time estimates.

### Timezone changes

Requested and effective zones are separate. A change starts at the first existing boundary in the
requested zone at or after the current allocation end. Until then the original start stays frozen
and the period may extend beyond one day. Repeating the same request is idempotent; replacing a
pending request or returning to the old zone never shortens that period or resets consumption.
The dashboard shows the effective zone and pending activation UTC instant; practice shows the
exact window end and remaining counts. No browser timezone is detected automatically.

Daily quiz prioritization and weekly Monday boundaries use the effective zone. All three legacy
review checks share its local day for unscheduled historical rows; scheduled due instants and
review interval durations stay UTC. New issuance snapshots pin calendar policy, zone and exact
UTC allocation bounds. Old snapshots and previous totals are not rewritten. DST day length and
skipped/ambiguous midnight are resolved through the IANA database, bundled via `tzdata` as a fallback.
Actual participant workload and active minutes remain unmeasured before the feasibility pilot.

Only four practice contexts are issued. The form maps to COMPLETE; other original
contextual tasks map to TRANSFORM. They are not modified to manufacture operation
coverage. RECOGNIZE/RETRIEVE need a later reviewed Sense pack. Four assessment contexts
are reserved for a separately consented delayed-probe protocol.

## Local retention boundary

Current engineering checks use disposable databases and fictional profiles/answers.
Do not collect research participants' responses before the P1-09b consent and probe
protocol is frozen. A model review cannot supply participant consent or human ratings.

Proposed local pilot retention is 35 days after the last planned observation, with earlier
withdrawal deletion on request. This is an operational default for review, not a public
legal policy. There is no automatic deletion job. The local deletion procedure below is
verified; before human use P1-09b must freeze consent, minimized export, copy deletion and
observer contact records. Until then, use test data only.

Keep existing PostgreSQL volumes and legacy profiles/histories intact. Deletion of a
disposable test database is separate from deletion of real pilot records. Do not use
`docker compose down -v` as a participant deletion procedure.

### Local operator deletion

Stop collection and close the participant's browser. Confirm the exact database/profile and
the local pilot opt-in; first inventory without mutation:

```bash
cd backend
LOCAL_PILOT_ENABLED=true .venv/bin/python -m app.local_pilot_data 'exact-profile-id'
```

Review the returned run/activity/event/state counts. To delete that profile's local pilot
history, repeat with `--execute`. It removes local v1/v2 raw events, activities/runs and their
neutral derived target states in one transaction. It preserves the profile, legacy quizzes,
vocabulary/progress, catalog/curriculum and all other profiles. Repeating deletion returns zero.
Shared non-pilot target history or non-neutral baselines cause a refusal before mutation and
require a reviewed replay plan; do not bypass that refusal with manual blanket deletes.

Clear that profile's `slovnik.practice.v1.<encoded-profile-id>` sessionStorage entry so the
browser does not retain the old run pointer or uncertain answer. A stale deleted pointer fails
to resume; do not reconstruct the history. Verify zero inventory afterward. Record only the
operator action/time/counts in a private non-content log, not the removed response text.

Before collecting human data, list every research export, raw ledger, consent/mapping file
and backup copy in the restricted manifest. Apply withdrawal/expiry to those copies too;
this DB utility does not delete filesystem exports or backups. Do not restore deleted pilot
records from an old backup. P1-09b remains a gate until consent and copy handling are reviewed.

### Reproduce the real browser check

The optional check starts disposable SQLite plus actual loopback API/Vite servers, uses Chromium,
and cleans up both servers. It exercises a lost submission, resume, recorded reveal/repair,
stop/resume and forwarding rejection; ordinary e2e mocks are separate.

```bash
cd backend
SLOVNIK_RUN_BROWSER_INTEGRATION=1 .venv/bin/pytest -q tests/test_local_pilot_browser.py
```

Provide `SLOVNIK_NODE_BINARY` if Node is absent from PATH. This check needs installed frontend
dependencies and Chromium; it does not write to the configured PostgreSQL application database.
