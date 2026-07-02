<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import { completeQuiz, startQuiz, submitQuizAnswer, type QuizCompletion, type QuizQuestion } from "../api/client";
import EmptyState from "../components/EmptyState.vue";
import FeedbackPanel from "../components/FeedbackPanel.vue";
import SessionProgress from "../components/SessionProgress.vue";
import { sessionStore } from "../stores/session";

const route = useRoute();
const router = useRouter();
const attemptId = ref(0);
const questions = ref<QuizQuestion[]>([]);
const index = ref(0);
const answer = ref("");
const feedback = ref<{ correct: boolean; repeat: boolean } | null>(null);
const error = ref("");
const quizType = computed(() => (route.query.type === "weekly" ? "weekly" : "daily"));
const currentQuestion = computed(() => questions.value[index.value]);

onMounted(async () => {
  if (!sessionStore.userId.value) {
    await router.push("/");
    return;
  }
  try {
    const result = await startQuiz(sessionStore.userId.value, quizType.value);
    attemptId.value = result.attempt_id;
    questions.value = result.questions;
  } catch {
    error.value = "Не удалось начать тест";
  }
});

async function submit(value?: string) {
  if (!currentQuestion.value) return;
  const response = await submitQuizAnswer(attemptId.value, {
    word_id: currentQuestion.value.word_id,
    question_type: currentQuestion.value.question_type,
    answer: value ?? answer.value,
  });
  feedback.value = { correct: response.is_correct, repeat: response.repeat_word };
  if (response.repeat_word) questions.value.push(currentQuestion.value);
}

async function next() {
  feedback.value = null;
  answer.value = "";
  if (index.value < questions.value.length - 1) {
    index.value += 1;
    return;
  }
  const completion: QuizCompletion = await completeQuiz(attemptId.value);
  sessionStorage.setItem("slovnik.quizResults", JSON.stringify({ ...completion, quizType: quizType.value }));
  await router.push("/results");
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>{{ quizType === "weekly" ? "Недельный тест" : "Ежедневный тест" }}</h1>
      <RouterLink to="/dashboard">Сегодня</RouterLink>
    </header>
    <section class="panel stack">
      <p v-if="error" class="error">{{ error }}</p>
      <EmptyState v-else-if="questions.length === 0" title="Пока нет слов для теста." />
      <template v-else>
        <SessionProgress :current="index" :total="questions.length" />
        <h2>{{ currentQuestion.prompt }}</h2>
        <div v-if="currentQuestion.question_type === 'sr_to_ru_choice'" class="choice-grid">
          <button v-for="choice in currentQuestion.choices" :key="choice" type="button" :disabled="Boolean(feedback)" @click="submit(choice)">{{ choice }}</button>
        </div>
        <form v-else-if="currentQuestion.question_type === 'ru_to_sr_typing'" class="control-row" @submit.prevent="submit()">
          <input v-model="answer" aria-label="Ответ" :disabled="Boolean(feedback)" />
          <button type="submit" :disabled="Boolean(feedback)">Проверить</button>
        </form>
        <div v-else class="stack">
          <p v-if="currentQuestion.answer" class="translation">{{ currentQuestion.answer }}</p>
          <div class="control-row">
            <button type="button" :disabled="Boolean(feedback)" @click="submit('remembered')">Помню</button>
            <button type="button" :disabled="Boolean(feedback)" @click="submit('forgot')">Забыл</button>
          </div>
        </div>
        <FeedbackPanel v-if="feedback" :correct="feedback.correct" :repeat="feedback.repeat" />
        <button v-if="feedback" type="button" @click="next">Дальше</button>
      </template>
    </section>
  </main>
</template>
