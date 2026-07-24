import { flushPromises, mount, RouterLinkStub } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

import VocabularyListView from "../../src/views/VocabularyListView.vue";

const apiMocks = vi.hoisted(() => ({
  listVocabulary: vi.fn(),
  listVocabularyThemes: vi.fn(),
  verifyEditorPassword: vi.fn(),
}));

vi.mock("../../src/api/client", () => apiMocks);

describe("VocabularyListView", () => {
  beforeEach(() => {
    apiMocks.listVocabulary.mockReset().mockResolvedValue([
      {
        id: 1,
        serbian_cyrillic: "радити",
        serbian_latin: "raditi",
        russian_translation: "делать",
        cefr_level: "A1",
        theme: "work",
        stress_marker: "legacy marker",
        stress_pattern: null,
      },
      {
        id: 2,
        serbian_cyrillic: "писати",
        serbian_latin: "pisati",
        russian_translation: "писать",
        cefr_level: "A1",
        theme: "work",
        stress_marker: "hidden marker",
        stress_pattern: {
          cyrillic_syllables: ["пи", "са", "ти"],
          latin_syllables: ["pi", "sa", "ti"],
          stressed_syllable_index: 0,
        },
      },
    ]);
    apiMocks.listVocabularyThemes.mockReset().mockResolvedValue([]);
    apiMocks.verifyEditorPassword.mockReset();
  });

  it("shows legacy stress metadata only without structured stress", async () => {
    const wrapper = mount(VocabularyListView, {
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    await flushPromises();

    expect(wrapper.findAll('[data-testid="legacy-stress"]').map((item) => item.text())).toEqual([
      "legacy marker",
    ]);
  });

  it("ignores verification that completes after the password changes", async () => {
    let resolveVerification!: () => void;
    apiMocks.verifyEditorPassword.mockReturnValue(new Promise<void>((resolve) => {
      resolveVerification = resolve;
    }));
    const wrapper = mount(VocabularyListView, {
      global: { stubs: { RouterLink: RouterLinkStub } },
    });
    await flushPromises();

    const password = wrapper.get('input[type="password"]');
    await password.setValue("old-password");
    await wrapper.get('button[type="button"]').trigger("click");
    await password.setValue("new-password");
    resolveVerification();
    await flushPromises();

    expect(wrapper.find('a[href="/editor"]').exists()).toBe(false);
  });
});
