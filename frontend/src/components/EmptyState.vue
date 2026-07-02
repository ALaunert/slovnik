<script setup lang="ts">
defineProps<{ title: string; detail?: string }>();
</script>

<template>
  <div class="empty-state">
    <h2>{{ title }}</h2>
    <p v-if="detail">{{ detail }}</p>
  </div>
</template>
