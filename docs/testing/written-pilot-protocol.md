# Written feasibility protocol v1 — preparation for P1-09b

Status: prespecified internal design, 2026-10-01; **not authorized for human collection**.
Astra reviewed the design under the owner's autonomous development instruction. That review
does not supply participant consent, a blinded human rubric trial or measured outcomes.
P1-09b stays open until the real reviews below. The joint synthetic engineering pipeline is
implemented; passing file checks does not authorize human data collection.
This protocol complements [P0 definitions](learning-evaluation.md) and
[local operation/deletion](../learning/local-written-practice.md).

## Scope and recruitment

Plan twelve consenting adults, Russian-speaking beginners, using dedicated local profiles under
supervision. Exclude anyone previously shown the four heldout tasks. Record invitations, declines,
withdrawal and attrition; recruiting twelve is a feasibility target, not a powered efficacy study.
No public enrollment or remote histories. Authentication remains outside current scope.

Use only the exact reviewed `a1-written-pilot-v1` bank/rights/answer-policy revisions already pinned
by publication. Four practice tasks and four heldouts assess narrow written functions, not CEFR
attainment. No comparative learning-effect threshold is estimable with this uncontrolled design;
this is an explicit limitation relative to P1-09b's effect-threshold wording.

## Holdout assignment before outcomes

There is only one heldout family per target. Assign two targets to the seven-day visit and the other
two to the twenty-eight-day visit. Use each of the six possible two-target combinations twice;
prespecify the shuffle seed/order before enrollment and retain it privately. The engineering
utility freezes the complete cohort-to-slot map after enrollment and before any included practice
or probe invitation. Late additions require a new study assignment; an occupied or withdrawn slot
cannot be silently reused. This batch-enrollment boundary needs human protocol review.
Each target has six potential observations per horizon. Each participant sees each heldout once.
There is no within-person comparison of the same target at both horizons. A display without an
answer still consumes that family's unseen status; do not reissue it as an independent probe.

Windows are `[7,10)` and `[28,31)` elapsed days after the latest verified target contact, including
material, feedback, reveal and practice. Stop planned target practice between preparation and its
probe. A new verified contact shifts eligibility; preserve the original assignment. Unknown contact
history makes eligibility unknown. Retain late observations as out-of-window; do not move them into
an eligible denominator. Defer probe feedback until all of that participant's probes are complete.

The backend event's selected/submitted timestamps alone do not prove latest contact. A separate
observer ledger must record shown/not-shown/unknown, contact time, additional support and first
response timing. In particular, GET feedback is not a complete display journal. Do not reconstruct
missing displays or external practice from DB timestamps.

## Restricted files and consent

Keep these outside Git and public serving directories, with one named local data custodian and
owner-only filesystem permissions. The custodian must be assigned before enrollment.

| File | Minimum content |
|---|---|
| Protocol/assignment | Version/hash, exact bank/rights/policy pins, windows, frozen slots and analysis rules |
| Enrollment, stored separately | Random study pseudonym ↔ dedicated profile; real consent reference/hash/time/version/scopes; withdrawal and deletion deadline |
| Observer ledger | Unique invitation/display/contact IDs; pseudonym, target/horizon/family, UTC times, shown/not-shown/unknown, support chronology, immutable first response or missing status |
| Export and manifest | Only consented pseudonymous first-response/support/context/time/version/workload fields; input hashes, generated files and omissions |
| Blinded ratings | Random response ID, task/rubric version, two rater IDs/scores and adjudication; no learner identity, horizon, previous result or automatic verdict |

Consent must precede the collected records and specifically cover local storage, delayed visits,
pseudonymous research export and blinded rating. Declining or withdrawing has no learning penalty.
No historical backfill. Withdrawn participants are absent from new exports; remove their existing
rows/copies using the manifest. Proposed expiry is 35 days after the last planned observation,
subject to the required local consent/retention review. There is no automatic retention job.
Delete DB raw/derived pilot records with the tested local operator tool; remove observer/enrollment,
export/rating and backup copies separately. Record non-content deletion counts/time. Verify zero
inventory and that no retained export/replay can restore a deleted answer. Public lifecycle is P2.

## Measurements and decision rules

