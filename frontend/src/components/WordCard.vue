<script setup lang="ts">
import { computed } from "vue";

import type { VocabularyWord } from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

type ExampleLine = { sentence: string; translation?: string };

const props = defineProps<{ word: VocabularyWord; weak?: boolean }>();
const copy = computed(() => messages[sessionStore.uiLanguage.value]);

function lines(value?: string | null) {
  return value ? value.split("\n").filter(Boolean) : [];
}

function examples(word: VocabularyWord): ExampleLine[] {
  const source = lines(word.example_sentences);
  const translations = lines(word.example_translations);
  return source.map((sentence, index) => ({ sentence, translation: translations[index] }));
}

function hasDetails(word: VocabularyWord) {
  return Boolean(word.meaning_notes || examples(word).length > 0);
}

function meta(word: VocabularyWord) {
  const register = word.usage_register ? ` · ${word.usage_register}` : "";
  const stress = word.stress_marker ? ` · ${word.stress_marker}` : "";
  return `${word.cefr_level} · ${word.theme}${register}${stress}`;
}
</script>

<template>
  <article class="word-card">
    <p class="eyebrow">{{ meta(props.word) }} <span v-if="props.weak" class="badge">{{ copy.weak }}</span></p>
    <h2>{{ props.word.serbian_cyrillic }} / {{ props.word.serbian_latin }}</h2>
    <p class="translation">{{ props.word.russian_translation }}</p>
    <details v-if="hasDetails(props.word)">
      <summary>{{ copy.details }}</summary>
      <p v-if="props.word.meaning_notes">{{ props.word.meaning_notes }}</p>
      <ul v-if="examples(props.word).length > 0">
        <li v-for="(item, index) in examples(props.word)" :key="`${item.sentence}-${index}`">
          {{ item.sentence }}<br />
          <span>{{ item.translation }}</span>
        </li>
      </ul>
    </details>
  </article>
</template>
