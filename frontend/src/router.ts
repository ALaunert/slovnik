import { createRouter, createWebHistory } from "vue-router";

import DashboardView from "./views/DashboardView.vue";
import UserAccessView from "./views/UserAccessView.vue";
import VocabularyListView from "./views/VocabularyListView.vue";
import WordEditorView from "./views/WordEditorView.vue";
import NewWordsView from "./views/NewWordsView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: UserAccessView },
    { path: "/dashboard", component: DashboardView },
    { path: "/vocabulary", component: VocabularyListView },
    { path: "/new-words", component: NewWordsView },
    { path: "/editor", component: WordEditorView },
    { path: "/editor/:id", component: WordEditorView },
  ],
});
