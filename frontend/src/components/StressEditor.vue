<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import type { StressPattern } from "../api/client";
import { messages } from "../i18n/messages";
import StressText from "./StressText.vue";

type StressEditorLabels = {
  title: string;
  cyrillicSyllables: string;
  latinSyllables: string;
  splitHint: string;
  clear: string;
  invalidSplit: string;
  preview: string;
  selectStress: string;
  syllableLabel: string;
};

const defaultLabels: StressEditorLabels = {
  title: messages.ru.structuredStressTitle,
  cyrillicSyllables: messages.ru.cyrillicSyllables,
  latinSyllables: messages.ru.latinSyllables,
  splitHint: messages.ru.stressSplitHint,
  clear: messages.ru.stressClear,
  invalidSplit: messages.ru.stressInvalidSplit,
  preview: messages.ru.stressPreview,
  selectStress: messages.ru.stressSelect,
  syllableLabel: messages.ru.stressSyllableLabel,
};

const props = defineProps<{
  cyrillicWord: string;
  latinWord: string;
  modelValue: StressPattern | null;
  labels?: StressEditorLabels;
}>();

const emit = defineEmits<{
  "update:modelValue": [value: StressPattern | null];
}>();

const labels = computed(() => props.labels ?? defaultLabels);
const middleDot = "·";
const cyrillicInput = ref("");
const latinInput = ref("");
const selectedIndex = ref<number | null>(null);
const preserveLocalOnNextNull = ref(false);

function parseSegments(value: string): string[] {
  if (!value) return [];
  return value.split(middleDot).map((segment) => segment.trim());
}

const validSplit = computed(() => {
  const cyrillicSyllables = parseSegments(cyrillicInput.value);
  const latinSyllables = parseSegments(latinInput.value);
  const count = cyrillicSyllables.length;
  const hasValidShape = (
    count > 0
    && count === latinSyllables.length
    && [...cyrillicSyllables, ...latinSyllables].every((segment) => segment.length > 0)
  );
  if (!hasValidShape) return null;

  const reconstructsCyrillic = (
    cyrillicSyllables.join("").normalize("NFC")
    === props.cyrillicWord.normalize("NFC")
  );
  const reconstructsLatin = (
    latinSyllables.join("").normalize("NFC")
    === props.latinWord.normalize("NFC")
  );
  if (!reconstructsCyrillic || !reconstructsLatin) return null;

  return { cyrillicSyllables, latinSyllables };
});

const hasSplitInput = computed(() => cyrillicInput.value.length > 0 || latinInput.value.length > 0);
const selectedPattern = computed<StressPattern | null>(() => {
  const split = validSplit.value;
  const index = selectedIndex.value;
  if (!split || index === null || index < 0 || index >= split.cyrillicSyllables.length) return null;
  return {
    cyrillic_syllables: [...split.cyrillicSyllables],
    latin_syllables: [...split.latinSyllables],
    stressed_syllable_index: index,
  };
});

function patternsEqual(left: StressPattern | null, right: StressPattern | null): boolean {
  if (left === null || right === null) return left === right;
  return (
    left.stressed_syllable_index === right.stressed_syllable_index
    && left.cyrillic_syllables.length === right.cyrillic_syllables.length
    && left.latin_syllables.length === right.latin_syllables.length
    && left.cyrillic_syllables.every((value, index) => value === right.cyrillic_syllables[index])
    && left.latin_syllables.every((value, index) => value === right.latin_syllables[index])
  );
}

function emitPattern(pattern: StressPattern) {
  emit("update:modelValue", {
    cyrillic_syllables: [...pattern.cyrillic_syllables],
    latin_syllables: [...pattern.latin_syllables],
    stressed_syllable_index: pattern.stressed_syllable_index,
  });
}

watch(
  () => props.modelValue,
  (pattern) => {
    if (pattern === null) {
      if (preserveLocalOnNextNull.value) {
        preserveLocalOnNextNull.value = false;
        return;
      }
      cyrillicInput.value = "";
      latinInput.value = "";
      selectedIndex.value = null;
      return;
    }
    cyrillicInput.value = pattern.cyrillic_syllables.join(middleDot);
    latinInput.value = pattern.latin_syllables.join(middleDot);
    selectedIndex.value = pattern.stressed_syllable_index;
  },
  { deep: true, immediate: true },
);

