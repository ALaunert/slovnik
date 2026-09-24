# Production identity and legacy linking (P2-01a)

Status: **blocked_external — design inventory, threat model and rehearsal contract prepared; decision not accepted**. Date: 2026-09-24. Scope: documentation only. This ADR does not enable remote access, change an API, or assert that a provider has been selected.

## Context and decision required

Today `user_id` is supplied by the browser and creates or loads a profile. It is an identifier, not evidence of control. The legacy learning and quiz routes pass it to services; internal practice services compare a run's `learner_id` with the supplied value, which is also untrusted. Vocabulary writes use a shared `X-Editor-Password`. The frontend keeps `slovnik.userId` in `localStorage`, the last quiz result in `sessionStorage`, and editor passwords in view memory. No login, authenticated session, account mapping, server revocation, or logout flow exists.

The product owner must approve, in one recorded decision, **(1)** production host and browser/API origin arrangement, **(2)** identity provider or first-party identity operator and its operational owner, **(3)** credential format and server validation contract (issuer/audience/key rotation or server session), expiry and revocation/logout semantics, **(4)** editor role authority and provisioning/revocation, and **(5)** a verifiable opt-in proof for claiming each preexisting legacy profile, including recovery/collision adjudication. An email match, matching display name, browser-stored `userId`, or knowledge of the ID is insufficient proof. The owner must also identify who can review claim disputes and operate the provider. Until that decision, implementation details and production rollout are blocked.

P2-02a separately decides retention/deletion and backup treatment. Public learner history requires P2-01b ownership enforcement, P2-02 lifecycle approval and their release checks. Local supervised practice still has its separate actual-loopback gate.

## Design constraints for the subsequent P2-01b implementation

1. A validated server-side principal resolves to one authorized profile through an additive mapping. Do not treat path/body `user_id`, localStorage, or a quiz/run ID as authority. During compatibility, compare supplied `user_id` to the principal's mapped profile before any service call. Reject mismatches uniformly; never create a profile as a side effect of a rejected request.
2. Every user-scoped read and write, including reveal, review status, completion, resume, events, projections and eventual export/delete, checks the same principal. Child IDs (`attempt_id`, `run_id`, `activity_id`, `event_id`) must be checked under the resolved owner; a guessed child ID cannot bypass the route check. Server-internal jobs must use explicit trusted service authority, not a request `user_id`.
3. Editor create/update, verify and AI fill require an authenticated editor authority selected by the owner. A learner credential, old shared password alone, frontend editor state, or a fabricated role claim cannot elevate. Public catalog reads and health may remain public according to the eventual deployment decision.
4. Reject missing, invalid, expired and revoked credentials before profile lookup. Choose a validation and revocation strategy that survives key rotation, clock skew, restarts and multiple backend workers. Do not store access credentials in `localStorage`; choose browser credential storage and CSRF treatment with the approved deployment. Logout clears browser identity and cached learner-specific result/editor state and invalidates or terminates server credentials according to the approved mechanism. Back-button or another tab must not restore access.
5. Link a legacy profile only after fresh trusted login, approved independent proof of control of that specific profile, explicit confirmation of the target, and an atomic claim with uniqueness constraints/audit trail. Keep unclaimed profiles unclaimed and unavailable through guessed IDs. Collision, already-claimed, interrupted and disputed claims require a deterministic denial/recovery path. Preserve all existing rows and foreign keys; do not reassign history by email or merge two histories automatically.
6. Keep the current local legacy mode documented until replacement. Production readiness flags are attestations after controls are tested; setting them cannot substitute for authentication.

## Current ownership inventory

