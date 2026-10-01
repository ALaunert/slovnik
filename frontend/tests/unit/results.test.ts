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
  it("shows first responses, repairs and self ratings apart from practice score", () => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      result_version: 2, breakdown_status: "available", answer_key_status: "frozen",
      score: 2, total_questions: 3, weak_word_ids: [], mistakes: [],
      first_attempt_correct: 0, first_attempt_eligible: 2,
      recovered_objective_items: 1, self_report_remembered: 1, self_report_total: 1,
    }));
    const text = mount(ResultsView).text();
    expect(text).toContain("Практический результат");
    expect(text).toContain("Без подсказки с первого раза: 0 / 2");
    expect(text).toContain("Исправлено после ошибки: 1");
    expect(text).toContain("По самооценке: помню: 1 / 1");
  });

  it("labels an old cached result as unavailable", () => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      score: 1, total_questions: 1, weak_word_ids: [], mistakes: [],
    }));
    const text = mount(ResultsView).text();
    expect(text).toContain("Практический результат");
    expect(text).toContain("Разбивка недоступна");
    expect(text).not.toContain("Без подсказки с первого раза: 0 / 0");
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
  it.each([
    { first_attempt_status: "unavailable", first_attempt_correct: 0 },
    { first_attempt_status: "available", first_attempt_correct: null },
  ])("does not promote unavailable or incomplete counters to a measured result: %j", (fields) => {
    sessionStorage.setItem("slovnik.quizResults", JSON.stringify({
      ...legacy, result_version: 2, breakdown_status: "available",
      first_attempt_eligible: 2, recovered_objective_items: 1,
      self_report_remembered: 1, self_report_total: 1, ...fields,
    }));
    expect(mount(ResultsView).text()).toContain("Разбивка недоступна");
  });

});
