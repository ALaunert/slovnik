<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import { createOrLoadProfile } from "../api/client";
import { sessionStore } from "../stores/session";

const router = useRouter();
const userId = ref(sessionStore.userId.value);
const error = ref("");
const isLoading = ref(false);

async function start() {
  const trimmed = userId.value.trim();
  if (!trimmed) {
    error.value = "Введите User ID";
    return;
  }
  isLoading.value = true;
  error.value = "";
  try {
    await createOrLoadProfile(trimmed);
    sessionStore.setUserId(trimmed);
    await router.push("/dashboard");
  } catch {
    error.value = "Не удалось загрузить профиль";
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <main class="page narrow-page">
    <section class="panel access-panel">
      <h1>Сербский словарь</h1>
      <form class="stack" @submit.prevent="start">
        <label>
          User ID
          <input v-model="userId" name="user_id" autocomplete="username" />
        </label>
        <button type="submit" :disabled="isLoading">{{ isLoading ? "Загрузка" : "Начать" }}</button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
    </section>
  </main>
</template>
