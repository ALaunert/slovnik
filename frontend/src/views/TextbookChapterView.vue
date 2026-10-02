<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { textbook } from "../content/textbook";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const route = useRoute();
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const chapter = computed(() => textbook.chapters.find((item) => item.id === route.params.chapterId));
const group = computed(() => textbook.groups.find((item) => item.id === chapter.value?.group_id));
const index = computed(() => textbook.chapters.findIndex((item) => item.id === chapter.value?.id));
const previous = computed(() => textbook.chapters[index.value - 1]);
const next = computed(() => textbook.chapters[index.value + 1]);
const related = computed(() => textbook.chapters.filter((item) => chapter.value?.related.includes(item.id)));
const sources = computed(() => (chapter.value?.source_refs ?? []).flatMap((ref) => {
  const source = textbook.sources.find((item) => item.id === ref.source_id);
  return source ? [{ ...source, locator: ref.locator }] : [];
}));
</script>

<template>
  <main class="page lesson-page">
    <RouterLink class="book-back" to="/textbook">← {{ copy.textbookBack }}</RouterLink>
    <section v-if="!chapter" class="empty-state">
      <h1>{{ copy.textbookMissing }}</h1>
      <p>{{ copy.textbookMissingHint }}</p>
    </section>
    <article v-else :key="chapter.id" lang="ru">
      <header class="lesson-header">
        <p class="eyebrow">{{ group?.title }}</p>
        <h1>{{ chapter.title }}</h1>
        <p>{{ chapter.summary }}</p>
      </header>
      <section class="panel lesson-objectives">
        <h2>{{ copy.textbookObjectives }}</h2>
        <ul><li v-for="objective in chapter.objectives" :key="objective">{{ objective }}</li></ul>
      </section>
      <nav class="panel lesson-contents" :aria-label="copy.textbookContents">
        <h2>{{ copy.textbookContents }}</h2>
        <ul>
          <li v-for="(section, sectionIndex) in chapter.sections" :key="sectionIndex"><RouterLink :to="{ hash: `#section-${sectionIndex + 1}` }">{{ section.title }}</RouterLink></li>
          <li><RouterLink to="#examples">{{ copy.textbookExamples }}</RouterLink></li>
          <li><RouterLink to="#self-check">{{ copy.textbookSelfCheck }}</RouterLink></li>
          <li><RouterLink to="#sources">{{ copy.textbookSources }}</RouterLink></li>
        </ul>
      </nav>
      <section v-for="(section, sectionIndex) in chapter.sections" :id="`section-${sectionIndex + 1}`" :key="section.title" class="lesson-section">
        <h2>{{ section.title }}</h2>
        <p v-for="paragraph in section.paragraphs" :key="paragraph">{{ paragraph }}</p>
        <div v-if="section.table" class="table-scroll" role="region" :aria-label="section.title" tabindex="0">
          <table>
            <caption>{{ section.title }}</caption>
            <thead><tr><th v-for="heading in section.table.headers" :key="heading" scope="col">{{ heading }}</th></tr></thead>
            <tbody><tr v-for="(row, rowIndex) in section.table.rows" :key="rowIndex"><td v-for="(cell, column) in row" :key="column">{{ cell }}</td></tr></tbody>
          </table>
        </div>
      </section>
      <section id="examples" class="lesson-section">
        <h2>{{ copy.textbookExamples }}</h2>
        <div v-for="example in chapter.examples" :key="example.serbian" class="lesson-example panel">
          <p lang="sr" class="serbian-example">{{ example.serbian }}</p>
          <p>{{ example.translation }}</p>
          <p class="muted">{{ example.note }}</p>
        </div>
      </section>
      <aside class="panel lesson-pitfalls">
        <h2>{{ copy.textbookPitfalls }}</h2>
        <ul><li v-for="pitfall in chapter.pitfalls" :key="pitfall">{{ pitfall }}</li></ul>
      </aside>
      <section id="self-check" class="lesson-section">
        <h2>{{ copy.textbookSelfCheck }}</h2>
        <p>{{ copy.textbookSelfCheckHint }}</p>
        <div v-for="(exercise, exerciseIndex) in chapter.practice" :key="exerciseIndex" class="lesson-exercise panel">
          <p>{{ exercise.prompt }}</p>
          <details>
            <summary>{{ copy.textbookShowAnswer }}</summary>
            <p :lang="exercise.answer_language ?? 'sr'" class="serbian-example">{{ exercise.answer }}</p>
            <p>{{ exercise.explanation }}</p>
          </details>
        </div>
      </section>
      <section v-if="related.length" class="lesson-section">
        <h2>{{ copy.textbookRelated }}</h2>
        <ul><li v-for="topic in related" :key="topic.id"><RouterLink :to="`/textbook/${topic.id}`">{{ topic.title }}</RouterLink></li></ul>
      </section>
      <section id="sources" class="lesson-sources lesson-section">
        <h2>{{ copy.textbookSources }}</h2>
        <ul><li v-for="source in sources" :key="source.id + source.locator"><a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.title }}</a> — {{ source.locator }}</li></ul>
        <p class="muted">{{ copy.textbookSourceNote }}</p>
      </section>
      <nav class="lesson-navigation" :aria-label="copy.textbookTopicNavigation">
        <RouterLink v-if="previous" :to="`/textbook/${previous.id}`">← {{ previous.title }}</RouterLink>
        <RouterLink v-if="next" :to="`/textbook/${next.id}`">{{ next.title }} →</RouterLink>
      </nav>
    </article>
  </main>
</template>

<style scoped>
.lesson-page { max-width: 860px; }
.book-back { display: inline-block; margin: 0 0 24px; }
.lesson-header h1 { margin: 4px 0 12px; }
.lesson-header p, .lesson-section p, li { line-height: 1.7; }
.lesson-objectives { margin: 24px 0 32px; }
.lesson-section { margin: 32px 0; scroll-margin-top: 150px; }
.lesson-contents { margin: 24px 0; }
.lesson-contents h2 { margin-top: 0; font-size: 1.1rem; }
.lesson-contents ul { margin-bottom: 0; }
.lesson-section h2 { font-size: 1.35rem; }
.table-scroll { max-width: 100%; overflow-x: auto; border: 1px solid #d8dfdc; border-radius: 8px; }
table { width: 100%; border-collapse: collapse; background: white; }
caption { text-align: left; padding: 12px; font-weight: 600; background: #eaf1ee; }
th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid #d8dfdc; vertical-align: top; min-width: 105px; }
th { background: #f3f7f5; }
tbody tr:last-child td { border-bottom: 0; }
.lesson-example, .lesson-exercise { margin: 14px 0; }
.lesson-example p, .lesson-exercise p { margin: 8px 0; }
.serbian-example { font-size: 1.2rem; font-weight: 600; color: #173b42; }
details summary { cursor: pointer; color: #0f5c6d; font-weight: 600; min-height: 40px; padding: 8px 0; }
details[open] { margin-top: 12px; border-top: 1px solid #d8dfdc; }
.lesson-navigation { display: flex; justify-content: space-between; gap: 24px; border-top: 1px solid #d8dfdc; padding: 24px 0; }
article, .lesson-navigation a { min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 760px) { .lesson-navigation { flex-direction: column; } th, td { padding: 8px 10px; } }
</style>
