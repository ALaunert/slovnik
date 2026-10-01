# Slovnik Product State

Last audited: 2026-10-01 (grammar textbook, practice entry and learner-local days; Compose setup verified: 2026-09-24; core runtime audit: 2026-08-27)

## Product Summary

Slovnik is a Serbian learning app for Russian-speaking learners. It has a FastAPI backend, Postgres persistence, Alembic migrations, and a Vue 3/Vite frontend. The app supports a bundled grammar textbook, lightweight `userId` profile access, a shared vocabulary pool, per-user learning progress, daily new-word and review sessions, daily and weekly quizzes, weak-word tracking, a password-gated vocabulary editor with manual and AI-assisted fill, and Russian/Serbian UI copy.

This audit reflects the current product implementation, including AI vocabulary fill and
reveal-first active recall, built on the MVP delivered in PR #1, "Serbian vocabulary trainer MVP."

## Language Assistant Foundation

- On 2026-08-26, Domain Model v0.1 was approved for evolving Slovnik from separate vocabulary,
  review, and quiz modes into an adaptive language-learning assistant.
- The approved direction is a modular monolith with four bounded contexts: Language Catalog,
  Curriculum, Practice & History, and Learner Progress. The next-activity orchestrator combines
  curriculum constraints, learner evidence, and memory risk; it is not an AI chat agent.
- AI may later provide candidate exercises or evaluate ambiguous answers through replaceable ports.
  It cannot own curriculum progression, select learning truth, or update learner state directly.
- The backend foundation is implemented as a modular-monolith addition: typed contracts, four
  context-owned domain modules, reversible persistence, immutable evidence, replayable learner
  projections, curriculum publication/frontier services, and a deterministic next-activity selector.
- `VocabularyItem`, `UserWordProgress`, the existing review scheduler, quizzes, routes, responses,
  and frontend remain the authoritative public product behavior.
- Feature-flagged learning and quiz adapters can atomically shadow accepted legacy interactions into
  domain runs, activities, events, and learner projections. The flag is off by default.
- Shadow next-activity comparison is diagnostic only: it cannot change selection, learner state, or
  legacy responses. Daily new-word and review reads invoke it in an isolated read session using the
  first authoritative result (`NEW`, `DUE`, or `WEAK`) or `NONE`; failures remain isolated.
- Catalog bootstrap is creation-only. Each bootstrapped Form stores a canonical source fingerprint;
  shared learning/quiz mapping rejects missing, ambiguous, and stale content before evidence writes.
  `python -m app.catalog_audit` reports only affected legacy word IDs.
- Quiz shadow enrollment is per attempt. Attempts started while the flag was off remain legacy-only;
  answer/event drift abandons a linked run with the fixed `quiz_shadow_enrollment_gap` diagnostic
  and does not block legacy quiz behavior.
- Production shadow enablement is rejected unless both data-lifecycle and trusted-identity release
  gates are explicitly true. Those policies and real authentication remain deferred.
- The approved design and its explicit deferred log are in
  `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` and
  `docs/progress/domain-model-v0.1.md`.
- A formally accepted ADR and backend-only foundation SDD were added on 2026-08-26 and implemented
  through gates G1–G4 on 2026-08-27 using three context-owned workstreams plus one integrator.
  A strong implementation-level audit is recorded in `docs/progress/document-audit-2026-08-26.md`;
  initiative-wide status and mandatory follow-ups are tracked in `docs/progress/PROGRESS.md`.

## Learning Research and Proposed Roadmap

- The documentation-only [Serbian A1–B1 research package](learning/research-a1-b1/README.md)
  dated 2026-09-25 maps 36 topics to source locators and includes 72 model-draft examples,
  three short cited error fragments, and editorial gaps/handoff criteria. It provides internal
  research inputs, not an approved course or implementation plan; no example is publication-ready,
  and linguistic, translation, variant and rights reviews remain pending. It changes no app behavior.
- A 2026-09-25 [solo development readiness decision](learning/solo-development-readiness.md)
  removes external Serbian-teacher approval as a planned release dependency. P0 engineering
  preparation can start independently of lesson publication. A narrow written pilot still needs
  recorded source-based internal content and rights decisions; this does not constitute
  independent language validation or a CEFR attainment claim. No app behavior changed.
- A documentation-only learning audit on 2026-09-24 cross-checked the public trainer and internal
  foundation against code and researched language-learning evidence and Serbian resources.
  Start with [the current-system audit](learning/audit.md) and [prioritized roadmap](learning/roadmap.md).
- Supporting documents cover [research and evidence confidence](learning/research.md),
  [Serbian resources and release-specific licenses](learning/serbian-resources.md),
  [the proposed learning model](learning/learning-model.md), and
  [the proposed content pipeline](learning/content-pipeline.md).
- The proposal preserves the four-context foundation and prioritizes trustworthy assessment,
  source provenance and reviewed communicative content before a small written A1 pilot.
  Corpus ingestion, revised readiness rules, contextual practice and outcome evaluation remain
  proposed work; this audit implements none of them and does not supersede the accepted ADR.
- The follow-up [learning review](learning/review.md) corrected P0 dependencies and narrowed
  P0 to evidence definitions, quiz integrity, file-backed provenance/pilot contracts and
  read-only diagnostics. The [P0 implementation plan](learning/implementation-plan.md)
  recommends P0-01 first. Separate example tables, corpus/lexicon imports and a new readiness
  policy require demonstrated need or pilot evidence; none is implemented by this review.
- P0-01 now has a [learning evaluation contract](testing/learning-evaluation.md) and six synthetic
  [fixture histories](../backend/tests/fixtures/learning/p0_01_histories.json) with checked totals.
  They define denominators, missingness and first-response/retry separation for later work; no
  metric reporting, learner evidence backfill or product behavior was added by P0-01 itself.
- P0-07 has an unpublished [four-task written pilot draft](../content/curricula/a1-pilot/written-manifest.json)
  and [editorial brief](../content/curricula/a1-pilot/brief.md). Each proposed outcome separates
  practice from assessment families and records a bounded rubric, script conditions and CEFR
  locator. All crosswalks and soft sequencing are hypotheses; no curriculum is activated.
- P0-04 adds a versioned [file source/rights manifest](../content/sources/written-pilot-manifest.json) and
  `app.content_provenance` validation for medium-specific use, release/checksum pins,
  attribution and recorded review. The checked-in pilot source is analysis-only with unknown
  publication rights; this is not a legal clearance or an approval of legacy content.
- P0-05 adds eight [draft example/answer fixtures](../content/curricula/a1-pilot/examples.json),
  a file validator for target spans, references, NFC and practice/assessment leakage, and an
  [editorial decision](../content/curricula/a1-pilot/examples-decision.md). Publication validation
  intentionally fails pending item-level language, translation and rights review. Existing
  embedded catalog examples and immutable activity snapshots suffice for these fixtures;
  independent example persistence remains conditional on demonstrated reuse or withdrawal.
- P0-02 stores immutable private keys in newly issued quiz-plan JSON (`answer_key_version=1`)
  for choice, typing (both scripts) and self-check reveal. The start response exposes only
  prompt/options; grading, reveal and corrections use the issued key. Locally issued
  `plan_version=2` keys remain readable after integration with PR #6. Unkeyed historical plans
  retain legacy semantics; unknown/ambiguous key versions reject. No old plan or answer was
  rewritten, and shadow catalog-freshness checks remain in force.
