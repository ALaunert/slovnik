import { createRouter, createWebHistory } from "vue-router";

import DashboardView from "./views/DashboardView.vue";
import UserAccessView from "./views/UserAccessView.vue";
import VocabularyListView from "./views/VocabularyListView.vue";
import WordEditorView from "./views/WordEditorView.vue";
import NewWordsView from "./views/NewWordsView.vue";
import ReviewView from "./views/ReviewView.vue";
import QuizView from "./views/QuizView.vue";
import ResultsView from "./views/ResultsView.vue";
import PracticeView from "./views/PracticeView.vue";
import TextbookView from "./views/TextbookView.vue";
import TextbookChapterView from "./views/TextbookChapterView.vue";

export const router = createRouter({
  history: createWebHistory(),
  scrollBehavior(to, _from, savedPosition) {
    if (savedPosition) return savedPosition;
    if (to.path.startsWith("/textbook")) return { top: 0 };
  },
  routes: [
    { path: "/", component: UserAccessView },
    { path: "/dashboard", component: DashboardView },
    { path: "/vocabulary", component: VocabularyListView },
    { path: "/new-words", component: NewWordsView },
    { path: "/review", component: ReviewView },
    { path: "/quiz", component: QuizView },
    { path: "/results", component: ResultsView },
    { path: "/practice", component: PracticeView },
    { path: "/textbook", component: TextbookView },
    { path: "/textbook/:chapterId", component: TextbookChapterView },
    { path: "/editor", component: WordEditorView },
    { path: "/editor/:id", component: WordEditorView },
  ],
});
