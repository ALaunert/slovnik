<script setup lang="ts">
import { reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { createVocabularyWord, type VocabularyPayload } from "../api/client";

const editorPassword = ref("");
const status = ref("");
const error = ref("");
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

async function saveWord() {
  status.value = "";
  error.value = "";
  if (!editorPassword.value || !form.serbian_cyrillic || !form.serbian_latin || !form.russian_translation || !form.theme) {
    error.value = "Заполните обязательные поля и пароль";
    return;
  }
  try {
    await createVocabularyWord(form, editorPassword.value);
    status.value = "Слово сохранено";
  } catch {
    error.value = "Не удалось сохранить слово";
  }
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>Редактор</h1>
      <RouterLink to="/vocabulary">Словарь</RouterLink>
    </header>
    <form class="panel form-grid" @submit.prevent="saveWord">
      <label>Пароль редактора<input v-model="editorPassword" type="password" /></label>
      <label>Сербский кириллица<input v-model="form.serbian_cyrillic" required /></label>
      <label>Сербский латиница<input v-model="form.serbian_latin" required /></label>
      <label>Русский перевод<input v-model="form.russian_translation" required /></label>
      <label>Уровень<select v-model="form.cefr_level"><option>A1</option><option>A2</option><option>B1</option><option>B2</option><option>C1</option><option>C2</option></select></label>
      <label>Тема<input v-model="form.theme" required /></label>
      <label>Регистр<input v-model="form.usage_register" /></label>
      <label>Ударение<input v-model="form.stress_marker" /></label>
      <label class="wide">Заметки<textarea v-model="form.meaning_notes" rows="3" /></label>
      <label class="wide">Примеры<textarea v-model="form.example_sentences" rows="3" /></label>
      <label class="wide">Переводы примеров<textarea v-model="form.example_translations" rows="3" /></label>
      <button type="submit">Сохранить</button>
      <p v-if="status" class="success">{{ status }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </form>
  </main>
</template>
