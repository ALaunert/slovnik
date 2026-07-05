<script setup lang="ts">
import { computed } from "vue";

import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

defineProps<{ correct: boolean; repeat?: boolean }>();

const copy = computed(() => messages[sessionStore.uiLanguage.value]);
</script>

<template>
  <div class="feedback" :class="correct ? 'feedback-ok' : 'feedback-bad'">
    <strong>{{ correct ? copy.correct : copy.needsRepeat }}</strong>
    <span v-if="repeat">{{ copy.repeatAgain }}</span>
  </div>
</template>
