# AI Vocabulary Fill Design

Date: 2026-07-10

## Goal

Add a product UI feature that lets an editor fill the current vocabulary form from one Serbian word through OpenAI.

This is an editor-assist feature for the existing manual word editor. It is not the CLI importer, not a batch workflow, not a chat interface, and not Russian-to-Serbian card creation.

Generated stress data should also improve the product presentation: when structured stress is available, the stressed syllable is emphasized inside the Serbian word instead of being shown only as separate metadata.

## Current Product Context

Slovnik already has a password-gated manual vocabulary editor at `/editor` and `/editor/:id`. The editor can create and update rows in `vocabulary_items` with:

- `serbian_cyrillic`
- `serbian_latin`
- `russian_translation`
- `cefr_level`
- `theme`
- optional `usage_register`
- optional `stress_marker`
- optional `meaning_notes`
- optional `example_sentences`
- optional `example_translations`

Vocabulary writes are protected with `X-Editor-Password`. The MVP does not currently have product AI generation, persistent AI generation storage, or duplicate detection beyond ordinary manual editing behavior.

The separate vocabulary importer design remains a local/server artifact pipeline. This feature is deliberately separate: it runs from the product editor through the backend and uses OpenAI rather than local LM Studio.

## User-Facing Flow

The v1 flow is inline AI fill:

1. The editor opens `/editor` or `/editor/:id`.
2. The editor enters `editor_password` and unlocks the form.
3. A compact `AI fill` block appears above the vocabulary form.
4. The editor enters exactly one Serbian word in a dedicated AI input.
5. The editor clicks `Fill with AI`.
6. The frontend sends the word to the backend with `X-Editor-Password`; when editing an existing word, it also sends the current word id.
7. The backend checks whether the word already exists in `vocabulary_items`, excluding the current word id when one was supplied.
8. If another vocabulary row already contains the word, the backend returns `already_exists` and the frontend shows a message plus a button to open the existing word for editing.
9. If it does not exist, the backend checks the persistent AI generation store.
10. If a stored generation exists, the backend returns it without calling OpenAI.
11. If no stored generation exists, the backend calls OpenAI, validates the result shape, stores any successfully parsed result, and returns it.
12. Before applying a returned AI result, the frontend stores the current form values in an in-memory undo snapshot.
13. Returned fields overwrite the corresponding fields in the form.
14. If the result is partial, required fields that remain empty are highlighted.
15. The editor can edit the result manually and save through the existing create/update flow.
16. The editor can restore the previous form values while the current editor page remains open.

## Scope

In scope for v1:

- AI fill is available only after successful editor password verification.
- The AI input accepts one Serbian word only.
- The input may be Serbian Latin or Serbian Cyrillic.
- The backend normalizes the lookup key with Unicode NFC, `trim`, and `casefold`.
- Duplicate checks use strict normalized matching against existing Serbian headword fields.
- Persistent generation lookup uses the same normalized key.
- Stored AI generations are reused to save time and OpenAI cost.
- There is no v1 regenerate button.
- Partial generated results are valid draft output and are persisted.
- AI may return structured syllable and stress data for both Serbian scripts.
- When structured stress is available, product word displays emphasize the full stressed syllable inside both Serbian spellings.
- Strong technical failures do not mutate the form.
- OpenAI errors are logged in structured logs without secrets.

Out of scope for v1:

- Russian-to-Serbian card creation.
- Batch generation from a list of words.
- Multi-word phrase generation.
- Chat-style prompting.
- AI review queues or admin dashboards.
- Versioned regeneration by model or prompt version.
- Semantic duplicate detection, lemmatization, or form matching.
- Importer integration.

## Frontend Design

Update `frontend/src/views/WordEditorView.vue` so the unlocked editor shows a compact AI block above the existing form.

The block contains:

- A label and input for one Serbian word.
- A `Fill with AI` button.
- Loading state while the request is running.
- An info/success message when fields are filled.
- A `Restore previous values` action when an undo snapshot exists.
- An `already exists` message with a button/link to `/editor/:id`.
- A strong-error balloon/toast for failures that should not modify the form.

The AI input is deliberately separate from `serbian_cyrillic` and `serbian_latin`. This keeps the generation source separate from the saved vocabulary payload and avoids hidden rules such as "use whichever Serbian field happens to be filled."

The frontend behavior:

