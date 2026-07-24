import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import StressText from "../../src/components/StressText.vue";

describe("StressText", () => {
  it("bolds the complete selected syllable", () => {
    const wrapper = mount(StressText, {
      props: {
        word: "ljubav",
        syllables: ["lju", "bav"],
        stressedIndex: 0,
      },
    });

    expect(wrapper.text()).toBe("ljubav");
    expect(wrapper.get("strong").text()).toBe("lju");
  });

  it("supports Latin digraph and Cyrillic single-letter syllable arrays", () => {
    const latin = mount(StressText, {
      props: { word: "ljubav", syllables: ["lju", "bav"], stressedIndex: 0 },
    });
    const cyrillic = mount(StressText, {
      props: { word: "љубав", syllables: ["љу", "бав"], stressedIndex: 0 },
    });

    expect(latin.get("strong").text()).toBe("lju");
    expect(cyrillic.get("strong").text()).toBe("љу");
    expect(latin.text()).toBe("ljubav");
    expect(cyrillic.text()).toBe("љубав");
  });

  it.each([
    {
      name: "invalid reconstruction",
      props: { word: "raditi", syllables: ["ra", "diti-x"], stressedIndex: 0 },
    },
    {
      name: "invalid index",
      props: { word: "raditi", syllables: ["ra", "di", "ti"], stressedIndex: 3 },
    },
  ])("falls back to the exact plain word for $name", ({ props }) => {
    const wrapper = mount(StressText, { props });

    expect(wrapper.find("strong").exists()).toBe(false);
    expect(wrapper.text()).toBe("raditi");
  });

  it("falls back to the exact plain word for a missing pattern", () => {
    const wrapper = mount(StressText, {
      props: { word: "raditi", syllables: null, stressedIndex: null },
    });

    expect(wrapper.find("strong").exists()).toBe(false);
    expect(wrapper.text()).toBe("raditi");
  });

  it("renders HTML-like input as literal text", () => {
    const word = '<img src="x" onerror="alert(1)">';
    const wrapper = mount(StressText, {
      props: { word, syllables: [word], stressedIndex: 0 },
    });

    expect(wrapper.text()).toBe(word);
    expect(wrapper.get("strong").text()).toBe(word);
    expect(wrapper.find("img").exists()).toBe(false);
  });
});