- P0-08 removes the forced non-first correct choice, deduplicates Russian choice labels after
  NFC/whitespace/case normalization, and omits a choice question with fewer than two distinct
  labels. Typing and self-check remain available in sparse pools; actual issued count drives
  completion. Distinct labels are not proof of semantically distinct distractors.
- P0-03 adds a quiz completion breakdown for frozen-key plans: objectively scored first answers,
  objective items corrected on retry, and first self-check remembered ratings. The existing
  `score/total_questions` remains a mixed practice result, now labelled as such in both UI
  languages. Old cached/legacy-key results show an unavailable breakdown; zero eligible
  objective questions show “not measured.” No historical answer or score is rewritten.
- P0-06 adds an internal [read-only evidence diagnostic](testing/evidence-diagnostics.md)
  that classifies supported, repaired, self-reported, exposure and unknown observations
  using recorded event/activity facts. Existing shadow snapshots cannot establish complete
  support timing or independent context lineage, so the diagnostic does not alter projection
  v1, next-activity selection or the legacy review scheduler.
- P1-04a adds a caller-owned curriculum publication transaction and a file-backed content
  publication service. Preflight reports proposed IDs and rejects missing or retired targets,
  hard-edge cycles, unresolved source permissions, language/translation/answer-policy review,
  catalog examples without an exact reviewed text/translation match (including examples
  linked to existing form targets), inconsistent references and stale or ambiguous legacy
  mappings. Approved catalog inserts and curriculum activation
  commit together; failures roll both back. Exact concurrent repeats return the same active
  revision; an active repeat containing new catalog IDs is rejected. Changed content under an
  existing catalog ID is rejected, so a correction needs a new reviewed ID.
  The READ COMMITTED preflight also rechecks catalog absence when a concurrent identical
  publisher's active version becomes visible, so that exact repeat remains idempotent;
  genuinely new IDs and changed content under an active version still reject.
  No pilot pack was published or activated, and there is no new HTTP route or content table.
- The [P1 written brief decision](../content/curricula/a1-pilot/brief-decision.md) checked the
  four proposed task boundaries against the Council of Europe Companion Volume. It retains
  separate holdout families but does not approve the eight fixture examples: price fixtures
  lack the two-item lookup, and personal/location fixtures do not yet perform their stated
  written tasks. Display rights and item-level Serbian/Russian/answer reviews remain unresolved.
- P1-03a preparation adds a separate [eight-candidate written bank](../content/examples/a1-written-v1.json)
  and [review/decision journal](../content/examples/a1-written-v1-decision.md). Internal model
  source checks cover selected Serbian forms, Russian meanings, finite answer sets and distinct
  task contexts. This does not approve the P0 fixtures or establish independent language quality.
  The project owner accepted all eight and permitted their original text and separately authored
  Russian translations for local `pilot_display`; approval binds the exact bank and rights digests.
  Publication validation passes; no pack is activated. The owner accepted closing P1-03a on
  2026-09-30 despite unmeasured editorial time. Counts are recorded, but per-review-hour rates
  are unavailable and no editorial-efficiency claim is made.
- Example schema 2 retains the original/display text, source item/revision identity, hashes,
  contextual task, register, private-data declaration, duplicate cluster and separate editorial
  decisions. The shared publication validator checks keys, script equivalence, cluster separation
  and source pins. Its owner decision binds the exact bank and rights digests. A read-only CLI
  checks retained prior exports and emits a deterministic review document; it does not import,
  approve or activate content. Schema-1 fixtures keep their existing semantics. Unlisted plausible
  answers remain unresolved; this task adds no learner-facing scoring, route or table.
  A bank contains one current revision per source item; malformed task/review fields and conflicting
  source identities are rejected before export. Analysis checks the bank checksum, while release/
  pinned-checksum consistency remains a publication gate, not an analysis/export gate.
- P1-03b's persistence trigger was checked against the new candidate bank: no independently
  governed cross-target reuse/withdrawal is demonstrated. File revisions and embedded catalog
  examples remain sufficient; P1-03b is closed as not triggered, with no new table.
- P1-04b has a [prepared local publication revision](../content/curricula/a1-pilot/publication-v1.json)
  and [coverage decision](../content/curricula/a1-pilot/publication-decision.md) for four written
  outcomes and eight approved examples. A read-only loader pins the brief, bank, rights, source,
  answer policies, families and soft edges, then maps editorial target keys to stable catalog UUIDs
  without changing the approved bank. Catalog constructions embed practice examples only;
  assessment items remain in the bank and publication preflight rejects their catalog exposure.
  Catalog IDs include their revision, while node/edge IDs include the curriculum version; a
  corrected catalog item can receive a new ID and a later revision can restore an older target.
  Preflight rejects reused construction codes before database insertion.
  Atomic/idempotent publication passed in disposable SQLite and PostgreSQL tests. After a clean
  preflight on the previously empty local PostgreSQL database, `slovnik-written-a1` revision 1
  was activated with four catalog constructions. An independent read found four practice examples
  and no assessment text in catalog; an exact repeat was idempotent. P1-04b is complete for this
  local database. No learner-facing practice route or remote data access was enabled.
- P1-05a has a pure server-side bounded evaluator. It reads unchanged reviewed example
  hashes and versioned answer-policy IDs, checks the pinned target span and primary capability,
  and returns correct/incorrect/unresolved with a bounded reason. It applies NFC and outer trim
  to phrases; case, inner spacing, punctuation and diacritics in values stay significant. Form
  field labels are matched as case-insensitive identifiers across the two scripts, while field
  values remain finite. Only explicit cross-script aliases and reviewed per-field values are
  accepted; empty answers, missing
  required form values and wrong bare price numerals have narrow incorrect verdicts. Other
  variants remain unresolved. The [internal answer-case review](../content/examples/a1-written-v1-answer-label-review.md)
  and frozen fixture cover 20 constructed cases. On 2026-09-30 the owner directed an internal
  check without post-by-post owner labels; the fixture explicitly says `human_gold: false`.
  Its false-accept/reject counts are engineering diagnostics, not human-validated performance.
  The bounded engineering scorer is complete under the owner's internal-check direction,
  with this explicit deviation from the original human-gold acceptance criterion. The
  evaluator is not called by an HTTP route or existing quiz flow.
- Authentication work is outside the current scope by owner decision on 2026-09-30. Existing
  learner routes still trust caller-supplied `user_id`; the shared editor password is not an
  individual identity. Remote learner histories and public practice remain blocked until a
  later trusted-identity and lifecycle decision. No auth runtime or release-flag change was made.
- P1-05b adds an opt-in local practice API over the existing run/activity/event tables and
  deterministic selector. Client-assigned run UUIDs resume idempotently; next returns an existing
  pending activity; submit retains the first answer and rejects conflicting idempotency reuse.
  Snapshot revision 2 pins the pack, bank/rights digests, source release/checksum/attribution,
  reviewed example/hash/policy, context family, target span, capability, operation and support.
  Public DTOs use a field allowlist and omit private keys; grading uses the issued snapshot even
  after current files disappear or catalog content is retired. New issuance requires the exact
  active reviewed revision and unchanged published catalog content. Each of the four practice
  items is issued at most once per run; assessment families remain held out.
  The reviewed Construction pack supports COMPLETE (form) and TRANSFORM (other contextual
  tasks), plus non-scored exposure. RECOGNIZE/RETRIEVE remain generic domain operations;
  their live issuance requires reviewed Sense targets and keys. This bounded acceptance
  deviation was checked by Astra under the owner's autonomous-review direction; it is an
  internal model review, not human language validation.
