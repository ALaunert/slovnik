<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";

import type { QuizCompletion } from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const emptyResults = { score: 0, total_questions: 0, weak_word_ids: [], mistakes: [] };
const results = computed<QuizCompletion & { quizType?: string }>(() => {
  const raw = sessionStorage.getItem("slovnik.quizResults");
  if (!raw) return emptyResults;
  try {
    return JSON.parse(raw);
  } catch {
    return emptyResults;
  }
});
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const hasBreakdown = computed(() =>
  results.value.result_version === 2 &&
  (results.value.first_attempt_status === "available" || results.value.first_attempt_status === "not_measured") &&
  typeof results.value.first_attempt_correct === "number" &&
  typeof results.value.first_attempt_eligible === "number" &&
  typeof results.value.recovered_objective_items === "number" &&
  typeof results.value.self_report_remembered === "number" &&
  typeof results.value.self_report_total === "number",
);
const title = computed(() => (results.value.quizType === "weekly" ? copy.value.weeklyResults : copy.value.results));

function questionTypeLabel(questionType: string) {
  if (questionType === "sr_to_ru_choice") return copy.value.srToRuChoice;
  if (questionType === "ru_to_sr_typing") return copy.value.ruToSrTyping;
  return copy.value.selfCheck;
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>{{ title }}</h1>
      <RouterLink to="/dashboard">{{ copy.backToDashboard }}</RouterLink>
    </header>
    <section class="panel result-grid">
      <div><strong>{{ results.score }}</strong><span>{{ copy.practiceScore }}</span></div>
      <div><strong>{{ results.total_questions }}</strong><span>{{ copy.questionCount }}</span></div>
      <div><strong>{{ results.weak_word_ids.length }}</strong><span>{{ copy.weakWordCount }}</span></div>
    </section>
    <p class="muted">{{ copy.practiceScoreNote }}</p>
    <section class="panel stack" aria-label="evidence-breakdown">
      <h2>{{ copy.resultBreakdown }}</h2>
      <p v-if="!hasBreakdown">{{ copy.breakdownUnavailable }}</p>
      <template v-else>
        <p>
          {{ copy.firstUnaided }}:
          <span v-if="results.first_attempt_status === 'not_measured'">{{ copy.notMeasured }}</span>
          <span v-else>{{ results.first_attempt_correct }} / {{ results.first_attempt_eligible }}</span>
        </p>
        <p>{{ copy.recoveredAfterError }}: {{ results.recovered_objective_items }}</p>
        <p>{{ copy.selfRatedRemembered }}: {{ results.self_report_remembered }} / {{ results.self_report_total }}</p>
      </template>
    </section>
    <section v-if="results.mistakes.length > 0" class="panel stack">
      <h2>{{ copy.mistakes }}</h2>
      <ul class="word-list">
        <li v-for="mistake in results.mistakes" :key="`${mistake.word_id}-${mistake.question_type}-${mistake.answer}`" class="word-row">
          <strong>{{ mistake.prompt }}</strong>
          <span>{{ copy.mistakeAnswer }}: {{ mistake.answer }}</span>
          <span>{{ copy.correctAnswer }}: {{ mistake.correct_answer }}</span>
          <span>{{ copy.mistakeType }}: {{ questionTypeLabel(String(mistake.question_type ?? "")) }}</span>
        </li>
      </ul>
    </section>
  </main>
</template>
