import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { VocabularyWord } from "../../src/api/client";
import WordCard from "../../src/components/WordCard.vue";

const BASE_WORD: VocabularyWord = {
  id: 1,
  serbian_cyrillic: "радити",
  serbian_latin: "raditi",
  russian_translation: "работать",
  cefr_level: "A1",
  theme: "verbs",
};

describe("WordCard", () => {
  it("renders structured stress instead of legacy stress metadata", () => {
    const wrapper = mount(WordCard, {
      props: {
        word: {
          ...BASE_WORD,
          stress_marker: "legacy marker",
          stress_pattern: {
            cyrillic_syllables: ["ра", "ди", "ти"],
            latin_syllables: ["ra", "di", "ti"],
            stressed_syllable_index: 0,
          },
        },
      },
    });

    expect(wrapper.findAll("h2 strong").map((item) => item.text())).toEqual(["ра", "ra"]);
    expect(wrapper.get(".eyebrow").text()).not.toContain("legacy marker");
  });

  it("shows legacy stress metadata when structured stress is absent", () => {
    const wrapper = mount(WordCard, {
      props: {
        word: {
          ...BASE_WORD,
          stress_marker: "legacy marker",
          stress_pattern: null,
        },
      },
    });

    expect(wrapper.find("h2 strong").exists()).toBe(false);
    expect(wrapper.get(".eyebrow").text()).toContain("legacy marker");
  });
});