- New deterministic `unresolved` evidence is retained without competence, memory or scored
  evidence credit. Legacy partial and self-report behavior is unchanged; no historical replay
  or schedule rewrite was performed.
- All new practice reads/writes require `LOCAL_PILOT_ENABLED=true`, explicit local/development/test
  mode and a live loopback listener supplied by `python -m app.local_pilot`. The launcher passes
  that same socket to Uvicorn with proxy headers disabled. The guard also checks actual request
  endpoints and rejects forwarding headers and origins outside configured CORS origins.
  Ordinary Uvicorn/Compose startup has no verified listener and fails closed for practice.
  Local retention and test-only use are documented in [the local practice guide](learning/local-written-practice.md).
  The P1-05c frontend below uses these routes; a human-data collection protocol remains deferred.
- P1-05c adds a backend-gated `/practice` view and optional dashboard entry. It renders public
  written tasks and non-scored presentations; generic choice/text rendering retains the four
  operation values, while this reviewed pack still issues only COMPLETE/TRANSFORM. A separate
  version-1 sessionStorage key per learner retains the run UUID and an uncertain submission's
  token/first answer across refresh. Network retries send that same answer/token; resumed
  terminal results reconcile a response already saved by the server. No private key is stored
  in browser state. Stop returns to the dashboard while preserving resume, and empty/unresolved
  states avoid mastery claims. Controls have Russian/Serbian copy; reviewed task instructions
  remain Russian for the defined learner group.
  Before first issuance the learner chooses an exercise or unscored example. A failed resume
  offers reload even when an uncertain submission is already retained, preserving its token.
- P1-06a/P1-06b add one immediate linked repair after an incorrect or unresolved response.
  The parent's immutable snapshot and first result are retained. The child pins cue/reveal/correction
  support before its answer; duplicate issuance and submission reuse the original IDs. Revealing
  an answer after an error first reserves a reveal child; feedback with an answer is withheld
  before that reservation and while a cue child is pending. This prevents unrecorded disclosure.
  A reveal without a submitted answer creates no scored event. An unresolved parent stays unresolved
  even if a supported child is accepted. The read-only diagnostic excludes same-context repairs
  from independent recurrence. Projector/memory v1 still retain their previous supported-response
  behavior pending P2-08; their heuristic counts are not independent success or mastery.
  The UI distinguishes the original result, help and repair, preserves uncertain repair UUID/support
  across refresh, and shows only the unchanged reviewed instruction/example. Later opportunity
  uses the existing memory schedule; no new readiness or scheduling rule was introduced.
- P1-08a/P1-08b introduced `local-written-selector-v2` with `written-utc-budget-v1`, superseded
  for new issuance by P2-03's local allocation windows. Fixed ceilings remain eight total, six root
  activities, two new targets and two repairs per allocation; delayed probes remain disabled.
  Actual reviewed content offers at most four root contexts per allocation.
  Pending/exposure issuances count across all local v1/v2 runs of the profile, separately
  from legacy batch size. Profile then run locks serialize issuance and submission on PostgreSQL.
  A pending activity is returned before checking current caps; an already-issued response can
  be completed later. Repair repeats reuse their UUID before enforcing new-issuance caps.
  Newly shown targets get a valid first opportunity ahead of due/weak backlog; familiar exposure
  or unresolved contexts are not relabeled new. Invalid higher-priority intent groups fall back
  to valid lower groups only in the versioned local policy. Reasons and workload policy are pinned
  in the issued snapshot; no-activity reason codes also produce a content-free diagnostic log.
  Each practice example is issued at most once per run and allocation window (excluding its linked repair).
  Familiar ASSESS remains practice, not a heldout probe. Old v1 runs remain readable/submittable
  but cannot issue fresh roots or repairs. Legacy/default selector and memory/readiness remain unchanged.
  The UI shows issuance counts and remaining ceilings, with explicit window/content limits, stop/resume
  and new-session controls. Definite repair rejection clears its pending pointer and reconciles server
  state; uncertain failures retain the UUID/support. Both locales describe legacy new-word count as
  batch size. Allocation values are engineering defaults awaiting usability evidence, not research facts.
- P1-09a verifies the opt-in written flow through actual loopback API/Vite servers and Chromium,
  using a disposable database and fictional profile. The module launcher uses the canonical
  imported listener class; running it as `python -m` now satisfies the same guard used by routes.
  The test covers a lost request, frozen answer resume, recorded reveal/repair, stop/resume and
  forwarding rejection. Ordinary startup/flag-off still hides practice and preserves legacy behavior.
  A local-only operator CLI inventories by default and requires `--execute` to remove one profile's
  local pilot runs, activities/events and exclusively neutral derived states atomically. It preserves
  profiles, legacy quizzes/vocabulary/progress and other learners; shared non-pilot target history
  or non-neutral baselines refuse before mutation. PostgreSQL linked-repair deletion was verified.
  Retention, browser pointer cleanup and separate export/backup-copy handling are documented in
  the local guide. This is not public erasure/retention enforcement or consented human collection;
  P1-09b must still freeze the protocol, contacts, consent and exports before research use.
- P1-09b has an internally reviewed [protocol preparation](testing/written-pilot-protocol.md).
  It prespecifies twelve adult local participants, counterbalanced two-target 7-day/two-target
  28-day assignment so each of the four heldouts appears only once per participant, verified-contact
  windows, feasibility/burden thresholds, missingness and a blinded two-scale rubric. An uncontrolled
  feasibility study has no estimable comparative effect threshold. A separate observer ledger is
  required because DB response times do not prove latest contact or all feedback displays.
  Version-2 engineering exports include explicit response kinds and records/enrollment digests,
  a minimized allowlist and private files; human registries reject. The separate pure observer-ledger analyzer
  reconciles all six P0 truth histories, preserves duplicate/missing/unresolved distinctions and uses
  verified display/response/support chronology for context independence and elapsed windows.
  Export deletion refuses unknown files and symlinks; it does not remove other copies or DB records.
  The joint file-only builder now verifies frozen twelve-slot counterbalance, exact reviewed
  content/rights/policy/protocol pins, consent times/scopes and source/observer first-response
  consistency. It preserves unknown support/history, missing versus empty/unresolved responses,
  per-probe eligibility reasons and workload windows. One heldout per participant/target is allowed;
  earlier or additional linked displays cannot hide exposure/help, and known pre-response heldout
  exposure is reported as an incident. Source export/observer inputs and the original reviewed
  bundle/protocol must be retained for reproducibility; hashes prove file consistency, not DB origin.
  A separate random-ID shuffled blind packet and retained private mapping omit identity/horizon,
  automatic verdicts and keys. Two-rater synthetic score checks retain missing pairs, disagreement
  and separate adjudication; they never write product events or report real human agreement.
  New private output bundles have eight recognized files, input/file digests, verification and
  bounded removal; old copies/inputs/backups require separate inventory/deletion. Withdrawal
  invalidates old enrollment hashes and excludes linked rows from rebuilt outputs without reusing
  slots. Free-form answers are not automatically anonymized; custodian review remains necessary.
  This is completed synthetic engineering preparation, not enrollment approval: real consent/
  retention/custodian review and real blinded human agreement remain open.
  P1-09b/P1-09c are incomplete;
  no participant observations or ratings were manufactured.