- Disable the AI button when the AI input is empty or a request is in flight.
- Save a copy of the current form state before applying any `generated` result.
- Apply only fields returned by the backend.
- Keep ordinary save validation in place.
- Highlight required fields left empty after partial generation.
- Let the editor review and manually adjust the syllable split and stressed syllable before saving.
- Render a structured stress preview by wrapping the selected syllable in `<strong>`; never render model-provided HTML.
- Do not store the undo snapshot in localStorage or on the backend.
- Do not expose `OPENAI_API_KEY` to the browser.

Reusable product word displays should use the same stress-rendering component or helper. Given a valid `stress_pattern`, it renders each syllable through ordinary Vue text interpolation and wraps only the syllable at `stressed_syllable_index` in `<strong>`. It must not use `v-html`. Cyrillic and Latin use their own syllable arrays because corresponding syllables may have different character lengths, for example `љу` and `lju`.

The v1 rendering surfaces are:

- `WordCard.vue`, which covers new-word and review sessions.
- Serbian headwords in `VocabularyListView.vue`.
- The structured stress preview in `WordEditorView.vue`.

Quiz prompts, answer reveals, results, and example sentences keep their current plain-string contracts in v1. Extending stress emphasis to those surfaces is deferred because it requires a separate quiz snapshot/API design.

The existing `stress_marker` remains available as a legacy fallback. When `stress_pattern` is absent and `stress_marker` is present, the UI continues showing the old marker as metadata. It must not guess a substring to emphasize from an unstructured legacy value.

### Manual Stress Control

The editor uses a deterministic text-and-selection control:

- One input contains Cyrillic syllables separated by a middle dot, for example `ра·ди·ти`.
- One input contains Latin syllables separated by a middle dot, for example `ra·di·ti`.
- When both inputs contain the same number of valid syllables and reconstruct the current headwords, the UI shows aligned syllable buttons.
- Clicking a syllable selects one shared zero-based `stressed_syllable_index` and updates the preview.
- A `Clear structured stress` action sets `stress_pattern` to null without changing the legacy `stress_marker`.

If either Serbian headword changes and the existing syllable arrays no longer reconstruct it, the frontend immediately marks the structured control invalid and excludes the stale `stress_pattern` from save until the editor fixes the split or clears it. Invalid optional stress must not block saving the rest of the card. The existing free-form `stress_marker` input remains available in v1 for legacy values, but AI fill does not populate it.

## Backend API

Add a thin vocabulary router endpoint:

```text
POST /api/vocabulary/ai-fill
```

Headers:

```text
X-Editor-Password: <editor password>
```

Request:

```json
{
  "source_word": "raditi",
  "current_word_id": 123
}
```

`current_word_id` is optional. The frontend sends it only on `/editor/:id`. The backend uses it only to exclude the currently edited row from duplicate lookup; it must not grant access to edit that row or skip editor password verification.

Responses should be modeled as a discriminated union.

Generated response:

```json
{
  "status": "generated",
  "source": "openai",
  "payload": {
    "serbian_cyrillic": "радити",
    "serbian_latin": "raditi",
    "russian_translation": "делать, работать",
    "cefr_level": "A1",
    "theme": "daily-life",
    "stress_pattern": {
      "cyrillic_syllables": ["ра", "ди", "ти"],
      "latin_syllables": ["ra", "di", "ti"],
      "stressed_syllable_index": 0
    },
    "meaning_notes": "Глагол для действий и работы.",
    "example_sentences": "Šta radiš?",
    "example_translations": "Что ты делаешь?"
  },
  "missing_required_fields": []
}
```

Stored generated response:

```json
{
  "status": "generated",
  "source": "store",
  "payload": {
    "serbian_latin": "raditi",
    "russian_translation": "делать, работать"
  },
  "missing_required_fields": ["serbian_cyrillic", "cefr_level", "theme"]
}
```

Already-existing response:

```json
{
  "status": "already_exists",
  "word_id": 123,
  "message": "Word already exists."
}
```

Strong technical errors should use ordinary HTTP errors with frontend-safe messages. The backend should log the technical details separately.

Error responses should use a stable body:

```json
{
  "code": "openai_unavailable",
  "message": "AI fill is temporarily unavailable."
}
```

Expected v1 error codes:

- `invalid_source_word`, 422: empty input, too-long input, or input that appears to contain more than one word.
- `invalid_editor_password`, 403: existing editor password failure.
- `openai_not_configured`, 503: missing or unusable OpenAI backend configuration.
- `openai_rate_limited`, 503: OpenAI rate limit.
- `openai_timeout`, 503: OpenAI timeout.
- `openai_unavailable`, 503: OpenAI service failure.
- `invalid_ai_response`, 502: response did not match the expected shape after parsing/validation.

