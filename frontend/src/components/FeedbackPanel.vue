<script setup lang="ts">
defineProps<{ correct: boolean; repeat?: boolean }>();
</script>

<template>
  <div class="feedback" :class="correct ? 'feedback-ok' : 'feedback-bad'">
    <strong>{{ correct ? "Верно" : "Нужно повторить" }}</strong>
    <span v-if="repeat">Слово появится еще раз в этой сессии.</span>
  </div>
</template>
