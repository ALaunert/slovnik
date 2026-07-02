import { createRouter, createWebHistory } from "vue-router";

import DashboardView from "./views/DashboardView.vue";
import UserAccessView from "./views/UserAccessView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", component: UserAccessView },
    { path: "/dashboard", component: DashboardView },
  ],
});