| Surface | Current owner key and reachable data | Enforcement point for P2-01b |
|---|---|---|
| `POST /api/profiles`, `PATCH /api/profiles/{user_id}` | Body/path string selects or creates `user_profiles`; settings returned/changed | Resolve principal before create/load/update; refuse another or unclaimed ID |
| Six `/api/learning/{user_id}` routes | `user_word_progress`; new-word, review/status, per-answer and batch writes; reads may create profile | Resolve principal before service; require owner for read and mutation |
| Four `/api/quizzes/{user_id}` routes | `quiz_attempts` and child `quiz_answers`; service checks attempt against supplied ID | Resolve principal first, then check attempt belongs to profile for answer, reveal, completion |
| Internal practice/history (no public router currently) | `practice_runs.learner_id`, child activities/events, `learner_target_states.learner_id`; shadow writes from legacy routes | Any future direct route checks principal and run/activity/event ownership; shadow inherits authorized legacy owner |
| Vocabulary editor | Global `vocabulary_items` and AI generation store; shared password header | Authenticated editor role on create, update, verify, AI fill |
| Vocabulary read and health | Global catalog and health, no learner rows | Explicit public policy; ensure responses contain no personal records |

The row and route inventories are encoded in [the ownership matrix](../testing/identity/route-ownership-matrix.json). The expected HTTP cases there are an executable test specification for P2-01b; they do **not** pass against the current unauthenticated code.

## Threat model and required tests

| Attack or failure | Required behavior after P2-01b | Test IDs |
|---|---|---|
| Guess a legacy `user_id` or vary casing/encoding | No claim, read, creation or mutation without authenticated mapped owner | `anonymous`, `foreign`, `guessed-id` |
| Use another learner's path/body ID or child attempt/run/activity ID | Deny before data access, including status and answer reveal; no cross-user side effect | `foreign`, `foreign-child` |
| Replay expired, revoked or logged-out credentials | Deny before lookup; verify clock/rotation and concurrent tabs | `expired`, `revoked`, `logout` |
| Submit learner credential or forged editor role to editor routes | Deny all editor actions; role derives from approved authority | `learner-editor`, `forged-role` |
| Claim same profile concurrently or collide with an existing link | Exactly one atomic claim; other request denied without moving rows | `claim-race`, `claimed-collision` |
| Leave a legacy profile unclaimed | No new account can inspect or claim it by ID alone; preserve rows for policy-governed recovery/export/deletion | `unclaimed` |

Run the future route test suite against the matrix with two authenticated principals, one editor and one unclaimed populated profile in disposable PostgreSQL. Assert expected status class, owner row counts before/after, unchanged cross-user payloads and no leaked answer keys. Run expiry/revocation tests with the selected provider/session adapter; test logout in both browser tabs and a fresh request. Run every route family with both missing and other-owner credentials, not just a middleware unit test. `backend/tests/test_profiles.py`, `test_learning.py`, `test_quizzes.py` and practice/history tests are the likely extension points. `frontend/tests/unit/session.test.ts`, quiz result tests and e2e navigation should cover state cleanup. No provider-specific command can be finalized before the external decision.

## Sanitized migration rehearsal contract

[Fixtures](../testing/identity/legacy-linking-rehearsal.json) use invented IDs and aggregate counts only. They represent an unclaimed profile with progress, quiz and shadow rows; two separately owned profiles; and link collision/race cases. In a disposable populated database, P2-01b must add the account/profile mapping without rewriting `user_profiles.user_id` or the child foreign keys, compare pre/post row counts and per-owner digests, claim one profile atomically only with approved proof, and verify all unclaimed/colliding records remain untouched. Re-run the same operation to establish idempotency and test restore from a snapshot. The fixture is a design rehearsal, not evidence from deployed data or a complete production data inventory. Before migration, inspect sanitized representative production shapes and obtain the P2-02a policy for export, deletion and backups.

## Release gate and disposition

P2-01a remains `blocked_external` until the product owner records the five choices above and the ADR is reviewed against the selected provider and deployment. P2-01b then implements and passes the matrix, migration and frontend tests. Production trusted-identity readiness must remain false until that evidence exists; the independent lifecycle gate must also pass. This ADR does not authorize changing `LANGUAGE_ASSISTANT_SHADOW_TRUSTED_IDENTITY_READY`, exposing direct practice routes, or remote enrollment.

Design verification on 2026-09-24: `python3 docs/testing/identity/check_matrix.py` passed against all 20 current FastAPI routes and seven synthetic claim scenarios; `git diff --check` passed. These checks validate inventory and artifact syntax, not access control.
