<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink } from "vue-router";

import { listVocabulary, listVocabularyThemes, type VocabularyWord } from "../api/client";

const levels = ["", "A1", "A2", "B1", "B2", "C1", "C2"];
const selectedLevel = ref("");
const selectedTheme = ref("");
const editorPassword = ref("");
const words = ref<VocabularyWord[]>([]);
const themes = ref<string[]>([]);
const error = ref("");
const canEdit = computed(() => editorPassword.value.trim().length > 0);

async function loadWords() {
  error.value = "";
  try {
    words.value = await listVocabulary({
      cefr_level: selectedLevel.value || undefined,
      theme: selectedTheme.value || undefined,
    });
    themes.value = await listVocabularyThemes();
  } catch {
    error.value = "Не удалось загрузить словарь";
  }
}

onMounted(loadWords);
</script>

<template>
  <main class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">Rečnik</p>
        <h1>Словарь</h1>
      </div>
      <RouterLink to="/dashboard">Сегодня</RouterLink>
    </header>

    <section class="panel stack">
      <div class="filter-row">
        <label>Уровень
          <select v-model="selectedLevel" @change="loadWords">
            <option v-for="level in levels" :key="level" :value="level">{{ level || "Все" }}</option>
          </select>
        </label>
        <label>Тема
          <select v-model="selectedTheme" @change="loadWords">
            <option value="">Все</option>
            <option v-for="theme in themes" :key="theme" :value="theme">{{ theme }}</option>
          </select>
        </label>
        <label>Пароль редактора
          <input v-model="editorPassword" type="password" autocomplete="current-password" />
        </label>
        <RouterLink class="button-link" to="/editor">Добавить</RouterLink>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-else-if="words.length === 0" class="muted">Пока нет слов. Добавьте первое слово в редакторе.</p>
      <ul v-else class="word-list">
        <li v-for="word in words" :key="word.id" class="word-row">
          <div>
            <strong>{{ word.serbian_cyrillic }}</strong>
            <span>{{ word.serbian_latin }}</span>
          </div>
          <span>{{ word.russian_translation }}</span>
          <span>{{ word.cefr_level }} · {{ word.theme }}</span>
          <RouterLink v-if="canEdit" :to="`/editor/${word.id}`">Изменить</RouterLink>
        </li>
      </ul>
    </section>
  </main>
</template>