The frontend may show the returned `message`, but should branch on `code` in tests and state handling.

## AI Fill Payload Contract

The API response uses an `AiFillPayload`, not the full create/update vocabulary schema.

The payload may contain these keys:

- `serbian_cyrillic`
- `serbian_latin`
- `russian_translation`
- `cefr_level`
- `theme`
- `usage_register`
- `stress_pattern`
- `meaning_notes`
- `example_sentences`
- `example_translations`

Required vocabulary fields are optional in `AiFillPayload` so partial drafts can be returned. If a required field is present, it must be a non-empty string after trimming. Required fields are considered missing when they are absent, empty, or null in the parsed AI result. The backend should not include null required fields in the response payload.

`AiFillPayload` is a patch produced by the backend, not the model's raw Structured Output. It contains only validated, non-null generated fields. If a key is omitted, the frontend leaves the existing form value unchanged. AI fill never clears an existing form field in v1; a human can clear optional values manually.

The raw OpenAI schema contains every known property and uses `null` for uncertain values so it is compatible with strict Structured Outputs. The backend converts that full nullable object into `AiFillPayload` by dropping null and unusable fields. Stored `generated_payload` uses the same non-null patch semantics as the API response.

A generated result is minimally usable only when the validated patch contains `russian_translation` and at least one of `serbian_cyrillic` or `serbian_latin`. A result below this threshold returns `invalid_ai_response` and is not persisted. This prevents an empty or echoed-only result from becoming the permanent stored generation when v1 has no regenerate action.

### Stress Pattern Contract

`stress_pattern` is an optional structured object:

```json
{
  "cyrillic_syllables": ["ра", "ди", "ти"],
  "latin_syllables": ["ra", "di", "ti"],
  "stressed_syllable_index": 0
}
```

The index is zero-based and identifies the same spoken syllable in both arrays. The backend validates that:

- Both arrays contain the same non-zero number of non-empty strings.
- Concatenating `cyrillic_syllables` equals `serbian_cyrillic`.
- Concatenating `latin_syllables` equals `serbian_latin`.
- `stressed_syllable_index` exists in both arrays.

The comparisons use Unicode NFC normalization and exact script-specific text after normalization. Generated `stress_pattern` is accepted only when the same raw model output also contains valid, non-null `serbian_cyrillic` and `serbian_latin`; it is not validated against pre-existing frontend values. If either spelling is absent, or generated stress data is otherwise invalid while the rest of the AI payload is usable, the backend omits `stress_pattern`, persists the remaining partial payload, and logs an `invalid_stress_pattern` validation category. Invalid stress alone must not turn a usable card draft into `invalid_ai_response`.

Manual create/update payloads may include `stress_pattern`. The editor exposes the syllable split and selected stress so a human can correct AI output or enter stress manually. The existing `stress_marker` field remains readable and writable during v1 for backward compatibility, but AI fill does not generate it.

## Backend Service Boundaries

Keep the router thin. Put product rules in a focused service, for example `ai_vocabulary_service.py`.

The service owns:

- Source word validation.
- Normalized key generation.
- Existing vocabulary lookup.
- Persistent generation lookup.
- OpenAI request orchestration.
- Deterministic validation of generated fields.
- Missing required field calculation.
- Persistence of parsed generation results.
- Structured error logging.

The service should not own:

- Manual vocabulary create/update behavior.
- Importer artifact processing.
- Frontend form state.
- User authentication beyond reusing the existing editor password dependency.

## Data Model

Add a persistent table such as `ai_vocabulary_generations`.

Suggested columns:

- `id`
- `source_word`
- `normalized_source_word`, unique
- `generated_payload`, JSON/Text
- `missing_required_fields`, JSON/Text
- `model`
- `prompt_version`
- `created_at`
- `updated_at`

The v1 lookup key is only `normalized_source_word`.

Store `model` and `prompt_version` for observability and future migrations, but do not use them to bypass stored results in v1. Repeated requests for the same normalized word return the stored generation.

Only successfully parsed AI results are persisted. Strong OpenAI failures, invalid response shapes, timeouts, and rate limits are logged but are not stored as reusable generation results.

Concurrent first-time requests for the same normalized word may race. The implementation should treat `normalized_source_word` as the uniqueness boundary and use transaction/upsert behavior: if inserting the newly generated row hits a unique-key conflict, re-read the existing row and return it as `source = "store"` instead of failing the request or writing a duplicate row.

