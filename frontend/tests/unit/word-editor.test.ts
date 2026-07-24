import { mount, type VueWrapper } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routeState = vi.hoisted(() => ({
  params: null as Record<string, string> | null,
}));
const loadedStressPattern = vi.hoisted(() => ({
  cyrillic_syllables: ["хва", "ла"],
  latin_syllables: ["hva", "la"],
  stressed_syllable_index: 0,
}));

vi.mock("vue-router", async () => {
  const { reactive } = await vi.importActual<typeof import("vue")>("vue");
  routeState.params = reactive({});
  return {
    RouterLink: {
      props: ["to"],
      template: '<a :href="to"><slot /></a>',
    },
    useRoute: () => ({ params: routeState.params! }),
  };
});

vi.mock("../../src/api/client", () => {
  class AiFillApiError extends Error {
    constructor(
      public readonly code: string,
      message: string,
      public readonly status: number,
    ) {
      super(message);
      this.name = "AiFillApiError";
    }
  }

  return {
    AiFillApiError,
    fillVocabularyWithAi: vi.fn(),
    getVocabularyWord: vi.fn(),
    createVocabularyWord: vi.fn(),
    updateVocabularyWord: vi.fn(),
    verifyEditorPassword: vi.fn(),
  };
});

import {
  AiFillApiError,
  createVocabularyWord,
  fillVocabularyWithAi,
  getVocabularyWord,
  updateVocabularyWord,
  verifyEditorPassword,
} from "../../src/api/client";
import { sessionStore } from "../../src/stores/session";
import WordEditorView from "../../src/views/WordEditorView.vue";

const loadedWord = {
  id: 7,
  serbian_cyrillic: "хвала",
  serbian_latin: "hvala",
  russian_translation: "спасибо",
  cefr_level: "A1",
  theme: "greetings",
  usage_register: null,
  stress_marker: null,
  stress_pattern: loadedStressPattern,
  meaning_notes: null,
  example_sentences: null,
  example_translations: null,
};
const secondLoadedWord = {
  ...loadedWord,
  id: 8,
  serbian_cyrillic: "жена",
  serbian_latin: "žena",
  russian_translation: "женщина",
  theme: "people",
  stress_pattern: {
    cyrillic_syllables: ["же", "на"],
    latin_syllables: ["že", "na"],
    stressed_syllable_index: 0,
  },
};
const thirdLoadedWord = {
  ...secondLoadedWord,
  id: 9,
  serbian_cyrillic: "радити",
  serbian_latin: "raditi",
  russian_translation: "работать",
  theme: "daily-life",
  stress_pattern: {
    cyrillic_syllables: ["ра", "ди", "ти"],
    latin_syllables: ["ra", "di", "ti"],
    stressed_syllable_index: 0,
  },
};

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
  await Promise.resolve();
}

async function unlockEditor(wrapper: VueWrapper) {
  await wrapper.get('input[name="editor_password"]').setValue("dev-editor-password");
  await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
  await flushPromises();
}

async function requestAiFill(wrapper: VueWrapper, sourceWord = "raditi") {
  await wrapper.get('input[name="ai_source_word"]').setValue(sourceWord);
  await wrapper.get('[data-testid="ai-fill-button"]').trigger("click");
  await flushPromises();
}