- P2-03 adds a validated IANA timezone preference with explicit UTC fallback for old profiles.
  Daily quiz prioritization, local Monday quiz scope and all three unscheduled-review checks share
  the effective calendar zone; scheduled review instants/durations and issued quiz keys stay unchanged.
  Written issuance uses `written-local-budget-v2`: new snapshots pin calendar policy, effective zone
  and exact UTC window. A requested change starts at a future boundary after the current allocation;
  pending replacements never shorten its frozen window or reset consumed quota. Transition windows
  can span more than one day. Dashboard shows requested/effective zones and pending activation;
  practice labels counts by period and displays the reset UTC instant. Zone detection is manual.
  Migration `20261001_0006` adds four fields without rewriting old events/snapshots; `tzdata` provides
  the IANA fallback. Legacy new-word count remains batch size, not a new daily quota. Counts are actual
  issuance; human workload comparison and active minutes await the feasibility pilot.
- P2-02a has a read-only [history lifecycle map](learning/history-lifecycle-map.md) over all eighteen
  application tables, FK/replay dependencies, browser pointers and research/backup/provider copies.
  ORM and local PostgreSQL schema agree; no database deletion cascades exist. It records a populated
  drill design and unresolved period/action matrix, preserving the bounded local pilot procedure.
  It approves no jurisdiction, retention periods or public erasure/export and deletes no real data;
  P2-02a remains open for actual policy and operational decisions.
- Remaining data gates were checked after joint research preparation: P3-02a is experiment not run,
  with no timed manual baseline, comparable manual group or independent blind human quality labels.
  Existing local display rights do not establish external-provider transmission/spend permission.
  Other conditional expansion/readiness/model tasks still require the real P1-09c study or named
  lifecycle/content gates; lack of pilot observations is not evidence that a measured gap is absent.
- Current CEFR settings are preferences/content labels, `learned` is a self-rating streak, and
  internal competence/frontier values are unvalidated heuristics. The repository does not
  demonstrate delayed learning gains, full A1 coverage or communicative proficiency.

## Implemented User-Facing Capabilities

- The grammar textbook at `/textbook` has 20 chapters in four groups (basics, nouns/cases,
  verbs, sentence), form tables, 40 original translated examples and 20 reveal-only self-checks.
  Topic search includes Russian/Serbian explanations and examples and tolerates missing Latin
  diacritics. Direct chapter links, related topics and previous/next navigation work without
  a profile or backend. Navigation, entry and dashboard expose the book. Explanations remain
  Russian when controls use Serbian; reading does not score answers or write history/progress.
  The [internal editorial journal](learning/textbook-review.md) records primary source pages,
  original layer authorship, delegated local-display decisions, source errors excluded and limits.
  Research drafts and the reserved pilot assessment situations were not republished.
- Direct written-practice entry distinguishes a missing browser profile from a disabled
  local pilot. It offers profile selection and returns to practice after successful entry;
  the `next` destination accepts only `practice`, with dashboard as the fallback. Disabled
  availability stays on an explanatory page with retry instead of a silent dashboard redirect.
  Existing saved attempts and the backend loopback guard are unchanged. Unit regression
  checks and Chromium entry/recovery/resume checks passed on 2026-10-01.

- User entry screen creates or loads a profile by `userId`; the last `userId` and UI language are stored in browser localStorage.
- Dashboard lets a learner change CEFR level, new-word batch size, UI language and timezone.
- Vocabulary list supports CEFR and theme filters, shows Serbian Cyrillic/Latin, Russian translation, level, and theme.
- Editor password unlocks add/edit controls; the editor can create and update vocabulary entries with optional register, stress, notes, examples, and example translations.
- After unlock, an editor can enter one Serbian word and apply a validated OpenAI or previously
  stored generation as a non-destructive patch. Existing vocabulary matches offer an explicit edit
  link, partial results highlight still-empty required fields, technical failures preserve the form,
  and the latest pre-fill form snapshot can be restored from frontend memory.
- Structured stress is rendered by emphasizing the full stressed syllable in both Serbian scripts
  in the vocabulary list and the shared new-word/review card. The legacy free-form stress marker
  remains metadata fallback when structured stress is absent.
- Daily new-word session selects unseen words at the learner's preferred level up to
  `daily_new_word_count` per fetch; completing another batch on the same day is possible.
  Completion records exposure and per-user progress, not an elicited recall answer.
- Review is productive Russian-to-Serbian recall: each due card initially exposes only the Russian
  cue, level, and theme; reveal shows the Serbian answer and details; and one Again, Hard, Good, or
  Easy rating must be saved before the learner advances.
- Daily and weekly quizzes use three question types: Serbian-to-Russian multiple choice, Russian-to-Serbian typing, and remembered/forgot self-check with answer reveal.
- Incorrect quiz answers mark words weak and can be repeated once per question. Quiz completion is blocked until required repeats are answered.
- Weekly quiz includes words touched this calendar week plus weak words; correct weekly answers clear weak status.
- Results page shows the mixed practice score, question and weak-word counts, mistakes and,
  for frozen-key results, separate first-answer, retry recovery and self-rating counts from
  `sessionStorage`; old cached results show the breakdown as unavailable.
- UI copy exists for Russian (`ru`) and Serbian (`sr`); the static HTML document language remains `ru`.

## Backend Architecture and API Areas

- FastAPI app assembly is in `backend/app/main.py`; CORS origins come from settings.
- Settings are in `backend/app/config.py`; placeholder `EDITOR_PASSWORD` values are allowed only for explicit local/test environments.
- SQLAlchemy session setup is in `backend/app/db.py`; Alembic uses app metadata and `DATABASE_URL`.
- Routers are thin wrappers over service modules:
  - `GET /api/health`
  - `POST /api/profiles`, `PATCH /api/profiles/{user_id}`
  - `GET /api/vocabulary`, `GET /api/vocabulary/themes`, `GET /api/vocabulary/{word_id}`, `POST /api/vocabulary`, `PUT /api/vocabulary/{word_id}`, `POST /api/vocabulary/editor/verify`, `POST /api/vocabulary/ai-fill`
  - `GET /api/learning/{user_id}/new-words`, `POST /api/learning/{user_id}/new-words/complete`, `GET /api/learning/{user_id}/review`, `GET /api/learning/{user_id}/review/status/{word_id}`, `POST /api/learning/{user_id}/review/answers`, `POST /api/learning/{user_id}/review/complete`
  - `POST /api/quizzes/{user_id}/start`, `POST /api/quizzes/{user_id}/{attempt_id}/answers`, `GET /api/quizzes/{user_id}/{attempt_id}/questions/{word_id}/{question_type}/answer`, `POST /api/quizzes/{user_id}/{attempt_id}/complete`
- Business logic lives in focused modules under `backend/app/services/`, including
  `ai_vocabulary_service.py` for duplicate/store/generation orchestration and
  `openai_vocabulary_client.py` for the Responses API adapter.
- Language-assistant services under `backend/app/services/` own catalog bootstrap, curriculum
  publication/frontier, immutable event recording, projection/replay, deterministic selection,
  shadow learning/quiz adapters, and non-authoritative comparison. Context persistence is under
  `backend/app/domain_models/` and `backend/app/repositories/`.
- Concurrent AI fills for the same normalized source are coalesced with an expiring database
  reservation. Lease timestamps come from the database clock, and acquisition lock/statement
  waits are bounded by a monotonic request deadline. The owner commits the lease before calling
  OpenAI, renews it through an independent heartbeat until validation, rechecks, fenced
  persistence, and release finish, and bounds heartbeat shutdown. Waiters reuse the stored result
  or receive a stable `503`; provider failures release the lease, stale leases can be reclaimed
  after a worker crash, and the request session holds no database transaction during the provider
  call.
