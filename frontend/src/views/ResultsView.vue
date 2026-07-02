<script setup lang="ts">
import { computed } from "vue";
import { RouterLink } from "vue-router";

const raw = sessionStorage.getItem("slovnik.quizResults");
const results = computed(() => raw ? JSON.parse(raw) : { score: 0, total_questions: 0, weak_word_ids: [], mistakes: [] });
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>Результаты</h1>
      <RouterLink to="/dashboard">Сегодня</RouterLink>
    </header>
    <section class="panel result-grid">
      <div><strong>{{ results.score }}</strong><span>Верно</span></div>
      <div><strong>{{ results.total_questions }}</strong><span>Вопросов</span></div>
      <div><strong>{{ results.weak_word_ids.length }}</strong><span>Слабых слов</span></div>
    </section>
  </main>
</template>
