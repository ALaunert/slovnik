<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import {
  AiFillApiError,
  createVocabularyWord,
  fillVocabularyWithAi,
  getVocabularyWord,
  updateVocabularyWord,
  verifyEditorPassword,
  type AiFillPayload,
  type StressPattern,
  type VocabularyPayload,
} from "../api/client";
import StressEditor from "../components/StressEditor.vue";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

type RequiredField =
  | "serbian_cyrillic"
  | "serbian_latin"
  | "russian_translation"
  | "cefr_level"
  | "theme";
type AiInfoState = "openai" | "store" | "already_exists" | null;

const route = useRoute();
const wordId = computed(() => {
  const raw = route.params.id;
  const value = Array.isArray(raw) ? raw[0] : raw;
  if (!value) return null;
  const id = Number(value);
  return Number.isFinite(id) ? id : null;
});
const editorPassword = ref("");
const status = ref("");
const error = ref("");
const isEditorUnlocked = ref(false);
const verifiedEditorPassword = ref("");
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const form = reactive<VocabularyPayload>({
  serbian_cyrillic: "",
  serbian_latin: "",
  russian_translation: "",
  cefr_level: "A1",
  theme: "",
  usage_register: "",
  stress_marker: "",
  stress_pattern: null,
  meaning_notes: "",
  example_sentences: "",
  example_translations: "",
});

const aiSourceWord = ref("");
const isAiLoading = ref(false);
const aiInfoState = ref<AiInfoState>(null);
const aiError = ref("");
const existingWordId = ref<number | null>(null);
const undoSnapshot = ref<VocabularyPayload | null>(null);
const showAiMissingFields = ref(false);
let aiRequestId = 0;
let routeLoadRequestId = 0;
let unlockRequestId = 0;

const requiredFields: RequiredField[] = [
  "serbian_cyrillic",
  "serbian_latin",
  "russian_translation",
  "cefr_level",
  "theme",
];
const missingRequiredFields = computed<RequiredField[]>(() => {
  if (!showAiMissingFields.value) return [];
  return requiredFields.filter((field) => !String(form[field] ?? "").trim());
});
const stressPattern = computed({
  get: () => form.stress_pattern ?? null,
  set: (pattern: StressPattern | null) => {
    form.stress_pattern = pattern;
  },
});
const aiInfoMessage = computed(() => {
  if (aiInfoState.value === "openai") return copy.value.aiSuccessOpenai;
  if (aiInfoState.value === "store") return copy.value.aiSuccessStore;
  if (aiInfoState.value === "already_exists") return copy.value.aiAlreadyExists;
  return "";
});
const stressEditorLabels = computed(() => ({
  title: copy.value.structuredStressTitle,
  cyrillicSyllables: copy.value.cyrillicSyllables,
  latinSyllables: copy.value.latinSyllables,
  splitHint: copy.value.stressSplitHint,
  clear: copy.value.stressClear,
  invalidSplit: copy.value.stressInvalidSplit,
  preview: copy.value.stressPreview,
  selectStress: copy.value.stressSelect,
  syllableLabel: copy.value.stressSyllableLabel,
}));

function cloneStressPattern(pattern: StressPattern | null | undefined): StressPattern | null {
  if (!pattern) return null;
  return {
    cyrillic_syllables: [...pattern.cyrillic_syllables],
    latin_syllables: [...pattern.latin_syllables],
    stressed_syllable_index: pattern.stressed_syllable_index,
  };
}

function cloneFormState(source: VocabularyPayload): VocabularyPayload {
  return {
    serbian_cyrillic: source.serbian_cyrillic,
    serbian_latin: source.serbian_latin,
    russian_translation: source.russian_translation,
    cefr_level: source.cefr_level,
    theme: source.theme,
    usage_register: source.usage_register,
    stress_marker: source.stress_marker,
    stress_pattern: cloneStressPattern(source.stress_pattern),
    meaning_notes: source.meaning_notes,
    example_sentences: source.example_sentences,
    example_translations: source.example_translations,
  };
}

