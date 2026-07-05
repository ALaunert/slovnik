<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";

import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const raw = sessionStorage.getItem("slovnik.quizResults");
const results = computed(() => raw ? JSON.parse(raw) : { score: 0, total_questions: 0, weak_word_ids: [], mistakes: [] });
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const title = computed(() => (results.value.quizType === "weekly" ? copy.value.weeklyResults : copy.value.results));
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>{{ title }}</h1>
      <RouterLink to="/dashboard">{{ copy.backToDashboard }}</RouterLink>
    </header>
    <section class="panel result-grid">
      <div><strong>{{ results.score }}</strong><span>{{ copy.correctCount }}</span></div>
      <div><strong>{{ results.total_questions }}</strong><span>{{ copy.questionCount }}</span></div>
      <div><strong>{{ results.weak_word_ids.length }}</strong><span>{{ copy.weakWordCount }}</span></div>
    </section>
  </main>
</template>