Report invited, displayed, responded, eligible, resolved, unresolved, missing and excluded-with-reason
per participant, target and horizon before aggregating. First resolved recall is correct/(correct +
incorrect) only among eligible unaided novel-family first responses, alongside resolved/invited and
missing/invited. Missing is not a submitted empty answer; intentional empty input remains a response.
Unresolved and unknown support/contact remain separate, never imputed failure or success. Human
task/target ratings remain separate from deterministic verdicts and do not write LearningEvent or
projection state. Small strata need counts and uncertainty, not a mastery percentage.

Prespecified feasibility defaults, to be reviewed before collecting answers:

- At least 75% of invitations completed in each observation window.
- At least four eligible resolved responses per target × horizon cell; otherwise that cell is
  descriptive and insufficient for a target-specific conclusion.
- Zero holdout leaks, consent violations or lost first responses. Any incident pauses collection.
- Two probes per visit; voluntary stop at any time; fifteen-minute visit ceiling measured by the
  observer. This is a procedural ceiling, not a predicted learning duration.
- Active minutes remain missing until separately observed; issuance-to-response delay is not
  active practice time. Report burden/missingness and editorial defects, including accepted but
  unlisted variants and score/support-label comprehension.

Up to 48 probes represent twelve independent participants, not 48 independent people. This sample
supports procedure/cell coverage checks; it cannot establish comparative efficacy, precise effects
or reliable subgroup differences. Report an inconclusive result if feasibility fails.

## Engineering prototypes and checked limits

`backend/app/research_export.py` provides `local-research-export-v2` for explicitly declared
synthetic fixtures only. It rejects a human enrollment registry, missing consent scopes, duplicate
profile/pseudonym mapping and unknown protocol versions. A caller declaration is not proof of real
consent: do not mark human records synthetic to bypass this preparation gate. The allowlist excludes
profile IDs, idempotency keys and private answer snapshots. Pending and unresolved responses remain
visible; no display, independent recall, elapsed active time or human rating is inferred.

The local operator may run a synthetic export with the dedicated local flag enabled:

```bash
cd backend
LOCAL_PILOT_ENABLED=true .venv/bin/python -m app.research_export /absolute/private/enrollment.json /absolute/private/new-export
```

Both paths belong outside Git and public serving directories. The new export directory is private
(0700), its two files are private (0600), and its manifest records enrollment and canonical records
hashes, response kinds and omissions. Existing v1 exports remain removable; the joint builder
requires v2 source fields and hashes and never infers missing response kinds in old exports.
`remove_export(path)` removes only a recognized two-file export, refuses unknown files or symlinks,
and is idempotent for an absent directory. It cannot remove copies elsewhere or database records;
the custodian must inventory and remove those separately. Human exports remain unavailable.

`backend/app/research_ledger.py` is a pure observer-fact analyzer, separately checked against all
six P0 truth histories. Its input is one learner/target/capability/modality history, not an automatic
conversion of DB export rows. Completeness, support capture and frozen keys must be explicitly
verified by the observer. Duplicate IDs preserve one first response; conflicting facts reject.
Verified response/display/support contacts are inventoried before analysis, so invitation order
cannot supply independent-family credit or determine the elapsed window. A completed probe must
have its observed start and first response in the specified window, with no intervening contact;
its matching initial display does not reset its delay. A presentation linked with `activity_id`
must match the activity's known initial display time/family and reconcile any known support.
Earlier displays, later feedback and additional contacts use separate, unlinked presentation IDs;
they remain contacts even if their family is the same. Unknown contact/support is excluded from eligible recall, and unanswered
invitations remain in missing counts. Human rubric scores never enter the product projection.

`backend/app/research_dataset.py` joins those retained files without reading or changing the DB.
It freezes twelve balanced slots, exact reviewed curriculum/example/answer-policy/bank/rights pins
and the protocol file hash. Keep the original pack files and frozen protocol: passing a changed
pack or protocol rejects; `--content-root` and `--protocol` can point to retained copies.
Withdrawals leave the slot map unchanged, invalidate the previous source export's enrollment hash
and require a new export/observer file. Rebuilds omit withdrawn rows; they do not erase old copies.

