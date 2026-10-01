<script setup lang="ts">
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { matchesChapter, textbook } from "../content/textbook";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const query = ref("");
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const groups = computed(() => textbook.groups.map((group) => ({ ...group,
  chapters: textbook.chapters.filter((chapter) => chapter.group_id === group.id && matchesChapter(chapter, query.value)),
})).filter((group) => group.chapters.length));
const count = computed(() => groups.value.reduce((total, group) => total + group.chapters.length, 0));
</script>

<template>
  <main class="page textbook-page">
    <header class="page-header">
      <div>
        <p class="eyebrow">{{ copy.textbook }}</p>
        <h1>{{ copy.textbookTitle }}</h1>
      </div>
      <RouterLink to="/practice">{{ copy.practiceTitle }}</RouterLink>
    </header>
    <p class="book-description" lang="ru">{{ textbook.description }}</p>
    <p>{{ copy.textbookReadingHint }}</p>
    <div class="book-search panel">
      <label for="topic-search">{{ copy.textbookSearch }}</label>
      <input id="topic-search" v-model="query" type="search" :placeholder="copy.textbookSearchHint" />
      <button v-if="query" class="secondary-button" data-test="clear-search" type="button" @click="query = ''">{{ copy.textbookClear }}</button>
      <p role="status" aria-live="polite">{{ copy.textbookTopicCount }} {{ count }} / {{ textbook.chapters.length }}</p>
    </div>
    <section v-if="!count" class="empty-state" role="status">
      <h2>{{ copy.textbookNoResults }}</h2>
      <p>{{ copy.textbookTrySearch }}</p>
    </section>
    <section v-for="group in groups" :key="group.id" class="book-group" lang="ru">
      <h2>{{ group.title }}</h2>
      <p>{{ group.description }}</p>
      <div class="chapter-grid">
        <RouterLink v-for="chapter in group.chapters" :key="chapter.id" :to="`/textbook/${chapter.id}`" class="chapter-card panel" data-test="chapter-card">
          <h3>{{ chapter.title }}</h3>
          <p>{{ chapter.summary }}</p>
          <span>{{ copy.textbookOpenTopic }} →</span>
        </RouterLink>
      </div>
    </section>
    <footer class="book-footer muted">{{ copy.textbookScope }}</footer>
  </main>
</template>

<style scoped>
.book-description { max-width: 75ch; line-height: 1.6; }
.book-search { display: grid; grid-template-columns: 1fr auto; gap: 10px; margin: 24px 0; }
.book-search label, .book-search p { grid-column: 1 / -1; margin: 0; }
.book-group { margin: 32px 0; }
.book-group h2 { margin-bottom: 8px; }
.chapter-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.chapter-card { display: flex; flex-direction: column; text-decoration: none; color: inherit; }
.chapter-card:hover { border-color: #216869; }
.chapter-card h3 { margin: 0 0 8px; color: #173b42; }
.chapter-card p { flex: 1; line-height: 1.5; margin: 0 0 16px; }
.chapter-card span { color: #0f5c6d; font-weight: 600; }
.book-footer { margin: 32px 0; line-height: 1.5; }
@media (max-width: 760px) { .chapter-grid { grid-template-columns: 1fr; } }
</style>