- Manual vocabulary create/update accepts optional structured stress with non-empty, aligned
  Cyrillic/Latin syllable arrays, a valid zero-based stress index, and NFC-equivalent exact
  reconstruction of both Serbian spellings. The legacy `stress_marker` contract remains supported.
- `learning_service.py` owns the lightweight review scheduler and SQL due query. A singular rating
  locks the progress row with `SELECT ... FOR UPDATE`, rechecks due state while holding the lock,
  applies one transition, and commits it, so concurrent ratings cannot both apply to the same due
  state on PostgreSQL.
- `backend/app/seed.py` seeds three sample A1 words only.
- The backend has a tested, backend-only OpenAI adapter using strict nullable Structured Outputs,
  a configurable API key and timeout, and `gpt-5.6-luna` as the default model. Product errors use
  stable codes, while provider and semantic validation failures are logged with request metadata
  without logging the API key or raw source word in the adapter.

## Frontend Architecture and Routes/Views

- Vue app bootstraps in `frontend/src/main.ts`; routes are defined in `frontend/src/router.ts`.
- Routes: `/`, `/dashboard`, `/vocabulary`, `/new-words`, `/review`, `/quiz`, `/results`,
  `/practice`, `/textbook`, `/textbook/:chapterId`, `/editor`, `/editor/:id`.
- `frontend/src/content/serbian-textbook.json` is the versioned, bundled read-only book.
  `textbook.ts` provides its typed contract and topic search; `TextbookView.vue` renders the
  grouped directory and `TextbookChapterView.vue` renders explanations, tables and sample answers.
  It has no catalog/curriculum database publication, learner identity or practice API dependency.
- API calls are centralized in `frontend/src/api/client.ts`.
- Browser session state is centralized in `frontend/src/stores/session.ts`.
- Route-level views live in `frontend/src/views/`; reusable display components live in `frontend/src/components/`.
- `WordEditorView.vue` owns the AI request, partial-patch, duplicate, toast, and in-memory undo
  workflow; `StressEditor.vue` owns aligned syllable entry, selection, validation, and preview.
- `ReviewView.vue` owns initial loading/error/empty states, answer reveal, per-card saving, focus
  movement, completion, and lost-response reconciliation through the precise per-word status API.
- `frontend/src/i18n/messages.ts` contains Russian and Serbian UI strings.

## Data Model and Persistence

- Docker Compose starts PostgreSQL, FastAPI, and Vue/Vite for local development. It preserves Postgres data and frontend `node_modules` in named volumes, bind-mounts backend/frontend sources for reload, runs Alembic upgrades before Uvicorn, and leaves sample vocabulary seeding manual. Published PostgreSQL, API, and Vite ports bind to host `127.0.0.1`; the backend uses the internal `postgres:5432` address while the frontend receives only the browser-facing API URL and file-watcher setting. Tests override the DB with in-memory SQLite fixtures.
- Initial migration `20260702_0001_initial_schema.py` creates:
  - `vocabulary_items`: global word content, CEFR level, theme, optional notes/examples, timestamps.
  - `user_profiles`: `user_id`, preferred level, daily new-word count, UI language.
  - `user_word_progress`: per-user word status, seen/quizzed timestamps, correct/incorrect counts, weak status.
  - `quiz_attempts`: user-scoped quiz type, timestamps, score, total questions, serialized question plan.
  - `quiz_answers`: submitted answers per attempt/question.
- Migration `20260724_0002_ai_vocabulary_fill.py` adds nullable JSON `stress_pattern` to
  `vocabulary_items` while preserving the legacy `stress_marker`, and creates
  `ai_vocabulary_generations`. Generation records retain the source word, a unique normalized
  source key, generated JSON payload, missing required fields, model and prompt versions, and
  timestamps. Both generation JSON fields are required, and explicit Python `None` values are
  rejected.
- Migration `20260725_0003_ai_fill_reservations.py` creates
  `ai_vocabulary_generation_reservations` without rewriting the existing `0002` revision.
  Reservations use the normalized source as their primary key and retain an owner token and expiry
  for crash recovery.
- Migration `20260725_0004_active_recall_schedule.py` adds nullable `next_review_at`, non-null
  `review_interval_days` and `review_streak` counters defaulted to zero, and an index on
  `next_review_at` without backfilling legacy review dates.
- Migration `20260826_0005_domain_foundation.py` adds 11 domain tables for Language
  Catalog, Curriculum, Practice & History, and Learner Progress. It preserves all legacy rows and
  is reversible back to `20260725_0004`.
- Learning events are immutable and idempotent per learner/key. Learner target state is a replayable
  projection with explicit baseline, competence, memory-v1 and evidence cursor fields.
- A technical A1 curriculum pilot and deterministic selector exist internally. They are not a
  claim of curated A1 coverage and are not exposed by a public next-activity endpoint.
- New-word completion schedules the first review one day later. Review ratings update the current
  scheduling state as follows:
  - Again: ten minutes, stored interval `0`, streak reset, mark weak.
  - Hard: one day, streak reset, preserve weak state.
  - Good: two days when the current interval is below two, otherwise double it up to 180 days; increment the
    streak and clear weak state.
  - Easy: four days when the current interval is below four, otherwise triple it up to 365 days; increment the
    streak and clear weak state.
- Three consecutive Good/Easy ratings set status to `learned`; Again and Hard reset that streak and
  put the word in `reviewing`. An incorrect quiz answer marks the word weak and clears
  `next_review_at`, making it immediately eligible; a correct quiz answer does not alter its
  schedule.
- The review queue is filtered in SQL to `seen`, `reviewing`, or `learned` rows that are due.
  Explicit schedules are due at `next_review_at <= now`. Legacy null schedules are due when weak or
  when both first and last exposure are null or predate today. Results are capped at 20 and ordered
  by weak first, then due time (null first), last exposure (null first), and stable progress-row ID.
- `POST /api/learning/{user_id}/review/answers` rejects unknown, unseen, and future-due words with
  `400` and returns the updated progress row.
  `GET /api/learning/{user_id}/review/status/{word_id}` returns an uncapped precise `is_due` result
  for lost-response reconciliation. The compatibility batch
  `/api/learning/{user_id}/review/complete` endpoint remains; each accepted word is scheduled one
  day ahead, its recall streak is reset, and its prior weak-state and learned-state behavior is
  preserved.
- Clearing `VocabularyItem.stress_pattern` stores SQL `NULL`; JSON values are replaced wholesale
  rather than tracked for in-place mutation.
- Vocabulary content is global; profiles, progress, quiz attempts, answers, and weak-word state are scoped by `user_id`.

## Security/Access Model and Caveats

- `userId` access is not authentication. Anyone who knows a `userId` can load that profile.
- Vocabulary create/update and editor verification use the `X-Editor-Password` header compared directly with `EDITOR_PASSWORD`.
- AI fill uses the same header. `OPENAI_API_KEY` is read only by the backend and is never sent to
  or stored by the frontend.
- The editor password is a simple shared secret, not a user account or session system.
- Production startup rejects placeholder editor passwords unless `ENVIRONMENT` is explicitly local/test.
- `LANGUAGE_ASSISTANT_SHADOW_ENABLED` defaults to false. Non-local enablement also requires
  `LANGUAGE_ASSISTANT_SHADOW_DATA_LIFECYCLE_READY` and
  `LANGUAGE_ASSISTANT_SHADOW_TRUSTED_IDENTITY_READY`; configuration validation rejects unsafe enablement.
- There is no delete endpoint for vocabulary, no real auth, no roles, no rate limiting, and no CSRF/session hardening.

## Verification and Test Coverage

