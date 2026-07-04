import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

const routeParams = vi.hoisted(() => ({ value: { id: "7" } }));

vi.mock("vue-router", () => ({
  RouterLink: { template: "<a><slot /></a>" },
  useRoute: () => ({ params: routeParams.value }),
}));

vi.mock("../../src/api/client", () => ({
  getVocabularyWord: vi.fn().mockResolvedValue({
    id: 7,
    serbian_cyrillic: "хвала",
    serbian_latin: "hvala",
    russian_translation: "спасибо",
    cefr_level: "A1",
    theme: "greetings",
    usage_register: null,
    stress_marker: null,
    meaning_notes: null,
    example_sentences: null,
    example_translations: null,
  }),
  createVocabularyWord: vi.fn(),
  updateVocabularyWord: vi.fn().mockResolvedValue({ id: 7 }),
}));

import { createVocabularyWord, updateVocabularyWord } from "../../src/api/client";
import WordEditorView from "../../src/views/WordEditorView.vue";

describe("WordEditorView", () => {
  it("updates the routed word instead of creating a duplicate", async () => {
    const wrapper = mount(WordEditorView);
    await Promise.resolve();
    await Promise.resolve();

    await wrapper.get('input[type="password"]').setValue("dev-editor-password");
    await wrapper.get('input[name="serbian_latin"]').setValue("hvala updated");
    await wrapper.get("form").trigger("submit.prevent");

    expect(updateVocabularyWord).toHaveBeenCalledWith(
      7,
      expect.objectContaining({ serbian_latin: "hvala updated" }),
      "dev-editor-password",
    );
    expect(createVocabularyWord).not.toHaveBeenCalled();
  });
});
