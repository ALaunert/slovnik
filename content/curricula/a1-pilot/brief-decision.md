# P1 editorial decision on the written outcome brief

Recorded 2026-09-25 for the Slovnik internal pilot. This approves the **four narrow task
definitions and the holdout split as design hypotheses**, not the current example sentences,
translations, answer keys, source permissions or a CEFR-level claim. The source is the Council of
Europe, *CEFR Companion Volume* (2020),
[official PDF](https://rm.coe.int/common-european-framework-of-reference-for-languages-learning-teaching/16809ea0d4).
Page numbers below are the printed pages, not PDF offsets. No descriptor text is imported into
the product.

| Outcome | Direct locator and internal decision | Boundary before an example is approved |
| --- | --- | --- |
| `A1.PERSONAL_DETAILS` | Notes, messages and forms, p. 84, A1: forms with personal fields. Keep a fictional registration form and score only requested fields. | A complete sentence about a name alone does not test filling several fields. Use fictional identities and separate the registration holdout from profile practice. |
| `A1.SIMPLE_REQUEST` | Obtaining goods and services, p. 78, A1: basic requests for food or drink. Keep a written rehearsal only; the source scale concerns oral interaction. | Limit the item, quantity and social situation. Review case, politeness and alternative formulations independently; no oral achievement claim. |
| `A1.PRICE_INFO` | Reading for orientation, p. 56, A1: basic information including cost in simple notices. Keep a two-item notice and an item–price lookup. | A single sentence containing one number leaks the answer without item selection. Reserve a different layout, item set and wording for holdout. |
| `A1.LOCATION_INFO` | Notes, messages and forms, p. 84, A1: a simple message about where someone has gone or when they return. Keep a short written location message as a provisional analogue. | A static sentence saying that a building is “here” does not by itself test the message task. Review the place/referent relation and a genuinely different holdout situation. |

The manifest's four practice and four assessment families remain separated. Family IDs alone do
not establish independence: a script change, changed name or changed number with the same prompt
shape is still near-duplicate leakage. Preserve the assessment family before writing additional
practice prompts. The proposed soft order stays a hypothesis; no hard prerequisite is approved.

This decision does **not** approve the eight P0 fixture examples. In particular, the existing
single-sentence price fixtures do not meet the two-item lookup, and the personal/location
fixtures do not yet perform their stated written tasks. Their language, translation and answer
variants still need item-level source checks under
[`solo-development-readiness.md`](../../../docs/learning/solo-development-readiness.md).
The source manifest still records unknown display rights. Exclude any item whose language or
rights cannot be justified; do not turn it into a binary scored answer by inference.
