<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import { completeNewWords, getNewWords, type VocabularyWord } from "../api/client";
import SessionProgress from "../components/SessionProgress.vue";
import WordCard from "../components/WordCard.vue";
import { sessionStore } from "../stores/session";

const router = useRouter();
const words = ref<VocabularyWord[]>([]);
const index = ref(0);
const error = ref("");
const isDone = ref(false);
const currentWord = computed(() => words.value[index.value]);

onMounted(async () => {
  if (!sessionStore.userId.value) {
    await router.push("/");
    return;
  }
  try {
    words.value = (await getNewWords(sessionStore.userId.value)).words;
  } catch {
    error.value = "Не удалось загрузить новые слова";
  }
});

function previous() {
  index.value = Math.max(0, index.value - 1);
}

function next() {
  index.value = Math.min(words.value.length - 1, index.value + 1);
}

async function complete() {
  await completeNewWords(sessionStore.userId.value, words.value.map((word) => word.id));
  isDone.value = true;
}
</script>

<template>
  <main class="page">
    <header class="page-header">
      <h1>Новые слова</h1>
      <RouterLink to="/dashboard">Сегодня</RouterLink>
    </header>
    <section class="panel stack">
      <p v-if="error" class="error">{{ error }}</p>
      <p v-else-if="isDone" class="success">Сессия завершена</p>
      <p v-else-if="words.length === 0" class="muted">На сегодня новых слов нет.</p>
      <template v-else>
        <SessionProgress :current="index" :total="words.length" />
        <WordCard :word="currentWord" />
        <div class="control-row">
          <button type="button" :disabled="index === 0" @click="previous">Назад</button>
          <button v-if="index < words.length - 1" type="button" @click="next">Дальше</button>
          <button v-else type="button" @click="complete">Завершить</button>
        </div>
      </template>
    </section>
  </main>
</template>