Every exported activity must have an observer counterpart with identical invitation, first text,
time, verdict, family and retry parent. Known assistance cannot be erased; absent observer flags
remain unknown. Only one heldout probe per participant/target is accepted, using the frozen
assigned horizon and assessment pins. The observer's `probes` retain explicit missing or first
text/time facts; the finite reviewed policy computes a research-only verdict. No heldout is issued
through the application and no research verdict becomes a product event. Known heldout displays
before the first response are reported as incidents, including when initial display is unknown.

The restricted output has eight files: normalized `dataset.json`, `assignment.json`, `protocol.md`,
`blinded-responses.json`, `blind-mapping.json`, `ratings.json`, `analysis.json` and
`dataset-manifest.json`. The manifest hashes all inputs and the seven data files. These are
consistency checks against retained files, not proof of DB origin or real consent. Workload counters
and actual allocation windows are retained separately from unmeasured active minutes. Per-probe
reports retain display/response/missingness, eligibility and exclusion reasons; enrollment,
withdrawal, unrecruited, planned, invited and not-invited counts are separate.

Blind rows contain only random response ID, task/input/instruction, first response and two-scale
rubric. Their order is randomized; rebuild with the retained `--mapping` preserves IDs/order and
rejects changed answers or mappings. Missing answers have no rating row; an intentional empty
answer does. Free-form response text is not automatically anonymized: human use also requires a
custodian's identifying-content review under the pending consent policy.

Ratings bind the exact blind packet hash and known response IDs. Two distinct random rater IDs
provide integer 0..2 scores for task success and target accuracy. Exact duplicate deliveries are
deduplicated; conflicting scores, third raters and boolean scores reject. Adjudication is separate
and requires the two original ratings. Missing pairs and disagreement counts remain visible;
synthetic agreement is a calculation check and always labels human agreement `not_measured`.

Synthetic-only operator commands (all input/output paths outside Git/public serving):

```bash
cd backend
.venv/bin/python -m app.research_dataset freeze --enrollment /private/study/enrollment.json --pack /retained/content/curricula/a1-pilot/publication-v1.json --content-root /retained/content --seed recorded-seed --frozen-at 2026-10-01T00:00:00+00:00 --output /private/study/frozen
.venv/bin/python -m app.research_dataset build --export /private/study/source-export --enrollment /private/study/enrollment.json --assignment /private/study/frozen/assignment.json --protocol /private/study/frozen/protocol.md --observer /private/study/observer.json --pack /retained/content/curricula/a1-pilot/publication-v1.json --content-root /retained/content --output /private/study/new-dataset
.venv/bin/python -m app.research_dataset verify /private/study/new-dataset
.venv/bin/python -m app.research_dataset remove /private/study/new-dataset
.venv/bin/python -m app.research_dataset remove-assignment /private/study/frozen
```

Build accepts the two-file source export directory (or an explicit combined synthetic fixture).
Add `--mapping /private/old/blind-mapping.json` for a stable rebuild and `--ratings
/private/study/ratings.json` for separately retained synthetic scores; without scores, an empty
rating template is written. New output directories must not exist; permissions are 0700/0600.
Verification refuses changed file hashes. Removal covers the recognized files even when a data
file hash is broken, but refuses unknown files, unsupported manifests or symlinks. It repeats safely
for an absent directory. It does not remove enrollment/observer inputs, separately retained pack
files, exports elsewhere, backups or DB data: inventory and remove those independently.
No human data has been collected by this work.

## Blinded human rubric and remaining gates

Two independent Serbian L2 raters score each response without participant identity, horizon,
automatic outcome or prior performance. Task success: 0 absent, 1 partial, 2 all requested
information/action conveyed. Target accuracy: 0 absent, 1 recognizable with errors, 2 correct;
for price, rate item→price correspondence. Missing response is missing, not 0. Preserve both
ratings and separate adjudication; human disagreement never rewrites automatic practice evidence.

Before enrollment, double-rate eight constructed answers: at most one disagreement per scale
and no unresolved 0↔2 discrepancy. This **has not occurred**; model ratings are not human agreement.
Real consent/retention review, an assigned custodian and blinded human rubric trial are open
P1-09b gates. Real participants and elapsed windows are
additional P1-09c gates. No outcomes have been viewed or collected for this protocol.
