import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const routeQuery = vi.hoisted(() => ({ value: { type: "daily" } }));
const routerPush = vi.hoisted(() => vi.fn());

vi.mock("vue-router", () => ({
  RouterLink: { template: "<a><slot /></a>" },
  useRoute: () => ({ query: routeQuery.value }),
  useRouter: () => ({ push: routerPush }),
}));

const apiMocks = vi.hoisted(() => ({
  startQuiz: vi.fn(),
  revealQuizAnswer: vi.fn(),
  submitQuizAnswer: vi.fn(),
  completeQuiz: vi.fn().mockResolvedValue({ score: 0, total_questions: 2, weak_word_ids: [1], mistakes: [] }),
}));

vi.mock("../../src/api/client", () => apiMocks);

import { completeQuiz, revealQuizAnswer, startQuiz, submitQuizAnswer } from "../../src/api/client";
import { sessionStore } from "../../src/stores/session";
import QuizView from "../../src/views/QuizView.vue";

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

function buttonByText(wrapper: ReturnType<typeof mount>, text: string) {
  const button = wrapper.findAll("button").find((item) => item.text() === text);
  if (!button) throw new Error(`Missing button: ${text}`);
  return button;
}

describe("QuizView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    routeQuery.value = { type: "daily" };
    sessionStore.setUserId("learner-1");
    sessionStore.setUiLanguage("ru");
    vi.mocked(completeQuiz).mockResolvedValue({ score: 0, total_questions: 2, weak_word_ids: [1], mistakes: [] });
  });

  it("requeues an incorrect word only once", async () => {
    vi.mocked(startQuiz).mockResolvedValueOnce({
      attempt_id: 12,
      quiz_type: "daily",
      questions: [{ word_id: 1, question_type: "sr_to_ru_choice", prompt: "хвала / hvala", choices: ["спасибо"] }],
    });
    vi.mocked(submitQuizAnswer).mockResolvedValue({ is_correct: false, repeat_word: true, is_weak: true });

    const wrapper = mount(QuizView);
    await flushPromises();

    await buttonByText(wrapper, "спасибо").trigger("click");
    await flushPromises();
    await buttonByText(wrapper, "Дальше").trigger("click");
    await flushPromises();
    await buttonByText(wrapper, "спасибо").trigger("click");
    await flushPromises();
    await buttonByText(wrapper, "Дальше").trigger("click");
    await flushPromises();

    expect(submitQuizAnswer).toHaveBeenCalledTimes(2);
    expect(completeQuiz).toHaveBeenCalledWith("learner-1", 12);
    expect(routerPush).toHaveBeenCalledWith("/results");
  });

  it("requeues the same word once for each missed question type", async () => {
    vi.mocked(startQuiz).mockResolvedValueOnce({
      attempt_id: 14,
      quiz_type: "daily",
      questions: [
        { word_id: 1, question_type: "sr_to_ru_choice", prompt: "хвала / hvala", choices: ["спасибо"] },
        { word_id: 1, question_type: "ru_to_sr_typing", prompt: "спасибо", choices: [] },
      ],
    });
    vi.mocked(submitQuizAnswer).mockResolvedValue({ is_correct: false, repeat_word: true, is_weak: true });

    const wrapper = mount(QuizView);
    await flushPromises();

    await buttonByText(wrapper, "спасибо").trigger("click");
    await flushPromises();
    await buttonByText(wrapper, "Дальше").trigger("click");
    await flushPromises();

    await wrapper.get('input[aria-label="Ответ"]').setValue("wrong");
    await wrapper.get("form").trigger("submit.prevent");
    await flushPromises();
    await buttonByText(wrapper, "Дальше").trigger("click");
    await flushPromises();

    await buttonByText(wrapper, "спасибо").trigger("click");
    await flushPromises();
    await buttonByText(wrapper, "Дальше").trigger("click");
    await flushPromises();

    await wrapper.get('input[aria-label="Ответ"]').setValue("wrong");
    await wrapper.get("form").trigger("submit.prevent");
    await flushPromises();
    await buttonByText(wrapper, "Дальше").trigger("click");
    await flushPromises();

    expect(submitQuizAnswer).toHaveBeenCalledTimes(4);
    expect(completeQuiz).toHaveBeenCalledWith("learner-1", 14);
  });

  it("does not reveal self-check answers until the learner asks", async () => {
    vi.mocked(startQuiz).mockResolvedValueOnce({
      attempt_id: 13,
      quiz_type: "daily",
      questions: [{
        word_id: 2,
        question_type: "remembered_forgot_self_check",
        prompt: "река / reka",
        choices: [],
      }],
    });
    vi.mocked(revealQuizAnswer).mockResolvedValueOnce({ answer: "вода" });

    const wrapper = mount(QuizView);
    await flushPromises();

    expect(wrapper.text()).not.toContain("вода");
    await buttonByText(wrapper, "Показать перевод").trigger("click");
    await flushPromises();

    expect(revealQuizAnswer).toHaveBeenCalledWith(
      "learner-1",
      13,
      2,
      "remembered_forgot_self_check",
    );
    expect(wrapper.text()).toContain("вода");
  });
});