function applyFormState(source: VocabularyPayload) {
  form.serbian_cyrillic = source.serbian_cyrillic;
  form.serbian_latin = source.serbian_latin;
  form.russian_translation = source.russian_translation;
  form.cefr_level = source.cefr_level;
  form.theme = source.theme;
  form.usage_register = source.usage_register ?? "";
  form.stress_marker = source.stress_marker ?? "";
  form.stress_pattern = cloneStressPattern(source.stress_pattern);
  form.meaning_notes = source.meaning_notes ?? "";
  form.example_sentences = source.example_sentences ?? "";
  form.example_translations = source.example_translations ?? "";
}

function clearFormState() {
  applyFormState({
    serbian_cyrillic: "",
    serbian_latin: "",
    russian_translation: "",
    cefr_level: "A1",
    theme: "",
    usage_register: "",
    stress_marker: "",
    stress_pattern: null,
    meaning_notes: "",
    example_sentences: "",
    example_translations: "",
  });
}

function applyAiPayload(payload: AiFillPayload) {
  if (payload.serbian_cyrillic !== undefined) form.serbian_cyrillic = payload.serbian_cyrillic;
  if (payload.serbian_latin !== undefined) form.serbian_latin = payload.serbian_latin;
  if (payload.russian_translation !== undefined) form.russian_translation = payload.russian_translation;
  if (payload.cefr_level !== undefined) form.cefr_level = payload.cefr_level;
  if (payload.theme !== undefined) form.theme = payload.theme;
  if (payload.usage_register !== undefined) form.usage_register = payload.usage_register;
  if (payload.stress_pattern !== undefined) form.stress_pattern = cloneStressPattern(payload.stress_pattern);
  if (payload.meaning_notes !== undefined) form.meaning_notes = payload.meaning_notes;
  if (payload.example_sentences !== undefined) form.example_sentences = payload.example_sentences;
  if (payload.example_translations !== undefined) form.example_translations = payload.example_translations;
}

function validStressPatternOrNull(payload: VocabularyPayload): StressPattern | null {
  const pattern = payload.stress_pattern;
  if (!pattern) return null;

  const syllableCount = pattern.cyrillic_syllables.length;
  const segments = [...pattern.cyrillic_syllables, ...pattern.latin_syllables];
  const hasValidShape = (
    syllableCount > 0
    && syllableCount === pattern.latin_syllables.length
    && segments.every((segment) => segment.trim().length > 0)
    && Number.isInteger(pattern.stressed_syllable_index)
    && pattern.stressed_syllable_index >= 0
    && pattern.stressed_syllable_index < syllableCount
  );
  if (!hasValidShape) return null;

  const reconstructsCyrillic = (
    pattern.cyrillic_syllables.join("").normalize("NFC")
    === payload.serbian_cyrillic.normalize("NFC")
  );
  const reconstructsLatin = (
    pattern.latin_syllables.join("").normalize("NFC")
    === payload.serbian_latin.normalize("NFC")
  );
  return reconstructsCyrillic && reconstructsLatin ? pattern : null;
}

function isMissing(field: RequiredField): boolean {
  return missingRequiredFields.value.includes(field);
}

function aiErrorMessage(cause: unknown): string {
  if (!(cause instanceof AiFillApiError)) return copy.value.aiErrorFallback;
  const messagesByCode: Record<string, string> = {
    invalid_source_word: copy.value.aiErrorInvalidSource,
    invalid_editor_password: copy.value.aiErrorInvalidPassword,
    openai_not_configured: copy.value.aiErrorNotConfigured,
    openai_rate_limited: copy.value.aiErrorRateLimited,
    openai_timeout: copy.value.aiErrorTimeout,
    openai_unavailable: copy.value.aiErrorUnavailable,
    invalid_ai_response: copy.value.aiErrorInvalidResponse,
    ai_fill_failed: copy.value.aiErrorFallback,
  };
  return messagesByCode[cause.code] ?? (cause.message.trim() || copy.value.aiErrorFallback);
}

