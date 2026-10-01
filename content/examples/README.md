# File-backed written example revisions

`a1-written-v1.json` is the first P1-03a bank, approved by the project owner for local
written pilot display on 2026-09-27. It is not loaded by the app.
The P0 examples stay intact in `content/curricula/a1-pilot/examples.json` as draft fixtures.
Both use the P0 target/family contract; schema 2 adds editorial revision checks. Schema 1
remains readable with its original validator and publication semantics.

## Contract

- `id` stays attached to `(source_id, source_item_key)`. A content correction increments
  `revision`; an existing `(id, revision)` cannot change during a checked re-import.
  Each bank contains one current revision per source item; prior banks are retained separately.
- `original_text` is retained; `text` is its NFC display form or equivalent Serbian script.
  Translation is separately authored and reviewed. `content_hash` binds the task, text,
  key, target, family, source identity and provenance; a hash is not a language approval.
- `task` contains the actual stimulus, instruction and response format. Fields and numeric
  keys must agree with canonical answers. Script aliases must transliterate a reviewed key.
  A short form/notice is a valid task format; a sentence fragment is not automatically approved.
- `review` records naturalness within the stated context, target alignment, answerability,
  variants, translation, source locators, reviewer/date and disagreements. The reviewer is
  an internal model pass; no independent language reviewer agreement is claimed.
- `duplicate_cluster` records the editorial task/near-duplicate group, not just the example ID.
  A cluster cannot straddle practice and assessment. Exact script-equivalent display text is
  also rejected across roles. These checks cannot prove semantic independence by themselves.
- Only fictional personal details are admitted. A fictional-data declaration cannot prove
  anonymity; the current bank was composed from scratch, with no learner data or source CV.
- `answer_policy.unlisted` is always `unresolved`. An unlisted plausible answer is not a
  binary learner error. Policies describe later practice; this task adds no grading route.
- `publication_decision` records the project owner's inclusion decision and binds the exact
  bank and rights manifest with separate digests. Language review and an owner's inclusion
  decision are separate gates. Permissions apply to text and translation separately; no audio.

## Checks and review export

From `backend/`:

```bash
.venv/bin/python -m app.reviewed_example_bank ../content/examples/a1-written-v1.json \
  --pilot ../content/curricula/a1-pilot/manifest.json \
  --sources ../content/sources/a1-written-v1.json \
  --review-export ../content/examples/a1-written-v1-review.md
```

Use `--previous <retained-prior-bank.json>` when importing an edited/reordered bank. This
checks prior identity and revision integrity; there is no database import or automatic approval.
Pass `--publication` to require the owner decision and permitted text/translation uses.
The checked-in bank passes this gate; removing owner approval or a medium's permission fails it.
The P1-04a publication service uses the same version-2 gate before writing catalog content.

For an explicit owner approval of this original material, retain its message as the authored
agreement evidence, set each permitted medium's rights/reviewer/date/use, then record the
owner decision with `bank_digest(bank)` and `rights_digest(sources)`. This is not done by
the validator or export command. The source checksum pins `bank_digest` and excludes the
owner decision; any edit to the bank requires a new source pin and inclusion decision.

See [the decision and unresolved time measurement](a1-written-v1-decision.md) and
[the complete review export](a1-written-v1-review.md).
