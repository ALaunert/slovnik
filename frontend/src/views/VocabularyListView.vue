<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { listVocabulary, listVocabularyThemes, verifyEditorPassword, type VocabularyWord } from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const levels = ["", "A1", "A2", "B1", "B2", "C1", "C2"];
const selectedLevel = ref("");
const selectedTheme = ref("");
const editorPassword = ref("");
const words = ref<VocabularyWord[]>([]);
const themes = ref<string[]>([]);
const error = ref("");
const unlockStatus = ref("");
const isEditorUnlocked = ref(false);
const canEdit = computed(() => isEditorUnlocked.value);
const copy = computed(() => messages[sessionStore.uiLanguage.value]);

watch(editorPassword, () => {
  isEditorUnlocked.value = false;
  unlockStatus.value = "";
});

async function loadWords() {
  error.value = "";
  try {
    words.value = await listVocabulary({
      cefr_level: selectedLevel.value || undefined,
      theme: selectedTheme.value || undefined,
    });
    themes.value = await listVocabularyThemes();
  } catch {
    error.value = copy.value.loadVocabularyError;
  }
}

async function unlockEditor() {
  error.value = "";
  unlockStatus.value = "";
  try {
    await verifyEditorPassword(editorPassword.value);
    isEditorUnlocked.value = true;
    unlockStatus.value = copy.value.unlocked;
  } catch {
    isEditorUnlocked.value = false;
    error.value = copy.value.unlockError;
  }
}

onMounted(loadWords);
</script>

<template>
  <main class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ copy.vocabularyEyebrow }}</p>
        <h1>{{ copy.vocabulary }}</h1>
      </div>
      <RouterLink to="/dashboard">{{ copy.backToDashboard }}</RouterLink>
    </header>

    <section class="panel stack">
      <div class="filter-row">
        <label>{{ copy.level }}
          <select v-model="selectedLevel" @change="loadWords">
            <option v-for="level in levels" :key="level" :value="level">{{ level || copy.all }}</option>
          </select>
        </label>
        <label>{{ copy.theme }}
          <select v-model="selectedTheme" @change="loadWords">
            <option value="">{{ copy.all }}</option>
            <option v-for="theme in themes" :key="theme" :value="theme">{{ theme }}</option>
          </select>
        </label>
        <label>{{ copy.editorPassword }}
          <input v-model="editorPassword" type="password" autocomplete="current-password" />
        </label>
        <button type="button" :disabled="!editorPassword" @click="unlockEditor">{{ copy.unlock }}</button>
        <RouterLink v-if="canEdit" class="button-link" to="/editor">{{ copy.add }}</RouterLink>
      </div>
      <p v-if="unlockStatus" class="success">{{ unlockStatus }}</p>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-else-if="words.length === 0" class="muted">{{ copy.emptyVocabulary }}</p>
      <ul v-else class="word-list">
        <li v-for="word in words" :key="word.id" class="word-row">
          <div>
            <strong>{{ word.serbian_cyrillic }}</strong>
            <span>{{ word.serbian_latin }}</span>
          </div>
          <span>{{ word.russian_translation }}</span>
          <span>{{ word.cefr_level }} · {{ word.theme }}</span>
          <RouterLink v-if="canEdit" :to="`/editor/${word.id}`">{{ copy.edit }}</RouterLink>
        </li>
      </ul>
    </section>
  </main>
</template>