onMounted(() => {
  isEditorUnlocked.value = false;
});

watch(editorPassword, (password) => {
  unlockRequestId += 1;
  if (verifiedEditorPassword.value && password !== verifiedEditorPassword.value) {
    aiRequestId += 1;
    isAiLoading.value = false;
    isEditorUnlocked.value = false;
    verifiedEditorPassword.value = "";
    status.value = "";
    aiError.value = "";
    aiInfoState.value = null;
    existingWordId.value = null;
    undoSnapshot.value = null;
    showAiMissingFields.value = false;
  }
});

watch(wordId, async (nextWordId, previousWordId) => {
  if (nextWordId === previousWordId) return;

  unlockRequestId += 1;
  aiRequestId += 1;
  isAiLoading.value = false;
  aiInfoState.value = null;
  aiError.value = "";
  existingWordId.value = null;
  undoSnapshot.value = null;
  showAiMissingFields.value = false;
  const loadRequestId = ++routeLoadRequestId;
  if (nextWordId === null) clearFormState();
  const hasVerifiedRouteAccess = (
    isEditorUnlocked.value
    || (
      verifiedEditorPassword.value.length > 0
      && verifiedEditorPassword.value === editorPassword.value
    )
  );
  if (!hasVerifiedRouteAccess) return;

  const routePassword = verifiedEditorPassword.value;
  isEditorUnlocked.value = false;
  status.value = "";
  error.value = "";
  if (nextWordId === null) {
    isEditorUnlocked.value = true;
    status.value = copy.value.unlocked;
    return;
  }

  try {
    const word = await getVocabularyWord(nextWordId);
    if (
      loadRequestId !== routeLoadRequestId
      || nextWordId !== wordId.value
      || routePassword !== editorPassword.value
      || routePassword !== verifiedEditorPassword.value
    ) return;
    applyFormState(word);
    isEditorUnlocked.value = true;
    status.value = copy.value.unlocked;
  } catch {
    if (loadRequestId !== routeLoadRequestId || nextWordId !== wordId.value) return;
    verifiedEditorPassword.value = "";
    error.value = copy.value.loadWordError;
  }
});

async function unlockEditor() {
  const requestId = ++unlockRequestId;
  routeLoadRequestId += 1;
  const submittedPassword = editorPassword.value;
  const submittedWordId = wordId.value;
  const isCurrentRequest = () => (
    requestId === unlockRequestId
    && submittedPassword === editorPassword.value
    && submittedWordId === wordId.value
  );
  status.value = "";
  error.value = "";
  try {
    await verifyEditorPassword(submittedPassword);
  } catch {
    if (!isCurrentRequest()) return;
    isEditorUnlocked.value = false;
    verifiedEditorPassword.value = "";
    error.value = copy.value.unlockError;
    return;
  }
  if (!isCurrentRequest()) return;

  try {
    const word = submittedWordId === null
      ? null
      : await getVocabularyWord(submittedWordId);
    if (!isCurrentRequest()) return;
    if (word) {
      applyFormState(word);
    } else {
      clearFormState();
    }
  } catch {
    if (!isCurrentRequest()) return;
    isEditorUnlocked.value = false;
    verifiedEditorPassword.value = "";
    error.value = copy.value.loadWordError;
    return;
  }

  verifiedEditorPassword.value = submittedPassword;
  isEditorUnlocked.value = true;
  status.value = copy.value.unlocked;
}

