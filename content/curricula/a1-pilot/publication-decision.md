# P1-04b: prepared written pilot publication revision

Date: 2026-09-30. [Publication manifest](publication-v1.json) is the reproducible file for
the **active revision 1 in the local PostgreSQL database**. It pins the [four-outcome brief](manifest.json), the
[eight approved reviewed examples](../../examples/a1-written-v1.json), separate
[text/translation rights](../../sources/a1-written-v1.json), source/revision digests, target
mapping, answer-policy revisions, practice and held-out families, CEFR locator labels and the
three proposed soft edges. There are no hard edges or full-A1/attainment claims.

| Outcome | Catalog pattern | Practice / held-out assessment | Catalog exposure |
| --- | --- | --- | --- |
| `A1.PERSONAL_DETAILS` | fictional three-field written form | profile card / registration message | profile practice only |
| `A1.SIMPLE_REQUEST` | bounded polite item request | counter notice / kiosk selection | counter practice only |
| `A1.PRICE_INFO` | two-item written price notation | shelf tags / left-price cafe table | shop practice only |
| `A1.LOCATION_INFO` | meeting-place message pattern | changed library plan / two-event office plan | library practice only |

Each row has two different contexts: one practice item embedded in `Construction.examples`
and one private assessment item retained only in the reviewed bank. A catalog example with an
assessment role is rejected by preflight even if its text and translation were reviewed.
Stable UUIDs map editorial target keys **and catalog revisions** to construction IDs, while
curriculum node/edge IDs include the curriculum version. This allows a reviewed correction
to receive a new catalog identity and a replacement or restoring revision to retain old
history. It does not change the owner-approved bank or its digests. `Construction` and the existing
`apply_construction` capability represent these narrow **written task patterns**, including
the price-notice lookup; they are not evidence of general grammatical competence. Later
practice/evaluation must honor the per-item task and answer policy rather than infer an
unbounded construction scorer from this catalog tag.

Preflight in a disposable database proposes four new catalog IDs and one curriculum revision.
It rejects stale source/brief/bank pins, target mappings, reused catalog codes, rights, missing
answers, held-out catalog examples and hard-edge changes. `ContentPublicationService.publish` then commits
catalog content with the curriculum atomically; repeated exact publication is idempotent.
The approved source and brief still carry unresolved variants as `unresolved`, never binary
errors. The old P0 fixtures and legacy vocabulary/quiz histories are not rewritten.

The current local PostgreSQL database was empty before publication (migration
`20260826_0005`, no vocabulary or curriculum rows). Its preflight proposed four new
construction IDs and one curriculum version ID, with no rejection. The atomic publication
created active `slovnik-written-a1` revision 1
(`3082e687-db28-5774-82a8-4f709a592cd7`), four constructions and four catalog practice
examples. A second read confirmed zero assessment texts in catalog and an idempotent exact
repeat; the approved bank still keeps all four assessment items privately. Full backend tests
with disposable PostgreSQL passed (`788 passed`). The manifest retains `prepared_for_local`
as a file-state marker; only the local database records activation. No production deployment,
learner-facing practice route or remote data access was enabled. A later rollback must be a
new reviewed revision; older published rows and issued histories are not rewritten.