- Final merge integration on 2026-10-01 preserves PR #6's canonical publication service,
  request fingerprint and database/catalog guards on published lexical parents and children.
  The reviewed written-bank publisher has a separate module and fingerprint discriminator;
  changed editorial bundles reject, and pre-existing local NULL fingerprints can be pinned
  only after an exact validated repeat with a locked recheck. Canonical source/pilot manifests
  remain unchanged; the additional written contracts live in `written-pilot-manifest.json`
  and `written-manifest.json` with separate validators and tests. Synthetic baseline fixtures
  and both read-only evidence diagnostics remain available without changing projection v1.
- Additive merge migration `20261001_0007` preserves both previously deployed revision IDs
  (`20260925_0006`, `20261001_0006`). Upgrading from either executes the missing branch and
  reaches one head; regression checks retain vocabulary, progress and an explicit timezone.
  Local PostgreSQL reached `20261001_0007`; all 18 existing table counts and profile timezone
  settings were preserved. No historical key, support context or observation is reconstructed.
- Fresh integrated verification: full backend with PostgreSQL and real HTTP/Chromium passed
  (`1058 passed`, eight subtests; no skipped tests); frontend unit checks (`126 passed`),
  typecheck, production build and Chromium e2e (`15 passed`) passed. Ruff passed. The future
  identity design inventory now covers 27 routes and seven synthetic claim scenarios; this
  validates route coverage only. Authorization remains deferred, and local practice requires
  the dedicated actual-loopback launcher. Three independent Astra reviews covered core,
  publication/practice and reader/research; the delayed-probe start defect was corrected.

- Final integration review on 2026-10-01 found and fixed a delayed-probe eligibility defect:
  an answer timestamp cannot stand in for unknown task display/start. Both 7/28-day analysis
  now retains the answer while reporting unknown eligibility and excluding that denominator.
  Five RED→GREEN regressions cover missing/unknown starts and the dataset join. The existing
  synthetic P0 truth example now explicitly declares its fictional probe display; no historical
  observation was filled and its expected totals stay unchanged.
- Grammar textbook/practice entry on 2026-10-01: all frontend unit checks passed (`120 passed`),
  `vue-tsc -b`, production Vite build and all Chromium e2e passed (`15 passed`). Checks cover
  grouped reading/search with unavailable API and no profile, direct/missing chapters,
  table/reference integrity, answer reveal reset on chapter navigation, Russian content with
  Serbian controls, 390/1280px layouts, profile return allowlist and recovered pilot availability.
  Full PostgreSQL-enabled backend including real HTTP/Chromium practice passed (`929 passed`);
  Ruff and diff whitespace checks passed. Astra content/code review found one misleading search
  placeholder, corrected; no remaining material findings. Runtime API availability returned true
  with the local frontend Origin, and in-app browser reading/entry were inspected. Existing
  dependency deprecation warnings remain; no user history or unrelated files were removed.
- P2-03 on 2026-10-01: PostgreSQL-enabled full backend including real HTTP/Chromium flow passed
  (`884 passed`), frontend units (`109 passed`), typecheck/build and Chromium e2e (`9 passed`) passed.
  Seventeen calendar/profile/product checks cover 23/25-hour days, midnight gap/fold, skipped date,
  the Toronto partial-midnight gap, idempotent/pending/date-line changes, exact activation, legacy
  review/quiz consistency, quota preservation, migration and profile-lock races for next/repair.
  Fifteen non-PostgreSQL checks also passed with system timezone paths disabled, using bundled
  `tzdata`. Ruff/diff checks passed; independent reviews found no remaining material issues.
  The additive migration was applied to local PostgreSQL (`20261001_0006`); prior data were retained.
- P1-09b joint engineering preparation on 2026-10-01: all 62 focused synthetic export/ledger/
  dataset checks passed, including six P0 truth histories, balanced frozen assignment, immutable
  first responses, family/support leakage, retained blind mapping, withdrawal, rating isolation,
  private hashes/permissions, bounded removal and the operator CLI. Actual DB export was serialized,
  read back and joined without changing product events/projection. Full backend with PostgreSQL
  and real Chromium/HTTP flow passed (`929 passed`); Ruff/diff checks passed. Independent review's
  two linked-contact/incident findings were reproduced and fixed with RED→GREEN regressions and
  that full suite. P1-09b remains open for real consent/custodian review and blinded human agreement.
- P1-09a on 2026-10-01: full backend suite with PostgreSQL and the opt-in real browser check
  passed (`850 passed`); Ruff and `git diff --check` passed. The browser check reproduced the
  module-launcher listener identity defect before its fix, then passed with actual servers.
  Five local-data tests cover dry run, idempotent deletion, guarded mode/flag, non-neutral refusal
  and PostgreSQL linked repairs while retaining legacy word progress. Astra review reported no
  actionable issues. The current frontend verification remains 107 units, type/build and nine e2e
  passes; no human answers, ratings or delayed outcomes were collected.
- P1-08a/P1-08b on 2026-10-01: full PostgreSQL-enabled backend suite passed (`844 passed`);
  Ruff passed. Workload regressions cover shared pending/exposure limits, zero/exhausted budget,
  90-day absence, UTC rollover, familiar exposure, readable v1 history, valid-intent fallback,
  new opportunity ahead of due backlog, concurrent PostgreSQL runs and submit lock order.
  The duplicate-v1 issuance cap and lock-order regressions failed before their fixes. Frontend
  units passed (`107 passed`), TypeScript/Vite builds passed, and Chromium e2e passed (`9 passed`),
  including mobile/keyboard recovery, displayed daily limits and repair. Astra re-review found
  no remaining actionable issues. Human workload comprehension is still unmeasured.
- P1-06a/P1-06b on 2026-10-01: eight repair API tests cover immutable first error, reveal without
  response, unresolved parent, context repetition, idempotence, owner/retirement rejection and
  disclosure timing. The disclosure regression failed before the fix. Full PostgreSQL-enabled
  backend suite passed (`834 passed`); Ruff passed. All frontend units passed (`104 passed`),
  TypeScript/Vite builds passed and Chromium e2e passed (`9 passed`), including revealed repair
  after reload. Astra backend/frontend review found no remaining actionable issues. Human
  comprehension of these labels and independent rater agreement remain pilot measurements.
- P1-05b/P1-05c work on 2026-10-01: backend lifecycle tests cover create/resume, private-key
  exclusion, preserved first response, idempotency conflicts, immutable source/policy pins,
  grading without current files, retirement and non-scored exposure. Real HTTP tests with
  Uvicorn distinguish the listening bind from accepted loopback connections and reject
  wildcard listeners, forwarded requests and production mode. Full PostgreSQL-enabled
  backend pytest passed (`826 passed`); Ruff passed. Frontend unit tests
  passed (`101 passed`), TypeScript/Vite builds passed, and Chromium e2e passed (`8 passed`),
  including practice resume after a frozen failed submission, desktop/mobile and keyboard.
  The PostgreSQL run exposed a publication preflight race; a deterministic interleaving
  regression reproduced it before the fix, and all publication tests plus the full suite
  passed afterward. Astra reviewed the backend and frontend; both reported no remaining
  actionable findings after the recovery/exposure UI fixes. No participant outcomes were collected.
