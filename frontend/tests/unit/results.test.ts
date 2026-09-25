import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("vue-router", () => ({ RouterLink: { template: "<a><slot /></a>" } }));

import { sessionStore } from "../../src/stores/session";
import ResultsView from "../../src/views/ResultsView.vue";

const legacy = { score: 2, total_questions: 3, weak_word_ids: [], mistakes: [] };

describe("ResultsView evidence breakdown", () => {
  beforeEach(() => {
    sessionStorage.clear();
    sessionStore.setUiLanguage("ru");
  });

  it("labels an old cached result as a practice score and leaves breakdown unavailable", () => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify(legacy));
    const wrapper = mount(ResultsView);
    expect(wrapper.text()).toContain("Практический результат");
    expect(wrapper.text()).toContain("Учитывает исправления после ошибок");
    expect(wrapper.text()).toContain("Разбивка недоступна");
    expect(wrapper.text()).not.toContain("0%");
  });

  it("shows first attempts, recovery and self-ratings separately", () => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      ...legacy,
      result_version: 2,
      first_attempt_correct: 1,
      first_attempt_eligible: 2,
      first_attempt_status: "available",
      recovered_objective_items: 1,
      self_report_remembered: 1,
      self_report_total: 1,
    }));
    const wrapper = mount(ResultsView);
    expect(wrapper.text()).toContain("Без подсказки с первого раза");
    expect(wrapper.text()).toContain("1 / 2");
    expect(wrapper.text()).toContain("Исправлено после ошибки");
    expect(wrapper.text()).toContain("По самооценке");
    expect(wrapper.text()).not.toContain("Разбивка недоступна");
  });

  it("calls an empty objective denominator not measured in Serbian", () => {
    sessionStore.setUiLanguage("sr");
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      ...legacy,
      result_version: 2,
      first_attempt_correct: 0,
      first_attempt_eligible: 0,
      first_attempt_status: "not_measured",
      recovered_objective_items: 0,
      self_report_remembered: 1,
      self_report_total: 1,
    }));
    const wrapper = mount(ResultsView);
    expect(wrapper.text()).toContain("Nije mereno");
    expect(wrapper.text()).not.toContain("0%");
  });
});
