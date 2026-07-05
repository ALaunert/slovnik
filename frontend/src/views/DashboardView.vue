<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { createOrLoadProfile, updateProfile, type Profile } from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const levels = ["A1", "A2", "B1", "B2", "C1", "C2"];
const languages = [
  { value: "ru", label: "Русский" },
  { value: "sr", label: "Srpski" },
];
const settings = reactive({ preferred_level: "A1", daily_new_word_count: 5, ui_language: "ru" });
const status = ref("");
const error = ref("");
const userId = sessionStore.userId;
const copy = computed(() => messages[sessionStore.uiLanguage.value]);

function applyProfile(profile: Profile) {
  settings.preferred_level = profile.preferred_level;
  settings.daily_new_word_count = profile.daily_new_word_count;
  settings.ui_language = profile.ui_language;
  sessionStore.setUiLanguage(profile.ui_language);
}

onMounted(async () => {
  if (!userId.value) return;
  try {
    applyProfile(await createOrLoadProfile(userId.value));
  } catch {
    error.value = copy.value.loadSettingsError;
  }
});

async function saveSettings() {
  if (!userId.value) return;
  error.value = "";
  status.value = "";
  const payload = {
    preferred_level: settings.preferred_level,
    daily_new_word_count: Math.min(50, Math.max(1, Number(settings.daily_new_word_count))),
    ui_language: settings.ui_language,
  };
  try {
    applyProfile(await updateProfile(userId.value, payload));
    status.value = copy.value.saved;
  } catch {
    error.value = copy.value.saveSettingsError;
  }
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ userId || "learner" }}</p>
        <h1>{{ copy.dashboard }}</h1>
      </div>
      <RouterLink to="/">{{ copy.changeId }}</RouterLink>
    </header>

    <nav class="action-grid" :aria-label="copy.mainActions">
      <RouterLink class="action-card" to="/new-words">{{ copy.newWords }}</RouterLink>
      <RouterLink class="action-card" to="/review">{{ copy.review }}</RouterLink>
      <RouterLink class="action-card" to="/quiz?type=daily">{{ copy.dailyQuiz }}</RouterLink>
      <RouterLink class="action-card" to="/quiz?type=weekly">{{ copy.weeklyQuiz }}</RouterLink>
      <RouterLink class="action-card" to="/vocabulary">{{ copy.vocabulary }}</RouterLink>
    </nav>

    <section class="panel">
      <h2>{{ copy.settings }}</h2>
      <form class="settings-grid" @submit.prevent="saveSettings">
        <label>
          {{ copy.level }}
          <select v-model="settings.preferred_level" name="preferred_level">
            <option v-for="level in levels" :key="level" :value="level">{{ level }}</option>
          </select>
        </label>
        <label>
          {{ copy.dailyNewWordCount }}
          <input
            v-model.number="settings.daily_new_word_count"
            name="daily_new_word_count"
            type="number"
            min="1"
            max="50"
          />
        </label>
        <label>
          {{ copy.uiLanguage }}
          <select v-model="settings.ui_language" name="ui_language">
            <option v-for="language in languages" :key="language.value" :value="language.value">
              {{ language.label }}
            </option>
          </select>
        </label>
        <button type="submit">{{ copy.save }}</button>
      </form>
      <p v-if="status" class="success">{{ status }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </main>
</template>