Add a nullable `stress_pattern` JSON column to `vocabulary_items`. Keep the existing nullable `stress_marker` column in v1 so migrations do not discard legacy editor data. New structured stress takes display precedence; no automatic conversion of free-form legacy markers is attempted.

## Duplicate Lookup

Before checking the AI generation table or calling OpenAI, the backend checks existing vocabulary rows.

For v1, duplicate lookup is strict normalized matching:

- Normalize input with Unicode NFC, `trim`, and `casefold`.
- Compare against normalized `serbian_latin`.
- Compare against normalized `serbian_cyrillic`.

No Serbian morphology, transliteration equivalence, lemma matching, fuzzy matching, or semantic duplicate detection is included in v1.

When the request includes `current_word_id`, duplicate lookup excludes that row. This lets editors use AI fill while editing the current card without the current card blocking its own generation. If any other existing word is found, the backend returns `already_exists` with the word id. The frontend shows a message and offers a button to open that word in the editor. It does not auto-navigate and does not overwrite the current form.

## OpenAI Integration

Use the OpenAI API from the backend only.

Configuration:

- `OPENAI_API_KEY` is required for the feature to call OpenAI.
- `OPENAI_MODEL` is configurable and defaults to `gpt-5.6-luna`, the current efficient GPT-5.6 variant suited to a small structured extraction request.
- `PROMPT_VERSION` should be a code constant stored with each generation.

The integration should use the Responses API for direct text-generation requests and Structured Outputs with a JSON Schema for predictable field extraction. OpenAI's current docs describe the Responses API as the recommended API for text-generation apps and document JSON Schema-based Structured Outputs.

The prompt should clearly state:

- Input is one Serbian word.
- The target learner is Russian-speaking.
- Output is a Slovnik vocabulary card draft.
- Return `null` for uncertain fields.
- When stress is known, split both Serbian spellings into corresponding syllables and identify the full stressed syllable with a shared zero-based index.
- Do not invent a phrase or list of alternatives when the input is not a single Serbian word.

The strict response schema should require every known property while allowing `null` for uncertain values and disallowing unexpected fields. The backend, not the model schema, converts this full nullable result into the partial `AiFillPayload` patch returned to the frontend.

Backend validation should enforce:

- Known payload keys only.
- Valid CEFR level when present.
- `theme` is one of the controlled themes listed below when present.
- The minimum usable result contains a Russian translation and at least one Serbian spelling.
- Valid `stress_pattern` structure and correspondence with both generated Serbian spellings when present.
- Length limits compatible with the existing app schema.
- Missing required fields calculation for `serbian_cyrillic`, `serbian_latin`, `russian_translation`, `cefr_level`, and `theme`.

### Theme Classification

AI fill should use the same controlled theme set as the importer design so AI-created content does not fragment vocabulary filters with arbitrary free-form themes.

Allowed values:

- `greetings`
- `personal-info`
- `family-relationships`
- `home`
- `daily-life`
- `food-drink`
- `shopping-money`
- `travel-transport`
- `places-directions`
- `health-body`
- `education`
- `work`
- `free-time`
- `nature-weather`
- `services`
- `language-communication`
- `technology-media`
- `emotions-qualities`
- `time-numbers`
- `grammar-functions`
- `other`

The prompt should tell the model to use `other` only when none of the specific themes fit.

## Error Handling

Business states:

- `already_exists`: frontend shows a message and an edit button.
- `generated` with full payload: frontend fills the form and shows success.
- `generated` with partial payload: frontend fills returned fields, highlights missing required fields, and lets the editor finish manually.
- `generated` from `store`: frontend may show neutral copy such as "Used saved AI result."

Recoverable technical errors:

- OpenAI timeout.
- OpenAI rate limit.
- OpenAI unavailable.
- Missing or invalid OpenAI configuration.
- Invalid model response shape.

For these errors, the frontend shows a strong error balloon/toast and does not mutate the form.

Validation errors:

- Empty source word.
- Source input appears to contain more than one word by a simple whitespace split.
- Source word is too long.

These should return 400/422 with frontend-safe copy.

Logs should include enough context to debug:

- `normalized_source_word`
- model
- prompt version
- error category
- OpenAI request id when available

Logs must not include:

- API keys
- secrets
- full authorization headers

## Localization

All visible frontend copy added for this feature must be added to `frontend/src/i18n/messages.ts` for both `ru` and `sr`.

