<script setup lang="ts">
import { RouterLink, RouterView } from "vue-router";

import { messages } from "../i18n/messages";

const copy = messages.ru;
</script>

<template>
  <div class="app-layout">
    <header class="app-header">
      <RouterLink class="brand" to="/dashboard">{{ copy.appTitle }}</RouterLink>
      <nav aria-label="Главная навигация">
        <RouterLink to="/dashboard">{{ copy.dashboard }}</RouterLink>
        <RouterLink to="/new-words">{{ copy.newWords }}</RouterLink>
        <RouterLink to="/review">{{ copy.review }}</RouterLink>
        <RouterLink to="/vocabulary">{{ copy.vocabulary }}</RouterLink>
      </nav>
    </header>
    <RouterView />
  </div>
</template>
