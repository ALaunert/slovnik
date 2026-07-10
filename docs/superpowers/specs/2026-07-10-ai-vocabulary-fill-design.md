# AI Vocabulary Fill Design

Date: 2026-07-10

## Goal

Add a product UI feature that lets an editor fill the current vocabulary form from one Serbian word through OpenAI.

This is an editor-assist feature for the existing manual word editor. It is not the CLI importer, not a batch workflow, not a chat interface, and not Russian-to-Serbian card creation.

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
6. The frontend sends the word to the backend with `X-Editor-Password`.
7. The backend checks whether the word already exists in `vocabulary_items`.
8. If it exists, the backend returns `already_exists` and the frontend shows a message plus a button to open the existing word for editing.
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
- The backend normalizes the lookup key with `trim + casefold`.
- Duplicate checks use strict normalized matching against existing Serbian headword fields.
- Persistent generation lookup uses the same normalized key.
- Stored AI generations are reused to save time and OpenAI cost.
- There is no v1 regenerate button.
- Partial generated results are valid draft output and are persisted.
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
- Do not store the undo snapshot in localStorage or on the backend.
- Do not expose `OPENAI_API_KEY` to the browser.

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
  "source_word": "raditi"
}
```

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
    "usage_register": null,
    "stress_marker": null,
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

## Duplicate Lookup

Before checking the AI generation table or calling OpenAI, the backend checks existing vocabulary rows.

For v1, duplicate lookup is strict normalized matching:

- Normalize input with `trim + casefold`.
- Compare against normalized `serbian_latin`.
- Compare against normalized `serbian_cyrillic`.

No Serbian morphology, transliteration equivalence, lemma matching, fuzzy matching, or semantic duplicate detection is included in v1.

If an existing word is found, the backend returns `already_exists` with the word id. The frontend shows a message and offers a button to open that word in the editor. It does not auto-navigate and does not overwrite the current form.

## OpenAI Integration

Use the OpenAI API from the backend only.

Configuration:

- `OPENAI_API_KEY` is required for the feature to call OpenAI.
- `OPENAI_MODEL` should be configurable with a documented default.
- `PROMPT_VERSION` should be a code constant stored with each generation.

The integration should use the Responses API for direct text-generation requests and Structured Outputs with a JSON Schema for predictable field extraction. OpenAI's current docs describe the Responses API as the recommended API for text-generation apps and document JSON Schema-based Structured Outputs.

The prompt should clearly state:

- Input is one Serbian word.
- The target learner is Russian-speaking.
- Output is a Slovnik vocabulary card draft.
- It is acceptable to leave uncertain fields empty.
- Do not invent a phrase or list of alternatives when the input is not a single Serbian word.

The response schema should allow partial payloads while still enforcing a known object shape and no unexpected fields.

Backend validation should enforce:

- Known payload keys only.
- Valid CEFR level when present.
- String or null optional fields.
- Length limits compatible with the existing app schema.
- Missing required fields calculation for `serbian_cyrillic`, `serbian_latin`, `russian_translation`, `cefr_level`, and `theme`.

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

## Testing

Backend tests:

- Source normalization: `Raditi`, `raditi`, and ` raditi ` share one key.
- More-than-one-word input is rejected.
- Existing vocabulary match returns `already_exists` before any store/OpenAI lookup.
- Store hit returns stored payload before any OpenAI call.
- OpenAI success persists the parsed generation.
- Partial OpenAI result is persisted and reports missing required fields.
- Invalid OpenAI shape returns a technical error and is not persisted.
- Editor password protects the endpoint.
- Migration creates `ai_vocabulary_generations` with a unique normalized key.

Frontend tests:

- AI block appears only after editor unlock.
- Empty AI input disables the fill button.
- Generated result applies fields to the form.
- Previous values can be restored after applying AI output.
- Partial result highlights missing required fields.
- `already_exists` shows a message and edit link/button.
- Strong errors preserve the current form.

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

- Which OpenAI model should be the default for production.
- Whether a future "Regenerate" action should bypass the stored generation.
- Whether Russian-to-Serbian card creation should become a separate feature.
- Whether phrase generation should be supported later.
- Whether stored AI generations need an admin review/debug UI.

## References

- OpenAI Text generation guide: `https://developers.openai.com/api/docs/guides/text`
- OpenAI Structured Outputs guide: `https://developers.openai.com/api/docs/guides/structured-outputs`
- Product audit: `docs/product-state.md`
- Existing importer design: `docs/superpowers/specs/2026-07-06-vocabulary-importer-design.md`