async function fillWithAi() {
  const sourceWord = aiSourceWord.value.trim();
  if (!isEditorUnlocked.value || !sourceWord || isAiLoading.value) return;

  const requestId = ++aiRequestId;
  const requestPassword = verifiedEditorPassword.value;
  const requestWordId = wordId.value;
  isAiLoading.value = true;
  aiError.value = "";
  aiInfoState.value = null;
  existingWordId.value = null;

  try {
    const response = await fillVocabularyWithAi(
      sourceWord,
      requestPassword,
      requestWordId ?? undefined,
    );
    if (
      requestId !== aiRequestId
      || !isEditorUnlocked.value
      || requestPassword !== verifiedEditorPassword.value
      || requestWordId !== wordId.value
    ) return;

    if (response.status === "already_exists") {
      aiInfoState.value = "already_exists";
      existingWordId.value = response.word_id;
      return;
    }

    undoSnapshot.value = cloneFormState(form);
    applyAiPayload(response.payload);
    showAiMissingFields.value = true;
    aiInfoState.value = response.source;
  } catch (cause) {
    if (requestId === aiRequestId) aiError.value = aiErrorMessage(cause);
  } finally {
    if (requestId === aiRequestId) isAiLoading.value = false;
  }
}

function restorePreviousValues() {
  if (!undoSnapshot.value) return;
  applyFormState(undoSnapshot.value);
  undoSnapshot.value = null;
  showAiMissingFields.value = false;
  aiInfoState.value = null;
  existingWordId.value = null;
}

async function saveWord() {
  status.value = "";
  error.value = "";
  const hasMissingRequiredField = requiredFields.some(
    (field) => !String(form[field] ?? "").trim(),
  );
  if (!isEditorUnlocked.value || !editorPassword.value || hasMissingRequiredField) {
    error.value = copy.value.requiredFieldsError;
    return;
  }
  try {
    form.stress_pattern = validStressPatternOrNull(form);
    const payload = cloneFormState(form);
    if (wordId.value) {
      await updateVocabularyWord(wordId.value, payload, editorPassword.value);
    } else {
      await createVocabularyWord(payload, editorPassword.value);
    }
    showAiMissingFields.value = false;
    status.value = copy.value.wordSaved;
  } catch {
    error.value = copy.value.saveWordError;
  }
}
</script>