describe("WordEditorView", () => {
  beforeEach(() => {
    const params = routeState.params!;
    Object.keys(params).forEach((key) => delete params[key]);
    params.id = "7";
    sessionStore.setUiLanguage("ru");
    vi.mocked(getVocabularyWord).mockReset().mockResolvedValue(loadedWord);
    vi.mocked(createVocabularyWord).mockReset().mockResolvedValue({ id: 8 } as never);
    vi.mocked(updateVocabularyWord).mockReset().mockResolvedValue({ id: 7 } as never);
    vi.mocked(verifyEditorPassword).mockReset().mockResolvedValue(undefined);
    vi.mocked(fillVocabularyWithAi).mockReset().mockResolvedValue({
      status: "generated",
      source: "openai",
      payload: {},
      missing_required_fields: [],
    });
  });

  it("hides AI fill before unlock and disables a blank request after unlock", async () => {
    const wrapper = mount(WordEditorView);

    expect(wrapper.find('[data-testid="ai-fill"]').exists()).toBe(false);

    await unlockEditor(wrapper);

    expect(wrapper.get('[data-testid="ai-fill"]').isVisible()).toBe(true);
    expect(wrapper.get('[data-testid="ai-fill-button"]').attributes("disabled")).toBeDefined();
  });

  it("does not unlock when the submitted password changes before verification resolves", async () => {
    let resolveVerification!: () => void;
    vi.mocked(verifyEditorPassword).mockReturnValue(new Promise((resolve) => {
      resolveVerification = resolve;
    }));
    const wrapper = mount(WordEditorView);

    await wrapper.get('input[name="editor_password"]').setValue("old-password");
    await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
    await wrapper.get('input[name="editor_password"]').setValue("new-password");
    resolveVerification();
    await flushPromises();

    expect(wrapper.find('[data-testid="ai-fill"]').exists()).toBe(false);
    expect(getVocabularyWord).not.toHaveBeenCalled();
  });

  it("ignores an older verification rejection after a newer attempt unlocks", async () => {
    let rejectFirstVerification!: (error: Error) => void;
    const firstVerification = new Promise<void>((_, reject) => {
      rejectFirstVerification = reject;
    });
    vi.mocked(verifyEditorPassword).mockImplementation((password) => (
      password === "old-password" ? firstVerification : Promise.resolve()
    ));
    const wrapper = mount(WordEditorView);

    await wrapper.get('input[name="editor_password"]').setValue("old-password");
    await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
    await wrapper.get('input[name="editor_password"]').setValue("new-password");
    await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
    await flushPromises();
    expect(wrapper.get('[data-testid="ai-fill"]').isVisible()).toBe(true);

    rejectFirstVerification(new Error("stale rejection"));
    await flushPromises();

    expect(wrapper.get('[data-testid="ai-fill"]').isVisible()).toBe(true);
    expect(wrapper.text()).not.toContain("Неверный пароль редактора");
  });

  it("shows a loading state while AI fill is pending", async () => {
    let resolveRequest!: (value: Awaited<ReturnType<typeof fillVocabularyWithAi>>) => void;
    vi.mocked(fillVocabularyWithAi).mockReturnValue(new Promise((resolve) => {
      resolveRequest = resolve;
    }));
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    await wrapper.get('input[name="ai_source_word"]').setValue("raditi");
    await wrapper.get('[data-testid="ai-fill-button"]').trigger("click");

    expect(wrapper.get('[data-testid="ai-fill-button"]').attributes("disabled")).toBeDefined();
    expect(wrapper.get('[data-testid="ai-fill-button"]').text()).toBe("Заполнение...");

    resolveRequest({
      status: "generated",
      source: "openai",
      payload: {},
      missing_required_fields: [],
    });
    await flushPromises();
  });

  it("cancels the loading state when a password change relocks the editor", async () => {
    let resolveRequest!: (value: Awaited<ReturnType<typeof fillVocabularyWithAi>>) => void;
    vi.mocked(fillVocabularyWithAi).mockReturnValue(new Promise((resolve) => {
      resolveRequest = resolve;
    }));
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await wrapper.get('input[name="ai_source_word"]').setValue("raditi");
    await wrapper.get('[data-testid="ai-fill-button"]').trigger("click");

    await wrapper.get('input[name="editor_password"]').setValue("new-password");
    await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.get('input[name="ai_source_word"]').attributes("disabled")).toBeUndefined();
    expect(wrapper.get('[data-testid="ai-fill-button"]').text()).toBe("Заполнить");

    resolveRequest({
      status: "generated",
      source: "openai",
      payload: { russian_translation: "late result" },
      missing_required_fields: [],
    });
    await flushPromises();
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("спасибо");
  });

  it("loads the new route word and ignores an AI response from the previous word", async () => {
    let resolveRequest!: (value: Awaited<ReturnType<typeof fillVocabularyWithAi>>) => void;
    vi.mocked(fillVocabularyWithAi).mockReturnValue(new Promise((resolve) => {
      resolveRequest = resolve;
    }));
    vi.mocked(getVocabularyWord).mockImplementation(async (id) => (
      id === 8 ? secondLoadedWord : loadedWord
    ));
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await wrapper.get('input[name="ai_source_word"]').setValue("raditi");
    await wrapper.get('[data-testid="ai-fill-button"]').trigger("click");

    routeState.params!.id = "8";
    await flushPromises();

    expect(getVocabularyWord).toHaveBeenCalledWith(8);
    expect((wrapper.get('[name="serbian_cyrillic"]').element as HTMLInputElement).value).toBe("жена");
    expect(wrapper.get('[data-testid="ai-fill-button"]').text()).toBe("Заполнить");

    resolveRequest({
      status: "generated",
      source: "openai",
      payload: { russian_translation: "stale AI result" },
      missing_required_fields: [],
    });
    await flushPromises();

    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("женщина");
  });

  it("loads the latest word when routes change again during an earlier route load", async () => {
    let resolveSecondWord!: (value: typeof secondLoadedWord) => void;
    const secondWordRequest = new Promise<typeof secondLoadedWord>((resolve) => {
      resolveSecondWord = resolve;
    });
    vi.mocked(getVocabularyWord).mockImplementation(async (id) => {
      if (id === 8) return secondWordRequest;
      if (id === 9) return thirdLoadedWord;
      return loadedWord;
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    routeState.params!.id = "8";
    await flushPromises();
    expect(getVocabularyWord).toHaveBeenCalledWith(8);

    routeState.params!.id = "9";
    await flushPromises();

    expect(getVocabularyWord).toHaveBeenCalledWith(9);
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("работать");

    resolveSecondWord(secondLoadedWord);
    await flushPromises();
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("работать");
  });

  it("does not re-unlock a route load after verified access was cleared", async () => {
    let resolveSecondWord!: (value: typeof secondLoadedWord) => void;
    vi.mocked(getVocabularyWord).mockImplementation(async (id) => {
      if (id !== 8) return loadedWord;
      return new Promise<typeof secondLoadedWord>((resolve) => {
        resolveSecondWord = resolve;
      });
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    routeState.params!.id = "8";
    await flushPromises();
    await wrapper.get('input[name="editor_password"]').setValue("changed-password");
    await wrapper.get('input[name="editor_password"]').setValue("dev-editor-password");
    resolveSecondWord(secondLoadedWord);
    await flushPromises();

    expect(wrapper.find('[data-testid="ai-fill"]').exists()).toBe(false);
  });

  it("ignores an older route-load rejection after a newer unlock succeeds", async () => {
    let rejectRouteLoad!: (error: Error) => void;
    let routeEightCalls = 0;
    vi.mocked(getVocabularyWord).mockImplementation(async (id) => {
      if (id !== 8) return loadedWord;
      routeEightCalls += 1;
      if (routeEightCalls === 1) {
        return new Promise<typeof secondLoadedWord>((_, reject) => {
          rejectRouteLoad = reject;
        });
      }
      return secondLoadedWord;
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    routeState.params!.id = "8";
    await flushPromises();
    await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
    await flushPromises();
    expect(wrapper.get('[data-testid="ai-fill"]').isVisible()).toBe(true);

    rejectRouteLoad(new Error("stale route failure"));
    await flushPromises();
    expect(wrapper.text()).not.toContain("Не удалось загрузить слово");

    await wrapper.get('input[name="editor_password"]').setValue("changed-password");
    expect(wrapper.find('[data-testid="ai-fill"]').exists()).toBe(false);
  });

  it("clears stale edit data before unlocking the create route", async () => {
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    expect((wrapper.get('[name="serbian_cyrillic"]').element as HTMLInputElement).value).toBe("хвала");

    await wrapper.get('input[name="editor_password"]').setValue("changed-password");
    delete routeState.params!.id;
    await flushPromises();
    await wrapper.get('input[name="editor_password"]').setValue("dev-editor-password");
    await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
    await flushPromises();

    expect((wrapper.get('[name="serbian_cyrillic"]').element as HTMLInputElement).value).toBe("");
    expect((wrapper.get('[name="serbian_latin"]').element as HTMLInputElement).value).toBe("");
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("");
  });

  it("applies only returned fields and sends the current route id", async () => {
    vi.mocked(fillVocabularyWithAi).mockResolvedValue({
      status: "generated",
      source: "openai",
      payload: {
        russian_translation: "благодарю",
        meaning_notes: "Новая заметка",
      },
      missing_required_fields: [],
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    await requestAiFill(wrapper);

    expect(fillVocabularyWithAi).toHaveBeenCalledWith(
      "raditi",
      "dev-editor-password",
      7,
    );
    expect((wrapper.get('[name="serbian_cyrillic"]').element as HTMLInputElement).value).toBe("хвала");
    expect((wrapper.get('[name="serbian_latin"]').element as HTMLInputElement).value).toBe("hvala");
    expect((wrapper.get('[name="theme"]').element as HTMLInputElement).value).toBe("greetings");
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("благодарю");
    expect((wrapper.get('[name="meaning_notes"]').element as HTMLTextAreaElement).value).toBe("Новая заметка");
    expect(wrapper.get('[data-testid="ai-info"]').text()).toContain("OpenAI");
    expect(wrapper.get('[data-testid="ai-info"]').attributes("role")).toBe("status");
  });

  it("restores the complete pre-fill form including structured stress", async () => {
    vi.mocked(fillVocabularyWithAi).mockResolvedValue({
      status: "generated",
      source: "openai",
      payload: {
        serbian_cyrillic: "жена",
        serbian_latin: "žena",
        russian_translation: "женщина",
        cefr_level: "A2",
        theme: "people",
        usage_register: "neutral",
        stress_pattern: {
          cyrillic_syllables: ["же", "на"],
          latin_syllables: ["že", "na"],
          stressed_syllable_index: 0,
        },
        meaning_notes: "AI note",
        example_sentences: "Ona je žena.",
        example_translations: "Она женщина.",
      },
      missing_required_fields: [],
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await wrapper.get('[name="usage_register"]').setValue("formal");
    await wrapper.get('[name="stress_marker"]').setValue("хва̑ла");
    await wrapper.get('[name="meaning_notes"]').setValue("old note");
    await wrapper.get('[name="example_sentences"]').setValue("Hvala lepo.");
    await wrapper.get('[name="example_translations"]').setValue("Большое спасибо.");

    await requestAiFill(wrapper);
    await wrapper.get('[data-testid="ai-restore"]').trigger("click");
    await flushPromises();

    expect((wrapper.get('[name="serbian_cyrillic"]').element as HTMLInputElement).value).toBe("хвала");
    expect((wrapper.get('[name="serbian_latin"]').element as HTMLInputElement).value).toBe("hvala");
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("спасибо");
    expect((wrapper.get('[name="cefr_level"]').element as HTMLSelectElement).value).toBe("A1");
    expect((wrapper.get('[name="theme"]').element as HTMLInputElement).value).toBe("greetings");
    expect((wrapper.get('[name="usage_register"]').element as HTMLInputElement).value).toBe("formal");
    expect((wrapper.get('[name="stress_marker"]').element as HTMLInputElement).value).toBe("хва̑ла");
    expect((wrapper.get('[name="meaning_notes"]').element as HTMLTextAreaElement).value).toBe("old note");
    expect((wrapper.get('[name="example_sentences"]').element as HTMLTextAreaElement).value).toBe("Hvala lepo.");
    expect((wrapper.get('[name="example_translations"]').element as HTMLTextAreaElement).value).toBe("Большое спасибо.");
    expect((wrapper.get('[name="cyrillic_syllables"]').element as HTMLInputElement).value).toBe("хва·ла");
    expect((wrapper.get('[name="latin_syllables"]').element as HTMLInputElement).value).toBe("hva·la");
    expect(wrapper.get('[data-stress-index="0"]').classes()).toContain("is-selected");
    expect(wrapper.find('[data-testid="ai-restore"]').exists()).toBe(false);
  });

  it("derives missing markers from the merged current form and clears them while typing", async () => {
    vi.mocked(fillVocabularyWithAi).mockResolvedValue({
      status: "generated",
      source: "store",
      payload: { russian_translation: "спасибо" },
      missing_required_fields: ["serbian_cyrillic", "theme"],
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await wrapper.get('[name="serbian_cyrillic"]').setValue("");

    await requestAiFill(wrapper);

    expect(wrapper.get('[data-field="serbian_cyrillic"]').classes()).toContain("is-missing");
    expect(wrapper.get('[data-field="theme"]').classes()).not.toContain("is-missing");
    expect(wrapper.find('[data-missing-field="theme"]').exists()).toBe(false);

    await wrapper.get('[name="serbian_cyrillic"]').setValue("хвала");

    expect(wrapper.get('[data-field="serbian_cyrillic"]').classes()).not.toContain("is-missing");
    expect(wrapper.find('[data-testid="ai-missing-hint"]').exists()).toBe(false);
  });

  it("shows an existing-word link without navigating or mutating the form", async () => {
    vi.mocked(fillVocabularyWithAi).mockResolvedValue({
      status: "already_exists",
      word_id: 42,
      message: "Word already exists.",
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await wrapper.get('[name="meaning_notes"]').setValue("keep me");

    await requestAiFill(wrapper);

    expect((wrapper.get('[name="serbian_cyrillic"]').element as HTMLInputElement).value).toBe("хвала");
    expect((wrapper.get('[name="meaning_notes"]').element as HTMLTextAreaElement).value).toBe("keep me");
    expect(wrapper.get('[data-testid="existing-word-link"]').attributes("href")).toBe("/editor/42");
    expect(wrapper.get('[data-testid="ai-info"]').text()).toContain("уже есть");
    expect(wrapper.get('[data-testid="ai-info"]').attributes("role")).toBe("status");
  });

  it("preserves the form in a dismissible localized technical-error toast", async () => {
    vi.mocked(fillVocabularyWithAi).mockRejectedValue(
      new AiFillApiError("openai_timeout", "AI fill timed out.", 503),
    );
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await wrapper.get('[name="meaning_notes"]').setValue("keep me");

    await requestAiFill(wrapper);

    expect((wrapper.get('[name="meaning_notes"]').element as HTMLTextAreaElement).value).toBe("keep me");
    expect(wrapper.get('[role="alert"]').text()).toContain("ИИ не ответил вовремя");

    await wrapper.get('[data-testid="dismiss-ai-error"]').trigger("click");

    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
  });

  it("keeps the previous AI undo action accessible after a later request errors", async () => {
    vi.mocked(fillVocabularyWithAi)
      .mockResolvedValueOnce({
        status: "generated",
        source: "openai",
        payload: { russian_translation: "благодарю" },
        missing_required_fields: [],
      })
      .mockRejectedValueOnce(
        new AiFillApiError("openai_timeout", "AI fill timed out.", 503),
      );
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    await requestAiFill(wrapper);
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("благодарю");
    await requestAiFill(wrapper, "hvala");

    expect(wrapper.get('[role="alert"]').text()).toContain("ИИ не ответил вовремя");
    expect(wrapper.get('[data-testid="ai-restore"]').isVisible()).toBe(true);

    await wrapper.get('[data-testid="ai-restore"]').trigger("click");
    await flushPromises();

    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("спасибо");
  });

  it("clears the AI undo snapshot when a password change relocks the editor", async () => {
    vi.mocked(fillVocabularyWithAi).mockResolvedValue({
      status: "generated",
      source: "openai",
      payload: { russian_translation: "благодарю" },
      missing_required_fields: [],
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await requestAiFill(wrapper);
    expect(wrapper.get('[data-testid="ai-restore"]').isVisible()).toBe(true);

    await wrapper.get('input[name="editor_password"]').setValue("changed-password");
    await wrapper.get('input[name="editor_password"]').setValue("dev-editor-password");
    await wrapper.get('[data-testid="unlock-form"]').trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.find('[data-testid="ai-restore"]').exists()).toBe(false);
    expect((wrapper.get('[name="russian_translation"]').element as HTMLInputElement).value).toBe("спасибо");
  });

  it("uses neutral copy for a stored generation", async () => {
    vi.mocked(fillVocabularyWithAi).mockResolvedValue({
      status: "generated",
      source: "store",
      payload: {},
      missing_required_fields: [],
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    await requestAiFill(wrapper);

    expect(wrapper.get('[data-testid="ai-info"]').text()).toContain("сохраненный результат");
    expect(wrapper.get('[data-testid="ai-info"]').text()).not.toContain("OpenAI");
  });

  it.each([
    { language: "ru" as const, title: "Заполнение с ИИ", fill: "Заполнить", stress: "Ударение по слогам" },
    { language: "sr" as const, title: "Popunjavanje pomoću AI", fill: "Popuni", stress: "Akcenat po slogovima" },
  ])("renders $language AI and stress copy", async ({ language, title, fill, stress }) => {
    sessionStore.setUiLanguage(language);
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    expect(wrapper.get('[data-testid="ai-fill"] h2').text()).toBe(title);
    expect(wrapper.get('[data-testid="ai-fill-button"]').text()).toBe(fill);
    expect(wrapper.get(".stress-editor h2").text()).toBe(stress);
  });

  it("resets missing-field mode after an ordinary successful save", async () => {
    vi.mocked(fillVocabularyWithAi).mockResolvedValue({
      status: "generated",
      source: "openai",
      payload: {},
      missing_required_fields: ["serbian_cyrillic"],
    });
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);
    await wrapper.get('[name="serbian_cyrillic"]').setValue("");
    await requestAiFill(wrapper);
    await wrapper.get('[name="serbian_cyrillic"]').setValue("хвала");

    await wrapper.get('[data-testid="word-form"]').trigger("submit.prevent");
    await flushPromises();
    await wrapper.get('[name="theme"]').setValue("");

    expect(updateVocabularyWord).toHaveBeenCalled();
    expect(wrapper.get('[data-field="theme"]').classes()).not.toContain("is-missing");
  });

  it("preserves loaded structured stress when an unrelated field changes", async () => {
    const wrapper = mount(WordEditorView);

    expect(wrapper.find('input[name="serbian_latin"]').exists()).toBe(false);
    expect(getVocabularyWord).not.toHaveBeenCalled();

    await unlockEditor(wrapper);
    expect(getVocabularyWord).toHaveBeenCalledWith(7);

    await wrapper.get('input[name="russian_translation"]').setValue("большое спасибо");
    await wrapper.get('[data-testid="word-form"]').trigger("submit.prevent");
    await flushPromises();

    expect(verifyEditorPassword).toHaveBeenCalledWith("dev-editor-password");
    expect(updateVocabularyWord).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        russian_translation: "большое спасибо",
        stress_pattern: loadedStressPattern,
      }),
      "dev-editor-password",
    );
    const submittedPattern = vi.mocked(updateVocabularyWord).mock.calls[0][1].stress_pattern;
    expect(submittedPattern).toEqual(loadedStressPattern);
    expect(submittedPattern).not.toBe(loadedStressPattern);
    expect(submittedPattern?.cyrillic_syllables).not.toBe(loadedStressPattern.cyrillic_syllables);
    expect(submittedPattern?.latin_syllables).not.toBe(loadedStressPattern.latin_syllables);
    submittedPattern!.cyrillic_syllables[0] = "changed";
    expect(loadedStressPattern.cyrillic_syllables).toEqual(["хва", "ла"]);
    expect(createVocabularyWord).not.toHaveBeenCalled();

    await wrapper.get('input[name="editor_password"]').setValue("changed-password");

    expect(wrapper.find('input[name="serbian_latin"]').exists()).toBe(false);
    expect(wrapper.find('[data-testid="ai-fill"]').exists()).toBe(false);
  });

  it.each([
    { field: "serbian_cyrillic", value: "хвала!" },
    { field: "serbian_latin", value: "hvala!" },
  ])("clears stale structured stress when $field changes", async ({ field, value }) => {
    const wrapper = mount(WordEditorView);
    await unlockEditor(wrapper);

    await wrapper.get(`input[name="${field}"]`).setValue(value);
    await wrapper.get('[data-testid="word-form"]').trigger("submit.prevent");
    await flushPromises();

    expect(updateVocabularyWord).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        [field]: value,
        stress_pattern: null,
      }),
      "dev-editor-password",
    );
  });
});
