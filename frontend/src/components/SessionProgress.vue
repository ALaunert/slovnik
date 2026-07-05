<script setup lang="ts">
import { computed } from "vue";

import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

function progressLabel(current: number, total: number) {
  return `${Math.min(current + 1, total)} / ${total}`;
}

function percent(current: number, total: number) {
  return total === 0 ? 0 : Math.round(((current + 1) / total) * 100);
}

const props = defineProps<{ current: number; total: number }>();
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
</script>

<template>
  <div class="session-progress" :aria-label="copy.progress">
    <span>{{ progressLabel(props.current, props.total) }}</span>
    <progress :value="percent(props.current, props.total)" max="100" />
  </div>
</template>
