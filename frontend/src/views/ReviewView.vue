<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import {
  getReviewStatus,
  getReviewWords,
  submitReviewAnswer,
  type ReviewRating,
  type VocabularyWord,
} from "../api/client";
import EmptyState from "../components/EmptyState.vue";
import { messages } from "../i18n/messages";
import SessionProgress from "../components/SessionProgress.vue";
import WordCard from "../components/WordCard.vue";
import { sessionStore } from "../stores/session";

const router = useRouter();
const words = ref<VocabularyWord[]>([]);
const index = ref(0);
const error = ref("");
const isDone = ref(false);
const loading = ref(true);
const revealed = ref(false);
const saving = ref(false);
const revealButton = ref<HTMLButtonElement | null>(null);
const answerRegion = ref<HTMLElement | null>(null);
const completionStatus = ref<HTMLElement | null>(null);
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const currentWord = computed(() => words.value[index.value]);
const ratings = computed<{ rating: ReviewRating; label: string }[]>(() => [
  { rating: "again", label: copy.value.reviewAgain },
  { rating: "hard", label: copy.value.reviewHard },
  { rating: "good", label: copy.value.reviewGood },
  { rating: "easy", label: copy.value.reviewEasy },
]);

onMounted(async () => {
  if (!sessionStore.userId.value) {
    loading.value = false;
    await router.push("/");
    return;
  }
  try {
    words.value = (await getReviewWords(sessionStore.userId.value)).words;
  } catch {
    error.value = copy.value.loadReviewError;
  } finally {
    loading.value = false;
  }
});

async function reveal() {
  if (saving.value) return;
  error.value = "";
  revealed.value = true;
  await nextTick();
  answerRegion.value?.focus();
}

async function advance() {
  error.value = "";
  revealed.value = false;
  if (index.value >= words.value.length - 1) {
    isDone.value = true;
    await nextTick();
    completionStatus.value?.focus();
    return;
  }
  index.value += 1;
  await nextTick();
  revealButton.value?.focus();
}

async function rate(rating: ReviewRating) {
  if (saving.value || !revealed.value || !currentWord.value) return;

  const wordId = currentWord.value.id;
  let shouldAdvance = false;
  saving.value = true;
  error.value = "";

  try {
    await submitReviewAnswer(sessionStore.userId.value, { word_id: wordId, rating });
    shouldAdvance = true;
  } catch {
    try {
      const status = await getReviewStatus(sessionStore.userId.value, wordId);
      shouldAdvance = !status.is_due;
      if (!shouldAdvance) error.value = copy.value.saveReviewError;
    } catch {
      error.value = copy.value.saveReviewError;
    }
  } finally {
    saving.value = false;
  }

  if (shouldAdvance) await advance();
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>{{ copy.review }}</h1>
      <RouterLink to="/dashboard">{{ copy.backToDashboard }}</RouterLink>
    </header>
    <section class="panel stack">
      <p v-if="loading" class="recall-loading muted" role="status" aria-live="polite">
        {{ copy.loading }}
      </p>
      <p v-else-if="error && words.length === 0" class="error">{{ error }}</p>
      <p
        v-else-if="isDone"
        ref="completionStatus"
        class="success"
        role="status"
        aria-live="polite"
        tabindex="-1"
      >
        {{ copy.reviewDone }}
      </p>
      <EmptyState v-else-if="words.length === 0" :title="copy.emptyReview" />
      <template v-else>
        <SessionProgress :current="index" :total="words.length" />
        <article v-if="!revealed" class="recall-cue" aria-labelledby="recall-cue-title">
          <p class="eyebrow">{{ currentWord.cefr_level }} · {{ currentWord.theme }}</p>
          <p class="recall-instruction">{{ copy.recallInstruction }}</p>
          <h2 id="recall-cue-title">{{ currentWord.russian_translation }}</h2>
          <button ref="revealButton" class="recall-reveal" type="button" :disabled="saving" @click="reveal">
            {{ copy.showReviewAnswer }}
          </button>
        </article>
        <template v-else>
          <section
            ref="answerRegion"
            class="recall-answer"
            role="region"
            :aria-label="copy.answerLabel"
            tabindex="-1"
          >
            <WordCard :word="currentWord" :weak="Boolean(currentWord.is_weak)" />
            <p v-if="currentWord.incorrect_count && currentWord.incorrect_count > 0" class="muted">
              {{ copy.weakHistory }}: {{ currentWord.incorrect_count }}
            </p>
          </section>
          <div
            class="recall-rating-area"
            role="group"
            aria-labelledby="recall-rating-guidance"
            :aria-busy="saving"
            tabindex="-1"
          >
            <p id="recall-rating-guidance" class="muted">{{ copy.ratingGuidance }}</p>
            <div class="recall-ratings">
              <button
                v-for="option in ratings"
                :key="option.rating"
                type="button"
                :disabled="saving"
                @click="rate(option.rating)"
              >
                {{ option.label }}
              </button>
            </div>
            <p class="recall-saving muted" role="status" aria-live="polite">
              {{ saving ? copy.savingReview : "" }}
            </p>
            <p v-if="error" class="error" role="alert">{{ error }}</p>
          </div>
        </template>
      </template>
    </section>
  </main>
</template>
