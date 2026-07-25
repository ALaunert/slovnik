import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routerPush = vi.hoisted(() => vi.fn());
const apiMocks = vi.hoisted(() => ({
  completeReview: vi.fn(),
  getReviewWords: vi.fn(),
  submitReviewAnswer: vi.fn(),
}));

vi.mock("vue-router", () => ({
  RouterLink: { template: "<a><slot /></a>" },
  useRouter: () => ({ push: routerPush }),
}));

vi.mock("../../src/api/client", () => apiMocks);

import {
  getReviewWords,
  submitReviewAnswer,
  type VocabularyWord,
} from "../../src/api/client";
import { sessionStore } from "../../src/stores/session";
import ReviewView from "../../src/views/ReviewView.vue";

const firstWord = {
  id: 1,
  serbian_cyrillic: "хвала",
  serbian_latin: "hvala",
  russian_translation: "спасибо",
  cefr_level: "A1",
  theme: "общение",
  stress_marker: "хва́ла",
  meaning_notes: "Форма благодарности",
  example_sentences: "Хвала лепо.",
  example_translations: "Большое спасибо.",
  incorrect_count: 2,
  is_weak: true,
};

const secondWord = {
  id: 2,
  serbian_cyrillic: "вода",
  serbian_latin: "voda",
  russian_translation: "вода",
  cefr_level: "A1",
  theme: "еда",
};

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll("button").find((item) => item.text() === text);
  if (!button) throw new Error(`Missing button: ${text}`);
  return button;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

async function mountReview(words: VocabularyWord[] = [firstWord]) {
  vi.mocked(getReviewWords).mockResolvedValueOnce({ words });
  const wrapper = mount(ReviewView);
  await flushPromises();
  return wrapper;
}