- P1-04b preparation on 2026-09-30: focused mapping/held-out-leakage, reviewed-pack,
  replacement/restore and catalog-code collision tests passed; full backend pytest passed on
  repeat after review fixes (`770 passed, 18 skipped`), Ruff and
  `git diff --check` passed. The known AI-fill heartbeat timing test failed once in the first
  full run, then passed alone and in the repeated full run; no AI-fill code changed. The new
  pack was published into disposable SQLite and PostgreSQL test databases; with Docker started,
  the complete PostgreSQL-enabled backend suite passed (`788 passed`). The local app database
  was migrated to `20260826_0005`, preflight returned five changed IDs and no rejection, and
  revision 1 was activated. A separate read confirmed four practice catalog examples, zero
  assessment examples and exact-repeat idempotence. The live product still has no practice UI.
- P1-05a on 2026-09-30: focused answer-policy tests passed, including reviewed exact
  answers, explicit other-script aliases, diacritics, omitted fields, wrong numerals and
  unresolved variants and a bank-hash-pinned 20-case internal reference fixture. The 16
  internally labeled cases yield 0/4 false accepts, 0/12 false rejects and 2/16 unresolved;
  these are constructed-case diagnostics, not observed learner rates or human gold.
  Full backend pytest passed (`785 passed, 18 skipped`), as did Ruff. Frontend unit tests
  (`88 passed`), TypeScript build, Vite build and Chromium Playwright e2e (`6 passed`) passed
  during this work; no frontend code changed in P1-05a.
- P1-03a candidate-bank verification on 2026-09-27: full backend pytest passed (`762 passed,
  18 skipped`), including 39 reviewed-bank regressions; Ruff and `git diff --check` passed.
  PostgreSQL integration was not rerun without `SLOVNIK_TEST_POSTGRES_ADMIN_URL`; no database
  code or frontend changed in this task. The eight-item CLI validation and unchanged re-import
  passed, and its review export exactly matched the retained document. After the recorded owner
  decision, publication validation passed; regression tests still reject removed owner approval
  or medium permission. No publication transaction was invoked.
- P0 verification on 2026-09-25: backend Ruff and full pytest passed (`707 passed, 16 skipped`);
  frontend unit tests passed (`88 passed`) and `vue-tsc -b` plus Vite production build passed.
  `git diff --check` passed. The 16 backend skips are environment-gated, including PostgreSQL
  tests without `SLOVNIK_TEST_POSTGRES_ADMIN_URL`. The six Playwright tests initially could not
  launch without a matching Chromium binary. Chromium for the locally installed Playwright 1.63.0
  was installed on 2026-09-25; all six e2e tests then passed against a loopback Vite server.
- P1-04a verification on 2026-09-25: synthetic approved-content fixtures exercised preflight,
  rollback and idempotence in SQLite and disposable PostgreSQL databases. Full backend pytest
  with PostgreSQL passed (`741 passed`); Ruff and `git diff --check` passed. The existing
  AI-fill heartbeat timing test failed once in a full PostgreSQL-enabled run, passed alone,
  and passed in the repeated full run; no AI-fill code was changed.
- P0-01 on 2026-09-25: the focused learning/quiz/projection/shadow and fixture suites passed
  (`125 passed, 3 skipped`); the full backend suite run from `backend/` passed (`675 passed,
  16 skipped`). Ruff, fixture JSON, documentation links and `git diff --check` passed. Skips
  include PostgreSQL-dependent cases without `SLOVNIK_TEST_POSTGRES_ADMIN_URL`.
- Solo-development documentation sanity check on 2026-09-25: the product-state and learning
  documents had 276 existing local link targets across 17 Markdown files, with no whitespace issues;
  `git diff --check` passed. No runtime tests were run for this documentation-only decision.
- A1–B1 research verification on 2026-09-25: all seven documents passed structural checks for
  36 topic IDs, 75 unique example IDs, 32 source/origin records, 132 local links and 47 tables;
  whitespace checks passed. Source access and inspected sections are recorded in the registry.
  No runtime tests were run for this documentation-only task; human language/rights review is pending.
- Learning-audit verification on 2026-09-24: the targeted learning, quiz, projection, curriculum,
  selector, catalog and domain/practice contract suites passed with `312 passed, 5 skipped`.
  The skipped cases require `SLOVNIK_TEST_POSTGRES_ADMIN_URL`; this audit did not run PostgreSQL
  integration, frontend or full-stack suites. Documentation references and whitespace were checked.
- Compose setup in `README.md` uses `docker compose up -d --build` after copying `.env.example` to `.env`; the existing host-run workflow remains available. Changing frontend npm dependencies requires `docker compose run --rm frontend npm ci` because its dependency volume persists. Compose configuration validation confirms all three published ports use host `127.0.0.1`.
- Verified on 2026-09-24 in a distinct disposable Compose project: configuration and frontend environment assertions passed; both images built; PostgreSQL became healthy; Alembic reached `20260826_0005 (head)` before Uvicorn started; the API health and Vite HTML endpoints responded; a temporary Vue edit appeared through Vite; vocabulary stayed at zero across a backend restart and became three only after manual seed; the container frontend build and all 83 unit tests passed.
- A separate 30-second PostgreSQL init-script smoke test reproduced premature readiness from a socket-only probe and an exhausted healthcheck retry budget. The Compose healthcheck now probes TCP on `127.0.0.1` with a 45-second startup grace period. On a fresh disposable volume, PostgreSQL stayed unready during initialization, then became healthy; backend migrations reached `20260826_0005 (head)` before Uvicorn, and `/api/health` returned OK.
- Backend verification documented in `README.md`: `cd backend && .venv/bin/ruff check .` and `.venv/bin/pytest -v`.
- Backend editable installation is verified with `.venv/bin/python -m pip install -e ".[dev]"`;
  setuptools discovers only `app*`, and the dev dependency remains on Ruff `0.6.x`.
- Frontend verification documented in `README.md`: `cd frontend && npm run test:unit`, `npm run build`, and `npm run test:e2e`.
- Database rebuild/seed verification is documented in `README.md` with `docker compose up -d postgres`, Alembic downgrade/upgrade, and `python -m app.seed`.
- Backend tests cover health, config validation, schema defaults, profiles, vocabulary, learning
  sessions, SQL due filtering/order/cap, every interval transition and cap, row-lock serialization,
  precise status reconciliation, quiz schedule reset, compatibility batch scheduling, quiz
  selection/submission/completion, weak-word behavior, repeat limits, and answer reveal.
- Language-assistant coverage includes frozen target/event/shadow wire contracts, all four context
  repositories, reversible migration constraints, event idempotency, replay and projection order,
  memory-v1 transitions, legacy baseline bootstrap, curriculum lifecycle/frontier, deterministic
  selector policies, shadow learning/quiz atomicity and concurrency, diagnostic isolation, and
  privacy-safe bounded payloads, catalog freshness, rollout flag transitions, deterministic partial
  evidence, persisted activity provenance, and runtime comparison wiring.
- OpenAI adapter tests cover strict response-schema requirements, configured SDK request arguments,
  prompt constraints, request-id retention, typed provider failures, and secret/source-word log
  redaction without real network calls.
- AI service and endpoint tests cover source normalization and validation, duplicate priority and
  edit exclusion, persistent store hits, partial patches, controlled fields and limits, structured
  stress validation, provider error translation, concurrent request coalescing, reservation
  failure/stale recovery, insertion races, and stable response bodies.
- Migration tests default to temporary SQLite databases and cover upgrade/downgrade data
  preservation, the upgrade path from the existing `0002` revision, JSON schema, and
  normalized-source uniqueness. Setting
  `SLOVNIK_TEST_POSTGRES_ADMIN_URL` enables the same round trip in a newly created disposable
  PostgreSQL database plus a synchronized two-session expired-reservation contention check that
  keeps the provider active beyond the initial lease; the normal `DATABASE_URL` is never migrated
  or dropped by that target. Supplied PostgreSQL configuration, connection, and privilege errors
  fail instead of skipping.