watch(
  [cyrillicInput, latinInput, () => props.cyrillicWord, () => props.latinWord],
  () => {
    const pattern = selectedPattern.value;
    if (pattern) {
      if (!patternsEqual(pattern, props.modelValue)) emitPattern(pattern);
      return;
    }
    if (props.modelValue !== null) {
      selectedIndex.value = null;
      preserveLocalOnNextNull.value = true;
      emit("update:modelValue", null);
      void nextTick(() => {
        if (props.modelValue !== null) preserveLocalOnNextNull.value = false;
      });
    }
  },
);

function selectStress(index: number) {
  const split = validSplit.value;
  if (!split) return;
  selectedIndex.value = index;
  emitPattern({
    cyrillic_syllables: [...split.cyrillicSyllables],
    latin_syllables: [...split.latinSyllables],
    stressed_syllable_index: index,
  });
}

function clearStress() {
  preserveLocalOnNextNull.value = false;
  cyrillicInput.value = "";
  latinInput.value = "";
  selectedIndex.value = null;
  emit("update:modelValue", null);
}
</script>

<template>
  <section class="stress-editor">
    <div class="stress-editor-heading">
      <div>
        <h2>{{ labels.title }}</h2>
        <p class="muted">{{ labels.splitHint }}</p>
      </div>
      <button
        type="button"
        class="secondary-button"
        data-testid="clear-stress"
        @click="clearStress"
      >
        {{ labels.clear }}
      </button>
    </div>
    <div class="stress-input-grid">
      <label>
        {{ labels.cyrillicSyllables }}
        <input
          v-model="cyrillicInput"
          name="cyrillic_syllables"
          placeholder="ра·ди·ти"
          :aria-invalid="hasSplitInput && !validSplit ? 'true' : undefined"
          :aria-describedby="hasSplitInput && !validSplit ? 'stress-split-error' : undefined"
        />
      </label>
      <label>
        {{ labels.latinSyllables }}
        <input
          v-model="latinInput"
          name="latin_syllables"
          placeholder="ra·di·ti"
          :aria-invalid="hasSplitInput && !validSplit ? 'true' : undefined"
          :aria-describedby="hasSplitInput && !validSplit ? 'stress-split-error' : undefined"
        />
      </label>
    </div>
    <p
      v-if="hasSplitInput && !validSplit"
      id="stress-split-error"
      class="field-hint error"
      data-testid="stress-invalid"
      role="status"
    >
      {{ labels.invalidSplit }}
    </p>
    <template v-if="validSplit">
      <p class="stress-select-label">{{ labels.selectStress }}</p>
      <div class="stress-syllables">
        <button
          v-for="(_, index) in validSplit.cyrillicSyllables"
          :key="index"
          type="button"
          class="stress-syllable-button"
          :class="{ 'is-selected': selectedIndex === index }"
          :data-stress-index="index"
          :aria-label="`${labels.syllableLabel} ${index + 1}: ${validSplit.cyrillicSyllables[index]}, ${validSplit.latinSyllables[index]}`"
          :aria-pressed="selectedIndex === index"
          @click="selectStress(index)"
        >
          <span>{{ validSplit.cyrillicSyllables[index] }}</span>
          <span>{{ validSplit.latinSyllables[index] }}</span>
        </button>
      </div>
    </template>
    <div v-if="selectedPattern" class="stress-preview">
      <span class="muted">{{ labels.preview }}</span>
      <StressText
        :word="props.cyrillicWord"
        :syllables="selectedPattern.cyrillic_syllables"
        :stressed-index="selectedPattern.stressed_syllable_index"
      />
      <StressText
        :word="props.latinWord"
        :syllables="selectedPattern.latin_syllables"
        :stressed-index="selectedPattern.stressed_syllable_index"
      />
    </div>
  </section>
</template>
