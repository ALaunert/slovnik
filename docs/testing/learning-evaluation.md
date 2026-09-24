# Learning evidence and evaluation contract (v1)

This is a measurement specification for the finite written pilot, not a validated mastery scale or a claim about current learners. `backend/tests/fixtures/learning/baseline-v1.json` contains invented, hand-reconciled specification examples. Keep current quiz practice scores separate from these measures.

## Observation classes

- **Exposure:** content was displayed without an elicited answer. Count exposures, never score them as success or failure.
- **First unaided scored response:** the first answer to an issued activity, before a hint, reveal or correction, judged deterministically as correct or incorrect. The unit is the issued activity/target/capability/modality/context revision. A later first answer in a repeated context is a new first attempt but not a new independent context occasion.
- **Assisted response:** an answer after a hint, reveal or correction. Report the support type and correctness separately; exclude it from unaided accuracy.
- **Repair/retry:** a subsequent answer explicitly linked to the first response in the same activity. A correct repair increases recovery, never first-attempt success. Keep the first answer immutable.
- **Self-report:** a learner's Again/Hard/Good/Easy or remembered/forgot rating. Count ratings by value; do not score them as objective correctness.
- **Unresolved answer:** ambiguous, unknown or model-only judgment without a reviewed deterministic verdict. Count it as unresolved, never as incorrect or eligible for objective accuracy. Missing old context/support fields remain unknown.
- **Independent context occasion:** an unaided first scored response in a known, distinct context family for the target. The first such family counts once; same-family repeats do not establish transfer. A missing or unversioned family cannot establish a distinct occasion.
- **Delayed new-context response:** an eligible independent context occasion at least seven full days after the first eligible response to that target, using a new, held-out context family. The 28-day measure uses the same rule with a 28-day horizon. Real study windows and invitations are reported separately.

## Denominators and missingness

| Measure | Numerator | Denominator | Exclude or report separately |
|---|---|---|---|
| First-attempt accuracy | Correct unaided first deterministic responses | Correct plus incorrect eligible first responses | Hints, reveal, retries, self-ratings, unresolved verdicts |
| Recovery | Correct linked repairs after an incorrect first response | Eligible incorrect first responses with a repair opportunity | Report no opportunity and missing follow-up separately |
| Assisted correctness | Correct supported deterministic responses | Correct plus incorrect supported deterministic responses | Report support type; never merge with first attempts |
| Delayed recall at 7/28 days | Correct unaided first responses in a new held-out context at the declared horizon | Eligible correct plus incorrect responses at that horizon | Separately report invited, completed, missed and unresolved probes; never turn a missing probe into failure |
| Unresolved rate | Unresolved submitted responses | Submitted responses requiring judgment | Report reason and evaluation source; no forced verdict |
| Self-report | Count by rating | Submitted ratings | No objective accuracy percentage |

Every result retains target, capability, modality, activity/content/policy versions, evaluation source, response order, support, source and context family, delay, and missingness where known. Compare like formats and populations; written cue-to-form recall and recognition have separate denominators. Report raw counts alongside rates. An empty denominator is “not measured,” not 0%. Repeated contexts may count as first attempts for a new issued activity but do not prove independent transfer.

The frozen fixture truth table is: wrong→correct gives one eligible incorrect first attempt and one recovery; hint→correct gives one assisted success; self-rating gives one subjective rating; two first successes in the same context give two first attempts but one distinct context; a success eight days later in a new context gives one eligible delayed success; an ambiguous verdict gives one unresolved answer. Totals are 5 eligible first attempts, 4 first successes, 1 recovery, 1 assisted success, 1 self-rating, 1 unresolved answer, 4 distinct context occasions, and 1 eligible/correct delayed new-context response. These are arithmetic checks, not pilot results.

## Current baseline and limits

The legacy quiz score counts questions with any correct answer, including a successful repeat and remembered self-check. It is a **mixed practice score**; the existing `QuizAttempt.score` and old cached results remain valid as that historical metric. Current review `learned` reflects a self-rating streak, not demonstrated mastery. Projector v1 weights deterministic retries like first successes and lacks reliable context/revision data for old shadow events. P0-03 adds a separate first-attempt breakdown; P0-06 adds read-only evidence classification. Neither should retroactively infer missing assistance, keys, context or ownership.

For a real pilot, report 7- and 28-day invitations, completions, attrition, target/capability/modality splits, unseen-task meaning and target accuracy separately, false accept/reject and unresolved rates against human labels, critical content defects, measured practice minutes and workload distribution. Predefine useful effects, burden and missing-data handling before comparative evaluation. No current fixture sets a proficiency threshold or a validated competence probability.