- Frontend unit tests cover app shell localization, session persistence, dashboard
  settings/localization, vocabulary API helpers, quiz repeat/self-check behavior, AI fill and undo,
  route/password request races, duplicate navigation, partial-field highlighting, localized
  feedback, accessibility, manual structured-stress editing, and the active-recall API/view,
  including initial loading, reveal-first hiding, save gating, precise status reconciliation,
  focus movement, completion, localization, and long-content constraints.
- Structured-stress coverage includes manual API create/update persistence and validation,
  canonical-equivalent Unicode reconstruction, legacy marker compatibility, full-syllable
  rendering, script-specific syllable arrays, invalid-pattern fallback, and HTML-safe text output.
- Playwright e2e covers the basic user-id-to-dashboard path, a mocked AI editor flow, and a mocked
  active-recall journey at 1280x900 and 390x844. Recall coverage proves answer details stay absent
  before reveal, all four ratings appear afterward, the next cue waits for the singular POST
  response, JSON payloads are exact, loading/focus/completion states work, and maximum bounded
  unbroken content creates no mobile horizontal overflow. No e2e scenario calls a real backend or
  OpenAI.
- Verified on 2026-08-27 after review remediation: full backend passed with `674 passed, 16 skipped`;
  targeted catalog/quiz/curriculum/selection/schema regressions, Ruff, whitespace, fresh migration
  upgrade, the explicit ORM/migration domain-schema parity regression, and the read-only catalog
  audit passed. PostgreSQL-only tests remain environment-gated by
  `SLOVNIK_TEST_POSTGRES_ADMIN_URL`.
- Verified on 2026-07-25: PostgreSQL-enabled backend tests passed with `221 passed`;
  frontend unit tests passed with `83 passed`; the production build passed; and all six Playwright
  tests passed.
- Manual MVP flow is in `docs/testing/mvp-manual-test.md`.

## Known Limitations / Deferred Scope

- The textbook is a basic written edition of selected grammar topics, not exhaustive A1–B1
  coverage. Case tables mainly cover singular forms; vocative, full plural paradigms, futur II,
  relative/indirect speech and audio remain outside this edition. Original prose/examples have
  internal source review, not independent teacher or corpus validation. Self-check sample answers
  are not exhaustive grading keys. The four-context practice pack is not expanded by reading
  textbook chapters, and the book does not claim learning efficacy or attained CEFR level.
- Quiz practice scores still count successful retries and self-checks alongside objectively
  scored responses; the new breakdown is limited to frozen-key attempts and does not establish
  mastery. Old plans retain vocabulary-dependent grading and cannot acquire historical keys.
  Mechanical choice-label repair does not establish semantic distractor quality.
- The internal curriculum can satisfy a hard prerequisite after one deterministic success, using
  a monotonic competence peak. This is a technical policy, not calibrated mastery evidence.
- Real authentication and authorization are deferred.
- Native mobile apps, audio pronunciation, bulk import, social features, and payments are not implemented.
- The legacy scheduler remains authoritative. Shadow mode can retain mapped review/quiz evidence,
  but production retention/export/delete policy, review-history analytics, desired-retention
  controls, FSRS fitting, and workload forecasting remain deferred.
- Catalog semantic versioning and automatic reconciliation remain deferred. Stale mappings are
  reported and rejected rather than silently rewritten.
- `alembic check` still reports five pre-existing legacy nullable mismatches on quiz/profile/
  vocabulary timestamps; the new domain tables have an explicit ORM/migration parity regression.
- AI fill v1 supports one Serbian word per request and strict normalized equality only. It has no
  batch input, regenerate action, Russian-to-Serbian card creation, morphology/fuzzy matching,
  generation review queue, or generation-store administration UI.
- Weekly quiz still uses calendar-week selection plus weak words rather than the review scheduler.
- Seed data is intentionally tiny and not a production vocabulary corpus.
- Results are stored client-side in `sessionStorage`; historical quiz analytics UI is not implemented.
- Vocabulary deletion, duplicate detection, import/export, and advanced content governance are not implemented.
- The frontend's `lang` attribute is hard-coded to `ru` even when Serbian UI copy is selected.

## Important Source Files and Docs

- `README.md`: setup, verification, and MVP access caveat.
- `.env.example`: local environment variables.
- `docker-compose.yml`: local PostgreSQL, migration-gated FastAPI, and Vue/Vite services, with source mounts and persistent data/dependency volumes.
- `backend/Dockerfile` and `backend/.dockerignore`: backend development image and context exclusions.
- `frontend/Dockerfile` and `frontend/.dockerignore`: lockfile-based Vite development image and context exclusions.
- `backend/app/models.py`: SQLAlchemy models.
- `backend/app/schemas.py`: Pydantic API contracts.
- `backend/app/routers/`: FastAPI endpoints.
- `backend/app/services/`: product rules for profiles, vocabulary, learning, and quizzes.
- `backend/alembic/versions/20260702_0001_initial_schema.py`: initial database schema.
- `backend/alembic/versions/20260724_0002_ai_vocabulary_fill.py`: structured stress and persistent
  AI generation schema.
- `backend/alembic/versions/20260725_0003_ai_fill_reservations.py`: concurrent generation
  reservation schema.
- `backend/alembic/versions/20260725_0004_active_recall_schedule.py`: persisted review scheduling
  state and due-time index.
- `backend/alembic/versions/20260826_0005_domain_foundation.py`: reversible domain
  foundation schema.
- `backend/app/services/learning_service.py`: due query, interval transitions, row locking, and
  compatibility review completion plus guarded shadow learning evidence.
- `backend/app/services/quiz_service.py`: quiz behavior plus guarded shadow quiz evidence.
- `backend/app/services/next_activity_service.py`: deterministic internal selector and optional
  non-authoritative comparison seam.
- `backend/app/services/shadow_selection_runtime.py`: persistence-backed isolated runtime
  composition for diagnostic selection comparison.
- `backend/app/services/catalog_mapping_service.py`: source fingerprint, fresh mapping resolver,
  and read-only mapping audit.
- `frontend/src/router.ts`: frontend route map.
- `frontend/src/api/client.ts`: typed frontend API wrapper.
- `frontend/src/views/ReviewView.vue`: reveal-first review, rating persistence, focus, and
  reconciliation.
- `frontend/tests/e2e/active-recall.spec.ts`: desktop/mobile active-recall journey and layout checks.
- `frontend/src/i18n/messages.ts`: UI copy.
- `docs/superpowers/plans/2026-07-02-serbian-vocabulary-trainer-mvp.md`: implementation plan.
- `docs/superpowers/specs/2026-08-26-parallel-sdd-execution-design.md`: ownership, waves and merge
  gates for parallel foundation development.
- `docs/progress/parallel-sdd-readiness-2026-08-26.md`: self-review evidence and residual delivery
  risks for the parallel SDD.
- `docs/testing/mvp-manual-test.md`: manual test script.

## Maintenance Instructions for Future Agents

- Read this file, `README.md`, and any task-relevant docs before planning or coding.
- Treat this file as the canonical current-state audit, but verify facts against code when changing behavior.
- Update this file in the same PR/commit when product behavior, architecture, setup, caveats, verification, or deferred scope changes.
- Keep this file factual and concise. Summarize durable product facts; do not turn it into a verbose changelog.
- Before claiming completion on a product-state change, run relevant tests or sanity checks and document what was verified.