This includes:

- AI block title and input label.
- Fill button.
- Loading text.
- Success/info text for OpenAI and stored results.
- Restore previous values action.
- Already-exists message and edit button text.
- Missing required field hint.
- Strong error fallback text.

Frontend tests should verify that the AI block can render in both supported UI languages.

## Testing

Backend tests:

- Source normalization: `Raditi`, `raditi`, and ` raditi ` share one key.
- More-than-one-word input is rejected.
- Existing vocabulary match returns `already_exists` before any store/OpenAI lookup.
- Existing vocabulary match excludes `current_word_id` on edit.
- Store hit returns stored payload before any OpenAI call.
- OpenAI success persists the parsed generation.
- Partial OpenAI result is persisted and reports missing required fields.
- Raw nulls, omitted API patch fields, and missing required fields follow the `AiFillPayload` contract.
- The full nullable model result is converted to a non-null API patch without clearing existing frontend fields.
- Empty, echoed-only, or otherwise below-threshold results return `invalid_ai_response` and are not persisted.
- Valid structured stress is accepted when both syllable arrays reconstruct their corresponding words.
- Structured stress is omitted when either generated Serbian spelling is absent.
- Invalid stress index, unequal syllable counts, or mismatched reconstructed words cause only `stress_pattern` to be omitted.
- Manual vocabulary create/update accepts valid `stress_pattern` while legacy `stress_marker` remains compatible.
- Invalid OpenAI shape returns a technical error and is not persisted.
- Unique-key conflict during generation insert re-reads and returns the stored row.
- Stable error codes are returned for validation, OpenAI configuration, OpenAI failures, and invalid AI responses.
- Editor password protects the endpoint.
- Migration creates `ai_vocabulary_generations` with a unique normalized key.
- Migration adds nullable structured stress storage without dropping `stress_marker`.

Frontend tests:

- AI block appears only after editor unlock.
- Empty AI input disables the fill button.
- Generated result applies fields to the form.
- Generated stress can be reviewed and manually adjusted before save.
- Middle-dot syllable inputs and the shared index produce a valid `stress_pattern`; clear removes only structured stress.
- Editing a headword invalidates and excludes a stale structured pattern without blocking the rest of the save.
- Word displays emphasize the complete stressed syllable in both Serbian scripts.
- Latin digraph and Cyrillic single-letter syllables render correctly from separate arrays.
- Invalid or absent structured stress never causes raw HTML rendering or guessed emphasis.
- Legacy `stress_marker` remains visible as metadata when no `stress_pattern` exists.
- Quiz and results views retain their current plain-string rendering.
- Previous values can be restored after applying AI output.
- Partial result highlights missing required fields.
- `already_exists` shows a message and edit link/button.
- Strong errors preserve the current form.
- AI feature copy renders in Russian and Serbian.

Verification:

- Backend: `cd backend && .venv/bin/ruff check .`
- Backend: `cd backend && .venv/bin/pytest -v`
- Frontend: `cd frontend && npm run test:unit`
- Frontend: `cd frontend && npm run build`
- Frontend: `cd frontend && npm run test:e2e`

## Documentation Updates During Implementation

When this design is implemented, update:

- `README.md` with `OPENAI_API_KEY`, `OPENAI_MODEL`, endpoint behavior, and verification notes.
- `.env.example` with OpenAI-related environment variables.
- `docs/product-state.md` with the new product capability, backend API, data model, setup caveats, and verification status.

Do not update `docs/product-state.md` merely for this design document; update it when product behavior or setup actually changes.

## Open Questions Deferred

- Whether a future "Regenerate" action should bypass the stored generation.
- Whether Russian-to-Serbian card creation should become a separate feature.
- Whether phrase generation should be supported later.
- Whether stored AI generations need an admin review/debug UI.
- Whether quiz prompts, answer reveals, and results should carry structured stress data.

## References

- OpenAI Text generation guide: `https://developers.openai.com/api/docs/guides/text`
- OpenAI Structured Outputs guide: `https://developers.openai.com/api/docs/guides/structured-outputs`
- OpenAI model guidance: `https://developers.openai.com/api/docs/guides/latest-model`
- OpenAI `gpt-5.6-luna` model reference: `https://developers.openai.com/api/docs/models/gpt-5.6-luna`
- Product audit: `docs/product-state.md`
- Existing importer design: `docs/superpowers/specs/2026-07-06-vocabulary-importer-design.md`
