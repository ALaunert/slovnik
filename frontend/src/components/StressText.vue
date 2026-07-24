<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  word: string;
  syllables?: string[] | null;
  stressedIndex?: number | null;
}>();

const hasValidPattern = computed(() => {
  const { syllables, stressedIndex } = props;
  return (
    syllables != null
    && stressedIndex != null
    && Number.isInteger(stressedIndex)
    && stressedIndex >= 0
    && stressedIndex < syllables.length
    && syllables.every((syllable) => syllable.trim().length > 0)
    && syllables.join("").normalize("NFC") === props.word.normalize("NFC")
  );
});
</script>

<template>
  <span>
    <template v-if="hasValidPattern">
      <template v-for="(syllable, index) in props.syllables" :key="index">
        <strong v-if="index === props.stressedIndex">{{ syllable }}</strong>
        <template v-else>{{ syllable }}</template>
      </template>
    </template>
    <template v-else>{{ props.word }}</template>
  </span>
</template>