<template>
  <main class="page" :class="{ 'has-toast': aiError }">
    <header class="page-header">
      <h1>{{ copy.editor }}</h1>
      <RouterLink to="/vocabulary">{{ copy.vocabulary }}</RouterLink>
    </header>
    <section class="panel stack">
      <form
        class="control-row"
        data-testid="unlock-form"
        @submit.prevent="unlockEditor"
      >
        <label>
          {{ copy.editorPassword }}
          <input v-model="editorPassword" name="editor_password" type="password" />
        </label>
        <button type="submit" :disabled="!editorPassword">{{ copy.unlock }}</button>
      </form>
      <p v-if="status" class="success">{{ status }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>

    <section v-if="isEditorUnlocked" class="panel editor-panel">
      <section class="ai-fill-section" data-testid="ai-fill">
        <div class="ai-fill-heading">
          <h2>{{ copy.aiBlockTitle }}</h2>
        </div>
        <div class="ai-fill-row">
          <label>
            {{ copy.aiSourceLabel }}
            <input
              v-model="aiSourceWord"
              name="ai_source_word"
              :placeholder="copy.aiSourcePlaceholder"
              :disabled="isAiLoading"
              @keydown.enter.prevent="fillWithAi"
            />
          </label>
          <button
            type="button"
            data-testid="ai-fill-button"
            :disabled="!aiSourceWord.trim() || isAiLoading"
            @click="fillWithAi"
          >
            {{ isAiLoading ? copy.aiFilling : copy.aiFill }}
          </button>
        </div>
        <div v-if="aiInfoMessage || undoSnapshot" class="ai-feedback">
          <span v-if="aiInfoMessage" role="status" data-testid="ai-info">{{ aiInfoMessage }}</span>
          <RouterLink
            v-if="existingWordId"
            class="button-link compact-button"
            :to="`/editor/${existingWordId}`"
            data-testid="existing-word-link"
          >
            {{ copy.aiEditExisting }}
          </RouterLink>
          <button
            v-if="undoSnapshot"
            type="button"
            class="secondary-button"
            data-testid="ai-restore"
            @click="restorePreviousValues"
          >
            {{ copy.aiRestore }}
          </button>
        </div>
        <p
          v-if="missingRequiredFields.length"
          class="field-hint error"
          data-testid="ai-missing-hint"
        >
          {{ copy.aiMissingHint }}
        </p>
      </section>

      <form
        class="form-grid"
        data-testid="word-form"
        @submit.prevent="saveWord"
      >
        <label
          data-field="serbian_cyrillic"
          :class="{ 'is-missing': isMissing('serbian_cyrillic') }"
        >
          {{ copy.serbianCyrillic }}
          <input v-model="form.serbian_cyrillic" name="serbian_cyrillic" required />
          <span
            v-if="isMissing('serbian_cyrillic')"
            class="field-hint"
            data-missing-field="serbian_cyrillic"
          >{{ copy.aiMissingField }}</span>
        </label>
        <label
          data-field="serbian_latin"
          :class="{ 'is-missing': isMissing('serbian_latin') }"
        >
          {{ copy.serbianLatin }}
          <input v-model="form.serbian_latin" name="serbian_latin" required />
          <span
            v-if="isMissing('serbian_latin')"
            class="field-hint"
            data-missing-field="serbian_latin"
          >{{ copy.aiMissingField }}</span>
        </label>
        <label
          data-field="russian_translation"
          :class="{ 'is-missing': isMissing('russian_translation') }"
        >
          {{ copy.russianTranslation }}
          <input v-model="form.russian_translation" name="russian_translation" required />
          <span
            v-if="isMissing('russian_translation')"
            class="field-hint"
            data-missing-field="russian_translation"
          >{{ copy.aiMissingField }}</span>
        </label>
        <label
          data-field="cefr_level"
          :class="{ 'is-missing': isMissing('cefr_level') }"
        >
          {{ copy.level }}
          <select v-model="form.cefr_level" name="cefr_level">
            <option>A1</option>
            <option>A2</option>
            <option>B1</option>
            <option>B2</option>
            <option>C1</option>
            <option>C2</option>
          </select>
          <span
            v-if="isMissing('cefr_level')"
            class="field-hint"
            data-missing-field="cefr_level"
          >{{ copy.aiMissingField }}</span>
        </label>
        <label
          data-field="theme"
          :class="{ 'is-missing': isMissing('theme') }"
        >
          {{ copy.theme }}
          <input v-model="form.theme" name="theme" required />
          <span
            v-if="isMissing('theme')"
            class="field-hint"
            data-missing-field="theme"
          >{{ copy.aiMissingField }}</span>
        </label>
        <label>
          {{ copy.register }}
          <input v-model="form.usage_register" name="usage_register" />
        </label>
        <label>
          {{ copy.stress }}
          <input v-model="form.stress_marker" name="stress_marker" />
        </label>
        <StressEditor
          v-model="stressPattern"
          :cyrillic-word="form.serbian_cyrillic"
          :latin-word="form.serbian_latin"
          :labels="stressEditorLabels"
        />
        <label class="wide">
          {{ copy.notes }}
          <textarea v-model="form.meaning_notes" name="meaning_notes" rows="3" />
        </label>
        <label class="wide">
          {{ copy.examples }}
          <textarea v-model="form.example_sentences" name="example_sentences" rows="3" />
        </label>
        <label class="wide">
          {{ copy.exampleTranslations }}
          <textarea v-model="form.example_translations" name="example_translations" rows="3" />
        </label>
        <button type="submit">{{ copy.save }}</button>
      </form>
    </section>

    <div v-if="aiError" class="ai-toast" role="alert">
      <span>{{ aiError }}</span>
      <button
        type="button"
        class="secondary-button"
        data-testid="dismiss-ai-error"
        @click="aiError = ''"
      >
        {{ copy.aiDismiss }}
      </button>
    </div>
  </main>
</template>
