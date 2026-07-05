<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute } from "vue-router";

import {
  createVocabularyWord,
  getVocabularyWord,
  updateVocabularyWord,
  verifyEditorPassword,
  type VocabularyPayload,
} from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const route = useRoute();
const wordId = computed(() => {
  const raw = route.params.id;
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value ? Number(value) : null;
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
  meaning_notes: "",
  example_sentences: "",
  example_translations: "",
});

function applyWord(word: VocabularyPayload) {
  form.serbian_cyrillic = word.serbian_cyrillic;
  form.serbian_latin = word.serbian_latin;
  form.russian_translation = word.russian_translation;
  form.cefr_level = word.cefr_level;
  form.theme = word.theme;
  form.usage_register = word.usage_register ?? "";
  form.stress_marker = word.stress_marker ?? "";
  form.meaning_notes = word.meaning_notes ?? "";
  form.example_sentences = word.example_sentences ?? "";
  form.example_translations = word.example_translations ?? "";
}

async function loadWordForEdit() {
  if (!wordId.value) return;
  applyWord(await getVocabularyWord(wordId.value));
}

onMounted(() => {
  isEditorUnlocked.value = false;
});

watch(editorPassword, (password) => {
  if (isEditorUnlocked.value && password !== verifiedEditorPassword.value) {
    isEditorUnlocked.value = false;
    status.value = "";
  }
});

async function unlockEditor() {
  status.value = "";
  error.value = "";
  try {
    await verifyEditorPassword(editorPassword.value);
  } catch {
    isEditorUnlocked.value = false;
    verifiedEditorPassword.value = "";
    error.value = copy.value.unlockError;
    return;
  }

  try {
    await loadWordForEdit();
  } catch {
    isEditorUnlocked.value = false;
    verifiedEditorPassword.value = "";
    error.value = copy.value.loadWordError;
    return;
  }

  verifiedEditorPassword.value = editorPassword.value;
  isEditorUnlocked.value = true;
  status.value = copy.value.unlocked;
}

async function saveWord() {
  status.value = "";
  error.value = "";
  if (!isEditorUnlocked.value || !editorPassword.value || !form.serbian_cyrillic || !form.serbian_latin || !form.russian_translation || !form.theme) {
    error.value = copy.value.requiredFieldsError;
    return;
  }
  try {
    if (wordId.value) {
      await updateVocabularyWord(wordId.value, form, editorPassword.value);
    } else {
      await createVocabularyWord(form, editorPassword.value);
    }
    status.value = copy.value.wordSaved;
  } catch {
    error.value = copy.value.saveWordError;
  }
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>{{ copy.editor }}</h1>
      <RouterLink to="/vocabulary">{{ copy.vocabulary }}</RouterLink>
    </header>
    <section class="panel stack">
      <form class="control-row" @submit.prevent="unlockEditor">
        <label>{{ copy.editorPassword }}<input v-model="editorPassword" name="editor_password" type="password" /></label>
        <button type="submit" :disabled="!editorPassword">{{ copy.unlock }}</button>
      </form>
      <p v-if="status" class="success">{{ status }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
    <form v-if="isEditorUnlocked" class="panel form-grid" @submit.prevent="saveWord">
      <label>{{ copy.serbianCyrillic }}<input v-model="form.serbian_cyrillic" name="serbian_cyrillic" required /></label>
      <label>{{ copy.serbianLatin }}<input v-model="form.serbian_latin" name="serbian_latin" required /></label>
      <label>{{ copy.russianTranslation }}<input v-model="form.russian_translation" name="russian_translation" required /></label>
      <label>{{ copy.level }}<select v-model="form.cefr_level" name="cefr_level"><option>A1</option><option>A2</option><option>B1</option><option>B2</option><option>C1</option><option>C2</option></select></label>
      <label>{{ copy.theme }}<input v-model="form.theme" name="theme" required /></label>
      <label>{{ copy.register }}<input v-model="form.usage_register" name="usage_register" /></label>
      <label>{{ copy.stress }}<input v-model="form.stress_marker" name="stress_marker" /></label>
      <label class="wide">{{ copy.notes }}<textarea v-model="form.meaning_notes" name="meaning_notes" rows="3" /></label>
      <label class="wide">{{ copy.examples }}<textarea v-model="form.example_sentences" name="example_sentences" rows="3" /></label>
      <label class="wide">{{ copy.exampleTranslations }}<textarea v-model="form.example_translations" name="example_translations" rows="3" /></label>
      <button type="submit">{{ copy.save }}</button>
    </form>
  </main>
</template>
