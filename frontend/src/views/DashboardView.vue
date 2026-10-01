<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";

import { createOrLoadProfile, getPracticeAvailability, updateProfile, type Profile } from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const levels = ["A1", "A2", "B1", "B2", "C1", "C2"];
const languages = [
  { value: "ru", label: "Русский" },
  { value: "sr", label: "Srpski" },
];
const settings = reactive({ preferred_level: "A1", daily_new_word_count: 5, ui_language: "ru", timezone: "UTC" });
const effectiveTimezone = ref("UTC");
const zoneChangeAt = ref<string | null>(null);
const timezoneChoices = ["UTC", "Europe/Belgrade", "Europe/Moscow", "Asia/Tbilisi", "Asia/Almaty", "America/New_York"];
const status = ref("");
const error = ref("");
const userId = sessionStore.userId;
const practiceAvailable = ref(false);
const copy = computed(() => messages[sessionStore.uiLanguage.value]);

function applyProfile(profile: Profile) {
  settings.preferred_level = profile.preferred_level;
  settings.daily_new_word_count = profile.daily_new_word_count;
  settings.ui_language = profile.ui_language;
  settings.timezone = profile.timezone ?? "UTC";
  effectiveTimezone.value = profile.effective_timezone ?? "UTC";
  zoneChangeAt.value = profile.allocation_window?.transition ? profile.allocation_window.end : null;
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

onMounted(async () => {
  try { practiceAvailable.value = await getPracticeAvailability(); }
  catch { practiceAvailable.value = false; }
});

async function saveSettings() {
  if (!userId.value) return;
  error.value = "";
  status.value = "";
  const payload = {
    preferred_level: settings.preferred_level,
    daily_new_word_count: Math.min(50, Math.max(1, Number(settings.daily_new_word_count))),
    ui_language: settings.ui_language,
    timezone: settings.timezone,
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
        <p class="eyebrow">{{ userId || copy.learnerFallback }}</p>
        <h1>{{ copy.dashboard }}</h1>
      </div>
      <RouterLink to="/">{{ copy.changeId }}</RouterLink>
    </header>

    <nav class="action-grid" :aria-label="copy.mainActions">
      <RouterLink class="action-card" to="/textbook">{{ copy.textbook }}</RouterLink>
      <RouterLink class="action-card" to="/new-words">{{ copy.newWords }}</RouterLink>
      <RouterLink class="action-card" to="/review">{{ copy.review }}</RouterLink>
      <RouterLink class="action-card" to="/quiz?type=daily">{{ copy.dailyQuiz }}</RouterLink>
      <RouterLink class="action-card" to="/quiz?type=weekly">{{ copy.weeklyQuiz }}</RouterLink>
      <RouterLink class="action-card" to="/vocabulary">{{ copy.vocabulary }}</RouterLink>
      <RouterLink v-if="practiceAvailable" class="action-card" to="/practice">{{ copy.practiceTitle }}</RouterLink>
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
        <label>
          {{ copy.timezoneLabel }}
          <input v-model="settings.timezone" name="timezone" list="timezone-choices" required maxlength="80" />
          <datalist id="timezone-choices">
            <option v-for="zone in timezoneChoices" :key="zone" :value="zone" />
          </datalist>
        </label>
        <button type="submit">{{ copy.save }}</button>
      </form>
      <p>{{ copy.timezoneEffective }} {{ effectiveTimezone }}</p>
      <p>{{ copy.timezonePolicy }}</p>
      <p v-if="zoneChangeAt">{{ copy.timezonePending }} {{ zoneChangeAt }}</p>
      <p v-if="status" class="success">{{ status }}</p>
      <p v-if="error" class="error">{{ error }}</p>
    </section>
  </main>
</template>
