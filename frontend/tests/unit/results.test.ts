import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("vue-router", () => ({ RouterLink: { template: "<a><slot /></a>" } }));

import { sessionStore } from "../../src/stores/session";
import ResultsView from "../../src/views/ResultsView.vue";

describe("ResultsView", () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStore.setUiLanguage("ru");
  });

  it("shows first responses, repairs and self ratings apart from practice score", () => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      result_version: 2, breakdown_status: "available", answer_key_status: "frozen",
      score: 2, total_questions: 3, weak_word_ids: [], mistakes: [],
      first_attempt_correct: 0, first_attempt_eligible: 2,
      recovered_objective_items: 1, self_report_remembered: 1, self_report_total: 1,
    }));
    const text = mount(ResultsView).text();
    expect(text).toContain("Результат практики");
    expect(text).toContain("Первый ответ: 0 / 2");
    expect(text).toContain("Исправлено на повторе: 1");
    expect(text).toContain("Самооценка «помню»: 1 / 1");
  });

  it("labels an old cached result as unavailable", () => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      score: 1, total_questions: 1, weak_word_ids: [], mistakes: [],
    }));
    const text = mount(ResultsView).text();
    expect(text).toContain("Результат практики");
    expect(text).toContain("Разбивка недоступна");
    expect(text).not.toContain("Первый ответ: 0 / 0");
  });

  it("labels legacy-key attempts that still use editable vocabulary", () => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      result_version: 2, answer_key_status: "legacy", breakdown_status: "unavailable",
      score: 1, total_questions: 1, weak_word_ids: [], mistakes: [],
    }));
    expect(mount(ResultsView).text()).toContain("Старый способ проверки ответов");
  });

  it("shows not measured for zero eligible questions in Serbian", () => {
    sessionStore.setUiLanguage("sr");
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      result_version: 2, breakdown_status: "available", score: 1,
      total_questions: 1, weak_word_ids: [], mistakes: [],
      first_attempt_correct: 0, first_attempt_eligible: 0,
      recovered_objective_items: 0, self_report_remembered: 1, self_report_total: 1,
    }));
    expect(mount(ResultsView).text()).toContain("Nije mereno");
  });
});
