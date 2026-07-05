<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";

import {
  completeQuiz,
  revealQuizAnswer,
  startQuiz,
  submitQuizAnswer,
  type QuizCompletion,
  type QuizQuestion,
} from "../api/client";
import EmptyState from "../components/EmptyState.vue";
import FeedbackPanel from "../components/FeedbackPanel.vue";
import { messages } from "../i18n/messages";
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
const repeatedQuestionKeys = ref(new Set<string>());
const isSelfCheckRevealed = ref(false);
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const quizType = computed(() => (route.query.type === "weekly" ? "weekly" : "daily"));
const currentQuestion = computed(() => questions.value[index.value]);
const quizTitle = computed(() => (quizType.value === "weekly" ? copy.value.weeklyQuiz : copy.value.dailyQuiz));

function questionKey(question: QuizQuestion) {
  return `${question.word_id}:${question.question_type}`;
}

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
    error.value = copy.value.startQuizError;
  }
});

async function submit(value?: string) {
  if (!currentQuestion.value) return;
  error.value = "";
  const question = currentQuestion.value;
  try {
    const response = await submitQuizAnswer(sessionStore.userId.value, attemptId.value, {
      word_id: question.word_id,
      question_type: question.question_type,
      answer: value ?? answer.value,
    });
    feedback.value = { correct: response.is_correct, repeat: response.repeat_word };
    const key = questionKey(question);
    if (response.repeat_word && !repeatedQuestionKeys.value.has(key)) {
      repeatedQuestionKeys.value.add(key);
      questions.value.push(question);
    }
  } catch {
    error.value = copy.value.quizActionError;
  }
}

async function revealSelfCheckAnswer() {
  if (!currentQuestion.value) return;
  error.value = "";
  const question = currentQuestion.value;
  try {
    const result = await revealQuizAnswer(
      sessionStore.userId.value,
      attemptId.value,
      question.word_id,
      question.question_type,
    );
    questions.value[index.value] = { ...question, answer: result.answer };
    isSelfCheckRevealed.value = true;
  } catch {
    error.value = copy.value.quizActionError;
  }
}

async function next() {
  error.value = "";
  if (index.value < questions.value.length - 1) {
    feedback.value = null;
    answer.value = "";
    isSelfCheckRevealed.value = false;
    index.value += 1;
    return;
  }
  try {
    const completion: QuizCompletion = await completeQuiz(sessionStore.userId.value, attemptId.value);
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({ ...completion, quizType: quizType.value }));
    await router.push("/results");
  } catch {
    error.value = copy.value.quizActionError;
  }
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>{{ quizTitle }}</h1>
      <RouterLink to="/dashboard">{{ copy.backToDashboard }}</RouterLink>
    </header>
    <section class="panel stack">
      <p v-if="error" class="error">{{ error }}</p>
      <EmptyState v-if="questions.length === 0" :title="copy.noQuizWords" />
      <template v-else>
        <SessionProgress :current="index" :total="questions.length" />
        <h2>{{ currentQuestion.prompt }}</h2>
        <div v-if="currentQuestion.question_type === 'sr_to_ru_choice'" class="choice-grid">
          <button v-for="choice in currentQuestion.choices" :key="choice" type="button" :disabled="Boolean(feedback)" @click="submit(choice)">{{ choice }}</button>
        </div>
        <form v-else-if="currentQuestion.question_type === 'ru_to_sr_typing'" class="control-row" @submit.prevent="submit()">
          <input v-model="answer" :aria-label="copy.answerLabel" :disabled="Boolean(feedback)" />
          <button type="submit" :disabled="Boolean(feedback)">{{ copy.check }}</button>
        </form>
        <div v-else class="stack">
          <button v-if="!isSelfCheckRevealed" type="button" @click="revealSelfCheckAnswer">{{ copy.showTranslation }}</button>
          <template v-else>
            <p v-if="currentQuestion.answer" class="translation">{{ currentQuestion.answer }}</p>
            <div class="control-row">
              <button type="button" :disabled="Boolean(feedback)" @click="submit('remembered')">{{ copy.remembered }}</button>
              <button type="button" :disabled="Boolean(feedback)" @click="submit('forgot')">{{ copy.forgot }}</button>
            </div>
          </template>
        </div>
        <FeedbackPanel v-if="feedback" :correct="feedback.correct" :repeat="feedback.repeat" />
        <button v-if="feedback" type="button" @click="next">{{ copy.next }}</button>
      </template>
    </section>
  </main>
</template>
