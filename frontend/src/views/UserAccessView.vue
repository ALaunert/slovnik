<script setup lang="ts">
import { computed, ref } from "vue";
import { useRouter } from "vue-router";

import { createOrLoadProfile } from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

const router = useRouter();
const userId = ref(sessionStore.userId.value);
const error = ref("");
const isLoading = ref(false);
const copy = computed(() => messages[sessionStore.uiLanguage.value]);

async function start() {
  const trimmed = userId.value.trim();
  if (!trimmed) {
    error.value = copy.value.userIdRequired;
    return;
  }
  isLoading.value = true;
  error.value = "";
  try {
    const profile = await createOrLoadProfile(trimmed);
    sessionStore.setUserId(trimmed);
    sessionStore.setUiLanguage(profile.ui_language);
    await router.push("/dashboard");
  } catch {
    error.value = copy.value.loadProfileError;
  } finally {
    isLoading.value = false;
  }
}
</script>

<template>
  <main class="page narrow-page">
    <section class="panel access-panel">
      <h1>{{ copy.appTitle }}</h1>
      <form class="stack" @submit.prevent="start">
        <label>
          User ID
          <input v-model="userId" name="user_id" autocomplete="username" />
        </label>
        <button type="submit" :disabled="isLoading">{{ isLoading ? copy.loading : copy.start }}</button>
        <p v-if="error" class="error">{{ error }}</p>
      </form>
    </section>
  </main>
</template>
