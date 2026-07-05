<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView } from "vue-router";

import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const navLabel = computed(() => (sessionStore.uiLanguage.value === "sr" ? "Glavna navigacija" : "Главная навигация"));
</script>

<template>
  <div class="app-layout">
    <header class="app-header">
      <RouterLink class="brand" to="/dashboard">{{ copy.appTitle }}</RouterLink>
      <nav :aria-label="navLabel">
        <RouterLink to="/dashboard">{{ copy.dashboard }}</RouterLink>
        <RouterLink to="/new-words">{{ copy.newWords }}</RouterLink>
        <RouterLink to="/review">{{ copy.review }}</RouterLink>
        <RouterLink to="/vocabulary">{{ copy.vocabulary }}</RouterLink>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