describe("review API", () => {
  it("posts one typed review rating to the encoded user endpoint", async () => {
    const progress = {
      id: 8,
      user_id: "learner/one",
      word_id: 1,
      status: "reviewing",
      correct_count: 1,
      incorrect_count: 0,
      is_weak: false,
      next_review_at: "2026-07-27T12:00:00Z",
      review_interval_days: 2,
      review_streak: 1,
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: vi.fn().mockResolvedValue({ progress }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const client = await vi.importActual<typeof import("../../src/api/client")>("../../src/api/client");

    await client.submitReviewAnswer("learner/one", { word_id: 1, rating: "good" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/learning/learner%2Fone/review/answers",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ word_id: 1, rating: "good" }),
      },
    );
    vi.unstubAllGlobals();
  });
});

describe("ReviewView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStore.setUserId("learner-1");
    sessionStore.setUiLanguage("ru");
  });

  it("starts with only the Russian cue, level, and theme", async () => {
    const wrapper = await mountReview();
    const cue = wrapper.get("article.recall-cue");

    expect(cue.text()).toContain("Вспомните слово по переводу.");
    expect(cue.text()).toContain("спасибо");
    expect(cue.text()).toContain("A1");
    expect(cue.text()).toContain("общение");
    expect(wrapper.html()).not.toContain("хвала");
    expect(wrapper.html()).not.toContain("hvala");
    expect(wrapper.html()).not.toContain("хва́ла");
    expect(wrapper.text()).not.toContain("Форма благодарности");
    expect(wrapper.text()).not.toContain("Подробности");
    expect(wrapper.text()).not.toContain("Не вспомнил");
    expect(wrapper.text()).not.toContain("Вспомнил с трудом");
  });

  it("reveals the existing word card and four localized ratings", async () => {
    const wrapper = await mountReview();

    await buttonByText(wrapper, "Показать ответ").trigger("click");

    expect(wrapper.get(".word-card").text()).toContain("хвала / hvala");
    expect(wrapper.get(".word-card").text()).toContain("Форма благодарности");
    expect(wrapper.text()).toContain("Оцените, насколько легко удалось вспомнить слово.");
    expect(wrapper.get(".recall-rating-area").attributes("role")).toBe("group");
    expect(wrapper.get(".recall-rating-area").attributes("aria-labelledby")).toBe("recall-rating-guidance");
    expect(wrapper.findAll(".recall-ratings button").map((button) => button.text())).toEqual([
      "Не вспомнил",
      "Вспомнил с трудом",
      "Вспомнил",
      "Легко вспомнил",
    ]);
  });

  it("saves one rating, blocks duplicates while saving, and advances after success", async () => {
    const save = deferred<Awaited<ReturnType<typeof submitReviewAnswer>>>();
    vi.mocked(submitReviewAnswer).mockReturnValueOnce(save.promise);
    const wrapper = await mountReview([firstWord, secondWord]);
    await buttonByText(wrapper, "Показать ответ").trigger("click");

    const good = buttonByText(wrapper, "Вспомнил");
    await good.trigger("click");
    await wrapper.vm.$nextTick();

    expect(submitReviewAnswer).toHaveBeenCalledWith("learner-1", { word_id: 1, rating: "good" });
    expect(wrapper.findAll(".recall-ratings button").every((button) => button.attributes("disabled") !== undefined)).toBe(true);
    expect(wrapper.text()).toContain("Сохраняем...");
    await good.trigger("click");
    expect(submitReviewAnswer).toHaveBeenCalledTimes(1);

    save.resolve({ progress: {} as never });
    await flushPromises();

    expect(wrapper.text()).toContain("вода");
    expect(wrapper.find(".word-card").exists()).toBe(false);
    expect(wrapper.text()).toContain("Показать ответ");
  });

  it("shows completion after the final saved rating", async () => {
    vi.mocked(submitReviewAnswer).mockResolvedValueOnce({ progress: {} } as never);
    const wrapper = await mountReview();
    await buttonByText(wrapper, "Показать ответ").trigger("click");

    await buttonByText(wrapper, "Легко вспомнил").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Повторение завершено");
    expect(wrapper.find(".word-card").exists()).toBe(false);
  });

  it("moves focus through reveal, advance, and the announced completion state", async () => {
    vi.mocked(submitReviewAnswer).mockResolvedValue({ progress: {} } as never);
    vi.mocked(getReviewWords).mockResolvedValueOnce({ words: [firstWord, secondWord] });
    const wrapper = mount(ReviewView, { attachTo: document.body });
    await flushPromises();

    await buttonByText(wrapper, "Показать ответ").trigger("click");
    await flushPromises();
    expect(document.activeElement).toBe(wrapper.get(".recall-rating-area").element);

    await buttonByText(wrapper, "Вспомнил").trigger("click");
    await flushPromises();
    expect(document.activeElement).toBe(buttonByText(wrapper, "Показать ответ").element);

    await buttonByText(wrapper, "Показать ответ").trigger("click");
    await buttonByText(wrapper, "Вспомнил").trigger("click");
    await flushPromises();

    const completion = wrapper.get('[role="status"]');
    expect(completion.attributes("aria-live")).toBe("polite");
    expect(document.activeElement).toBe(completion.element);
    wrapper.unmount();
  });

  it("keeps the revealed card and enables retry when the failed rating remains due", async () => {
    vi.mocked(submitReviewAnswer).mockRejectedValueOnce(new Error("network"));
    const wrapper = await mountReview();
    vi.mocked(getReviewWords).mockResolvedValueOnce({ words: [firstWord] });
    await buttonByText(wrapper, "Показать ответ").trigger("click");

    await buttonByText(wrapper, "Не вспомнил").trigger("click");
    await flushPromises();

    expect(getReviewWords).toHaveBeenCalledTimes(2);
    expect(wrapper.get(".word-card").text()).toContain("хвала / hvala");
    expect(wrapper.text()).toContain("Не удалось сохранить оценку. Попробуйте ещё раз.");
    expect(wrapper.findAll(".recall-ratings button").every((button) => button.attributes("disabled") === undefined)).toBe(true);
  });

  it("advances when reconciliation shows the failed rating is no longer due", async () => {
    vi.mocked(submitReviewAnswer).mockRejectedValueOnce(new Error("response lost"));
    const wrapper = await mountReview([firstWord, secondWord]);
    vi.mocked(getReviewWords).mockResolvedValueOnce({ words: [secondWord] });
    await buttonByText(wrapper, "Показать ответ").trigger("click");

    await buttonByText(wrapper, "Вспомнил").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("вода");
    expect(wrapper.find(".word-card").exists()).toBe(false);
    expect(wrapper.text()).not.toContain("Не удалось сохранить оценку");
  });

  it("handles a failed reconciliation without an unhandled rejection and allows retry", async () => {
    vi.mocked(submitReviewAnswer)
      .mockRejectedValueOnce(new Error("network"))
      .mockResolvedValueOnce({ progress: {} } as never);
    const wrapper = await mountReview();
    vi.mocked(getReviewWords).mockRejectedValueOnce(new Error("offline"));
    await buttonByText(wrapper, "Показать ответ").trigger("click");

    await buttonByText(wrapper, "Вспомнил с трудом").trigger("click");
    await flushPromises();

    expect(wrapper.get(".word-card").text()).toContain("хвала / hvala");
    expect(wrapper.text()).toContain("Не удалось сохранить оценку. Попробуйте ещё раз.");
    expect(buttonByText(wrapper, "Вспомнил с трудом").attributes("disabled")).toBeUndefined();

    await buttonByText(wrapper, "Вспомнил с трудом").trigger("click");
    await flushPromises();

    expect(submitReviewAnswer).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).toContain("Повторение завершено");
  });

  it("localizes the recall prompt, reveal, ratings, and save error in Serbian", async () => {
    sessionStore.setUiLanguage("sr");
    vi.mocked(submitReviewAnswer).mockRejectedValueOnce(new Error("network"));
    const wrapper = await mountReview();
    vi.mocked(getReviewWords).mockResolvedValueOnce({ words: [firstWord] });

    expect(wrapper.text()).toContain("Priseti se reči na osnovu prevoda.");
    await buttonByText(wrapper, "Prikaži odgovor").trigger("click");
    expect(wrapper.findAll(".recall-ratings button").map((button) => button.text())).toEqual([
      "Nisam se setio/la",
      "Setio/la sam se uz trud",
      "Setio/la sam se",
      "Lako sam se setio/la",
    ]);

    await buttonByText(wrapper, "Nisam se setio/la").trigger("click");
    await flushPromises();

    expect(wrapper.text()).toContain("Ocena nije sačuvana. Pokušaj ponovo.");
  });
});
