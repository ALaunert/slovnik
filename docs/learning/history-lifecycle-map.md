# Learning history storage and deletion map

Audited 2026-10-01. Engineering preparation for P2-02a, **not an approved retention policy**
or authority to delete existing data. Jurisdiction, legal basis, custodian, periods and backup
operations remain unresolved. Authentication is outside the owner's current scope; public owner
export and erasure remain unavailable.

The [local pilot procedure](local-written-practice.md#local-retention-boundary) and
[research protocol](../testing/written-pilot-protocol.md) retain their narrower boundaries. The
proposed 35-day period after the last planned observation still requires local consent review;
it is not a legal default or an implemented expiry job.

## Database records

Sources: [legacy models](../../backend/app/models.py),
[practice](../../backend/app/domain_models/practice.py),
[progress](../../backend/app/domain_models/progress.py),
[catalog](../../backend/app/domain_models/catalog.py) and
[curriculum](../../backend/app/domain_models/curriculum.py).
ORM metadata and local PostgreSQL at migration `20261001_0006` agree on these eighteen application
tables. `alembic_version` is additional schema administration metadata, not learner history.
No database foreign key specifies `ON DELETE CASCADE` or `SET NULL`. Catalog/curriculum ORM
`delete-orphan` relationships do not provide profile erasure.

| Table | Ownership and retained data | Export or deletion dependency |
| --- | --- | --- |
| `user_profiles` | Direct `user_id`; preferences, daily count, language, timezone and pending transition | Future verified owner export includes settings. Delete after dependent histories. Supplied ID is not ownership proof; local pilot deletion preserves profile. |
| `user_word_progress` | Profile and shared vocabulary FKs; counters, weakness, review dates/streak | Learner-owned legacy progress. Full erasure must cover this independently of shadow state. Local pilot deletion preserves it. |
| `quiz_attempts` | Profile FK; times, mixed score, serialized plan/keys and completion data | Owner attempts/results under approved rights. Remove answers and linked shadow runs first. Local pilot deletion preserves attempts. |
| `quiz_answers` | Owner through attempt FK; vocabulary FK, prompt, submitted text, correctness/time | Every first/retry answer belongs in approved owner scope. Delete before attempts; deleting practice events leaves these texts. |
| `practice_runs` | Profile FK; optional curriculum and legacy quiz-attempt FKs; status/policy/time | Delete events/activities before runs, runs before profile/linked attempt. Local operator selects local v1/v2 runs without a quiz link. |
| `activity_instances` | Owner through run; composite run/policy and self retry/run/target FKs; frozen task/key/context/workload JSON | Export only permitted snapshot fields privately. Delete affected repairs/parents together after events. Pending/cancelled rows count. |
| `learning_events` | Profile FK plus composite run/owner and activity/run/target/kind FKs; first response/rating/outcome JSON and idempotency key | Raw personal evidence. Preserve first facts in approved export; erasure also covers derived state/external copies. |
| `learner_target_states` | Profile FK; learner/target uniqueness; competence/memory, cursor and baseline JSON | Derived personal state in erasure scope. `last_event_id` is a string, not FK; raw deletion does not clear it. Neutral/legacy baselines differ. |
| `vocabulary_items` | Shared editor text/examples/stress; no learner-owner column | Preserve shared content on learner erasure. Editorial rights/withdrawal are separate; user-entered shared text is not necessarily free of identifying content. |
| `ai_vocabulary_generations` | Shared source word/payload, model/prompt versions; no profile FK | No reliable per-learner mapping; do not guess by matching text. Cache/content and provider copies need separate lifecycle decisions. |
| `ai_vocabulary_generation_reservations` | Shared normalized word, transient owner token/expiry; no profile FK | Provider-call coordination. Lease expiry is neither learner retention nor provider deletion. |
| `language_lexical_units` | Shared catalog revision/status; optional vocabulary FK | Preserve for learner erasure. Retiring content does not rewrite issued snapshots. |
| `language_forms` | Lexical-unit FK; shared orthographies, morphology/stress, revision/status | Preserve catalog. Rights determine permitted later historical/export representation. |
| `language_senses` | Lexical-unit FK; glosses, notes, embedded examples, revision/status | Shared content; profile deletion does not retire examples. |
| `language_constructions` | Shared code/text/examples and revision/status | Current written pilot content; no independent example table. Preserve in learner erasure. |
| `curriculum_versions` | Shared lifecycle/version metadata; referenced by runs | Preserve course; an old version cannot supply deleted learner responses. |
| `curriculum_nodes` | Version FK; target/capability/modality/condition/outcome | Shared structure. Catalog `target_id`/`target_key` are serialized references, not catalog FKs. |
| `curriculum_prerequisites` | Version FK and two composite version/node FKs | Preserve shared edges. Separately authorized node deletion requires edge cleanup. |

## Replay and deletion boundaries

[Projection replay](../../backend/app/services/learner_projection_service.py) resets to a stored
neutral or legacy-bootstrap baseline and applies retained events. Deleting some events while
keeping derived state, baseline or stale snapshots is not completed selective erasure. Restored
events can reconstruct evidence. Shared content identities do not authorize personal retention.

The [local operator](../../backend/app/local_pilot_data.py) already inventories and, with
`--execute`, deletes selected pilot target states → events → activities → runs in one transaction.
It locks the profile/runs, rejects shared non-pilot target history or non-neutral baselines, and
preserves profiles, vocabulary, legacy quiz/progress and other learners. It does not remove browser
or filesystem copies. Refused mixed history needs a reviewed replay plan, not invented baselines.

For future **full owner erasure**, candidate FK-safe drill order is all owner states/events →
owner activities/runs → answers/attempts → legacy progress → profile, preserving shared content.
This is a test design, not a live command. Trusted ownership, an approved action matrix,
concurrent-write fencing and restore handling must be implemented first.

## Files browser and infrastructure copies

| Record class | Current facts and additional work |
| --- | --- |
| Enrollment/consent | Restricted pseudonym↔profile map, consent scopes/time/evidence hash and withdrawal; synthetic-only export. Store separately from blind packets; inventory real consent evidence/copies. Hash is not proof of consent or anonymization. |
| Frozen assignment/protocol/pack | Immutable slots/cohort and exact content/rights/protocol pins. Assignment has study pseudonyms. Withdrawn slots stay occupied; new outputs do not erase prior maps. Shared authored pack has a separate editorial lifecycle. |
| Raw research export | Two private files; recognized remover accepts v1/v2. It cannot remove other copies. Changed withdrawal registry requires a new export; no historical first-response edits. |
| Observer ledger | Explicit display/support/contact and probe answer/missing facts. Custodian must inventory/remove consented rows/files/copies; no automatic ledger eraser or inferred history. |
| Joint dataset/blind scores | Eight private files include histories, blind answers/mapping, ratings, analysis, assignment/protocol. Recognized build/verify/remove covers the whole bundle. Withdrawal rebuild excludes rows but old copies remain. Unknown files/symlinks refuse removal. |
| Browser storage | `localStorage`: `slovnik.userId`, UI language. `sessionStorage`: `slovnik.practice.v1.<encoded-profile-id>` run pointer, uncertain first text/token, pending repair; quiz results also use session storage. Clear relevant entries in affected browsers. Logout currently clears a profile pointer, not server history/every practice entry. |
| In-memory UI/requests | Prompt/feedback, typed answer and in-flight submission while a view is open. Close participant views/stop submissions before local deletion. Future erasure needs explicit client completion/retry handling. |
| PostgreSQL volume | Compose `postgres_data` persists after shutdown. Volume persistence is not backup expiry; do not remove a whole volume to erase one participant. Inventory actual storage copies separately. |
| Backups/WAL/snapshots/logs | No backup creation/expiry/restore-erasure mechanism is defined by repository Compose setup. External copies cannot be inferred absent. Locations, custodian, deadlines and restore suppression are pending; no current erasure certification. |
| Remote provider records | Existing vocabulary fill may send an editor's word to OpenAI. Written scoring/research join do not call a provider. Local cache deletion does not remove provider records; local `pilot_display` rights do not establish new research-text transmission permission. |

Free-form first text is pseudonymous, not automatically anonymous. A learner can enter identifying
information despite fictional prompts. Human-use copy minimization and restricted reviewer access
remain part of pending consent/custodian review.

## Period and action matrix requiring approval

| Record class | Active | Research withdrawal | Full owner deletion | Backup/copy |
| --- | --- | --- | --- | --- |
| Profile/legacy history | Period unapproved | Does not silently erase unrelated legacy learning | Scope/action/ownership pending | Deadline/restore suppression pending |
| Written raw/derived practice | Synthetic checks; local 35-day proposal needs review | Strict neutral/unshared local deletion available | General erasure/replay policy pending | Must not restore erased evidence; mechanism/period pending |
| Research files/ratings | Real consent/custodian/period pending | Exclude new outputs; inventory/remove already-held copies | Apply approved consent/erasure scope | Copy manifest/expiry/restore policy pending |
| Shared course/catalog/model cache | Editorial lifecycle, not learner period | Does not erase shared authored content | Preserve content; review identifying editor text separately | Rights/provider withdrawal separate |
| Non-content erasure log/tombstone | Not implemented/approved | Local action/count/time log proposed | Allowed fields/period pending | Restore-time use/expiry pending |

Unresolved cells are deliberate. Timezone, server location or model recommendation do not establish
jurisdiction, lawful basis or a retention period. No policy approval is inferred from this map.

## Populated drill design

Use isolated migrated PostgreSQL with two fictional profiles. Give the first legacy progress,
completed/pending quizzes with first/retry answers and linked shadow run; local written first
response, pending exposure, reveal/repair; neutral and legacy-bootstrap states. Give the second
overlapping shared targets and separate histories. Use synthetic sentinel text to check absence
from raw/derived/JSON/browser/research copies.

| Check | Required result and current evidence |
| --- | --- |
| Export completeness/isolation | Every approved personal record class, no other learner or unpermitted keys/consent copies. Current research export is narrower; P2-01b/P2-02b required. |
| Local pilot deletion | Atomic raw/derived removal; profile/legacy/other learner preserved, repeated inventory zero. Existing SQLite/PostgreSQL linked-repair tests cover this bounded action. |
| Mixed baseline/history | Refuse before mutation; later authorized replay uses lawful retained facts. Non-neutral refusal tested; general selective erasure absent. |
| Full owner erasure | FK-safe, no orphan retry/cursor/reconstructable text; shared content preserved; idempotent. Ownership/policy/implementation missing. |
| Withdrawal/copies | Old enrollment/export rejects; rebuilt blind/mapping/ratings/analysis excludes withdrawn learner; existing copies erased separately. Synthetic tests cover exclusion/invalidation and recognized removal. |
| Backup restore | Restore an old backup in isolation, apply approved suppression before service starts, sentinel absent by deadline. Backup technology/suppression/expiry missing. |
| Submission/deletion race | Delayed retry/new event cannot restore evidence; client reports removed/unavailable. Future lifecycle fence/race tests required; local profile lock is not public-release proof. |
| Content withdrawal | No new retired task; historical export has only permitted text/metadata. Runtime retirement guards exist; historical rights policy pending. |

Verified by read-only ORM/DB schema inspection and existing deletion/export/dataset tests. No real
profile or bundle was deleted. **P2-02a stays open** until periods/actions and responsibilities are approved.
