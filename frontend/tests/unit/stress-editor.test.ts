import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import StressEditor from "../../src/components/StressEditor.vue";

const validStressPattern = {
  cyrillic_syllables: ["ра", "ди", "ти"],
  latin_syllables: ["ra", "di", "ti"],
  stressed_syllable_index: 0,
};

describe("StressEditor", () => {
  it("emits aligned middle-dot syllables with one shared stress index", async () => {
    const wrapper = mount(StressEditor, {
      props: { cyrillicWord: "радити", latinWord: "raditi", modelValue: null },
    });

    await wrapper.get('[name="cyrillic_syllables"]').setValue("ра·ди·ти");
    await wrapper.get('[name="latin_syllables"]').setValue("ra·di·ti");
    await wrapper.get('[data-stress-index="1"]').trigger("click");

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual({
      cyrillic_syllables: ["ра", "ди", "ти"],
      latin_syllables: ["ra", "di", "ti"],
      stressed_syllable_index: 1,
    });
    expect(wrapper.get('[data-stress-index="1"]').classes()).toContain("is-selected");
    expect(wrapper.findAll(".stress-preview strong").map((node) => node.text())).toEqual(["ди", "di"]);
  });

  it("clears only its structured stress state", async () => {
    const wrapper = mount(StressEditor, {
      props: {
        cyrillicWord: "радити",
        latinWord: "raditi",
        modelValue: validStressPattern,
      },
    });

    await wrapper.get('[data-testid="clear-stress"]').trigger("click");

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toBeNull();
    expect((wrapper.get('[name="cyrillic_syllables"]').element as HTMLInputElement).value).toBe("");
    expect((wrapper.get('[name="latin_syllables"]').element as HTMLInputElement).value).toBe("");
    expect(wrapper.find("[data-stress-index]").exists()).toBe(false);
  });

  it("emits null and keeps the split visible when a headword makes it stale", async () => {
    const wrapper = mount(StressEditor, {
      props: {
        cyrillicWord: "радити",
        latinWord: "raditi",
        modelValue: validStressPattern,
      },
    });

    await wrapper.setProps({ cyrillicWord: "радити!" });

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toBeNull();
    expect((wrapper.get('[name="cyrillic_syllables"]').element as HTMLInputElement).value).toBe("ра·ди·ти");
    expect(wrapper.get('[data-testid="stress-invalid"]').text()).not.toBe("");
    expect(wrapper.find("[data-stress-index]").exists()).toBe(false);
  });

  it("synchronizes its inputs when modelValue changes after mount", async () => {
    const wrapper = mount(StressEditor, {
      props: { cyrillicWord: "радити", latinWord: "raditi", modelValue: null },
    });

    await wrapper.setProps({ modelValue: validStressPattern });

    expect((wrapper.get('[name="cyrillic_syllables"]').element as HTMLInputElement).value).toBe("ра·ди·ти");
    expect((wrapper.get('[name="latin_syllables"]').element as HTMLInputElement).value).toBe("ra·di·ti");
    expect(wrapper.get('[data-stress-index="0"]').classes()).toContain("is-selected");
  });

  it("accepts a later external clear after emitting a stale null without a bound parent", async () => {
    const wrapper = mount(StressEditor, {
      props: {
        cyrillicWord: "радити",
        latinWord: "raditi",
        modelValue: validStressPattern,
      },
    });

    await wrapper.setProps({ cyrillicWord: "радити!" });
    await Promise.resolve();
    await wrapper.setProps({ modelValue: null });

    expect((wrapper.get('[name="cyrillic_syllables"]').element as HTMLInputElement).value).toBe("");
    expect((wrapper.get('[name="latin_syllables"]').element as HTMLInputElement).value).toBe("");
  });

  it("accepts NFC-equivalent reconstruction", async () => {
    const decomposedCyrillic = "и\u0301";
    const decomposedLatin = "i\u0301";
    const wrapper = mount(StressEditor, {
      props: { cyrillicWord: "и́ћи", latinWord: "íći", modelValue: null },
    });

    await wrapper.get('[name="cyrillic_syllables"]').setValue(`${decomposedCyrillic}·ћи`);
    await wrapper.get('[name="latin_syllables"]').setValue(`${decomposedLatin}·ći`);
    await wrapper.get('[data-stress-index="0"]').trigger("click");

    expect(wrapper.emitted("update:modelValue")?.at(-1)?.[0]).toEqual({
      cyrillic_syllables: [decomposedCyrillic, "ћи"],
      latin_syllables: [decomposedLatin, "ći"],
      stressed_syllable_index: 0,
    });
  });

  it("does not mutate model or emitted syllable arrays through shared references", async () => {
    const sourcePattern = {
      cyrillic_syllables: ["хва", "ла"],
      latin_syllables: ["hva", "la"],
      stressed_syllable_index: 0,
    };
    const wrapper = mount(StressEditor, {
      props: {
        cyrillicWord: "хвала",
        latinWord: "hvala",
        modelValue: sourcePattern,
      },
    });

    await wrapper.get('[data-stress-index="1"]').trigger("click");
    const emittedPattern = wrapper.emitted("update:modelValue")?.at(-1)?.[0] as typeof sourcePattern;
    emittedPattern.cyrillic_syllables[0] = "changed";
    emittedPattern.latin_syllables[0] = "changed";

    expect(sourcePattern.cyrillic_syllables).toEqual(["хва", "ла"]);
    expect(sourcePattern.latin_syllables).toEqual(["hva", "la"]);
  });

  it("rejects mismatched counts and empty trimmed segments", async () => {
    const wrapper = mount(StressEditor, {
      props: { cyrillicWord: "радити", latinWord: "raditi", modelValue: null },
    });

    await wrapper.get('[name="cyrillic_syllables"]').setValue("ра··дити");
    await wrapper.get('[name="latin_syllables"]').setValue("ra·diti");

    expect(wrapper.find("[data-stress-index]").exists()).toBe(false);
    expect(wrapper.get('[data-testid="stress-invalid"]').text()).not.toBe("");
    expect(wrapper.emitted("update:modelValue")).toBeUndefined();
  });
});
