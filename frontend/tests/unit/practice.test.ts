import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.hoisted(() => vi.fn());
const api = vi.hoisted(() => ({
  getPracticeAvailability: vi.fn(), createOrResumePractice: vi.fn(),
  getPracticeRun: vi.fn(), nextPracticeActivity: vi.fn(), submitPracticeResponse: vi.fn(),
  getPracticeFeedback: vi.fn(), createPracticeRepair: vi.fn(),
}));
vi.mock("vue-router", () => ({
  RouterLink: { template: "<a><slot /></a>" }, useRouter: () => ({ push }),
}));
vi.mock("../../src/api/client", () => api);

import PracticeView from "../../src/views/PracticeView.vue";
import { sessionStore } from "../../src/stores/session";

const activity = {
  id: "activity-1", kind: "exercise", operation: "transform", cue_level: "full",
  status: "pending", sequence_number: 1, capability: "apply_construction",
  context_family: "request-practice", task: {
    input: "Вода доступна; сок закончился.", instruction_ru: "Попросите воду.", format: "sentence",
  }, response_contract: { kind: "text", max_codepoints: 2000 }, presentation: null,
  selection_reasons: ["new_target"], result: null,
};
const run = { schema_version: 1, id: "run-1", status: "active", policy_version: "local-written-selector-v2", activities: [] };
const result = { event_id: "event-1", outcome: "unresolved", first_response: "Можно воду?" };

async function load(autoStart = true) {
  const wrapper = mount(PracticeView);
  await flushPromises();
  if (autoStart && wrapper.find("[data-test=start-practice]").exists()) {
    await wrapper.get("[data-test=start-practice]").trigger("click");
    await flushPromises();
  }
  return wrapper;
}

describe("local written practice", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    sessionStorage.clear();
    sessionStore.setUserId("learner-1");
    sessionStore.setUiLanguage("ru");
    api.getPracticeAvailability.mockResolvedValue(true);
    api.createOrResumePractice.mockResolvedValue(run);
    api.getPracticeRun.mockResolvedValue(run);
    api.nextPracticeActivity.mockResolvedValue({ activity, reason: null });
    api.submitPracticeResponse.mockResolvedValue(result);
  });

  it("renders only the public task until submission and saves an unresolved first answer", async () => {
    const wrapper = await load();
    expect(wrapper.text()).toContain("Попросите воду.");
    expect(wrapper.text()).not.toContain("Молим воду.");
    await wrapper.get("textarea").setValue("Можно воду?");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Ответ сохранён без однозначной оценки");
    expect(wrapper.text()).toContain("Можно воду?");
    expect(api.submitPracticeResponse.mock.calls[0][2]).toMatchObject({ response: "Можно воду?" });
    expect(wrapper.find("textarea").exists()).toBe(false);
    wrapper.unmount();
  });

  it("freezes a failed submission and retries its original token and answer after remount", async () => {
    api.submitPracticeResponse.mockRejectedValueOnce(new Error("response lost"));
    let wrapper = await load();
    await wrapper.get("textarea").setValue("Можно воду?");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    const first = api.submitPracticeResponse.mock.calls[0];
    expect(wrapper.text()).toContain("Повторить отправку");
    wrapper.unmount();
    api.createOrResumePractice.mockResolvedValue({ ...run, activities: [activity] });
    wrapper = await load();
    await wrapper.get("[data-test=retry-submit]").trigger("click");
    await flushPromises();
    expect(api.submitPracticeResponse.mock.calls[1]).toEqual(first);
    wrapper.unmount();
  });

  it("can reload a failed resume while keeping the frozen answer and token", async () => {
    api.submitPracticeResponse.mockRejectedValueOnce(new Error("lost"));
    let wrapper = await load();
    await wrapper.get("textarea").setValue("Можно воду?");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    const original = api.submitPracticeResponse.mock.calls[0];
    wrapper.unmount();
    api.createOrResumePractice.mockRejectedValueOnce(new Error("offline"));
    wrapper = await load();
    const reload = wrapper.findAll("button").find((button) => button.text() === "Загрузить снова");
    expect(reload).toBeDefined();
    api.createOrResumePractice.mockResolvedValue({ ...run, activities: [activity] });
    await reload!.trigger("click");
    await flushPromises();
    await wrapper.get("[data-test=retry-submit]").trigger("click");
    await flushPromises();
    expect(api.submitPracticeResponse.mock.calls[1]).toEqual(original);
    wrapper.unmount();
  });

  it("lets the learner request a non-scored example before first issuance", async () => {
    const wrapper = await load(false);
    expect(api.nextPracticeActivity).not.toHaveBeenCalled();
    expect(wrapper.find("[data-test=start-exposure]").exists()).toBe(true);
    await wrapper.get("[data-test=start-exposure]").trigger("click");
    await flushPromises();
    expect(api.nextPracticeActivity).toHaveBeenCalledWith("learner-1", expect.any(String), "exposure");
    wrapper.unmount();
  });

  it("resumes a saved terminal result without issuing another task", async () => {
    const wrapper = await load();
    wrapper.unmount();
    api.createOrResumePractice.mockResolvedValue({ ...run, activities: [{ ...activity, status: "completed", result }] });
    api.nextPracticeActivity.mockClear();
    const resumed = await load();
    expect(resumed.text()).toContain("Можно воду?");
    expect(api.nextPracticeActivity).not.toHaveBeenCalled();
    resumed.unmount();
  });

  it("shows a reason when no activity is available and stops without claiming mastery", async () => {
    api.nextPracticeActivity.mockResolvedValue({ activity: null, reason: "empty_frontier" });
    const wrapper = await load();
    expect(wrapper.text()).toContain("Нет подходящего задания");
    await wrapper.get("[data-test=stop-practice]").trigger("click");
    expect(push).toHaveBeenCalledWith("/dashboard");
    expect(wrapper.text()).not.toContain("освоен");
    wrapper.unmount();
  });

  it("renders exposure as presentation and sends no answer", async () => {
    api.nextPracticeActivity.mockResolvedValue({ activity: {
      ...activity, kind: "exposure", operation: null, response_contract: null,
      presentation: { serbian: "Молим воду.", translation: "Воду, пожалуйста." },
    }, reason: null });
    api.submitPracticeResponse.mockResolvedValue({ event_id: "exposure-1", outcome: null, first_response: null });
    const wrapper = await load();
    expect(wrapper.text()).toContain("Молим воду.");
    expect(wrapper.find("textarea").exists()).toBe(false);
    await wrapper.get("[data-test=record-exposure]").trigger("click");
    await flushPromises();
    expect(api.submitPracticeResponse.mock.calls[0][2].response).toBeUndefined();
    expect(wrapper.text()).toContain("Просмотр сохранён");
    wrapper.unmount();
  });

  it.each(["recognize", "retrieve", "complete", "transform"])("renders %s from a public contract", async (operation) => {
    api.nextPracticeActivity.mockResolvedValue({ activity: {
      ...activity, operation, response_contract: operation === "recognize"
        ? { kind: "choice", max_options: 2, options: ["вода", "хлеб"] } : activity.response_contract,
    }, reason: null });
    const wrapper = await load();
    expect(wrapper.find("form").exists()).toBe(true);
    if (operation === "recognize") expect(wrapper.findAll("input[type=radio]")).toHaveLength(2);
    else expect(wrapper.find("textarea").exists()).toBe(true);
    wrapper.unmount();
  });

  it("fails closed and preserves old quiz storage when the pilot is unavailable", async () => {
    sessionStorage.setItem("quiz-result", "old-result");
    api.getPracticeAvailability.mockResolvedValue(false);
    const wrapper = await load();
    expect(api.createOrResumePractice).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("Локальная практика недоступна");
    expect(sessionStorage.getItem("quiz-result")).toBe("old-result");
    wrapper.unmount();
  });

  it("explains missing profile without calling it a disabled pilot", async () => {
    sessionStore.clearUserId();
    const wrapper = await load(false);
    expect(wrapper.text()).toContain("Выберите профиль для практики");
    expect(wrapper.text()).not.toContain("Локальная практика недоступна");
    expect(wrapper.find('[data-test=practice-profile-entry]').exists()).toBe(true);
    expect(sessionStorage.getItem("slovnik.practice.v1.")).toBeNull();
    expect(api.createOrResumePractice).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("can retry availability after the local pilot becomes available", async () => {
    api.getPracticeAvailability.mockResolvedValueOnce(false);
    const wrapper = await load(false);
    expect(wrapper.text()).toContain("Локальная практика недоступна");
    await wrapper.get('[data-test=retry-availability]').trigger('click');
    await flushPromises();
    expect(wrapper.text()).not.toContain("Локальная практика недоступна");
    expect(wrapper.find('[data-test=start-practice]').exists()).toBe(true);
    wrapper.unmount();
  });

  it("localizes controls and unresolved result in Serbian", async () => {
    sessionStore.setUiLanguage("sr");
    const wrapper = await load();
    expect(wrapper.text()).toContain("Pisana praksa");
    await wrapper.get("textarea").setValue("Можно воду?");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("Odgovor je sačuvan bez jednoznačne ocene");
    wrapper.unmount();
  });

  it("preserves the first error while showing a supported repair result", async () => {
    api.submitPracticeResponse.mockResolvedValueOnce({ ...result, outcome: "incorrect", first_response: "", evidence_kind: "first_answer" });
    api.createPracticeRepair.mockResolvedValue({ ...activity, id: "repair-1", retry_of: activity.id,
      support: { kind: "cue", instruction_ru: "Попросите воду.", example: null }, result: null });
    api.submitPracticeResponse.mockResolvedValueOnce({ ...result, outcome: "correct", first_response: "Молим воду.", evidence_kind: "repair" });
    const wrapper = await load();
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    await wrapper.get("[data-test=hint-repair]").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Подсказка перед повтором");
    await wrapper.get("textarea").setValue("Молим воду.");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("На повторе после помощи ответ принят");
    expect(wrapper.text()).toContain("В первом ответе обнаружено несоответствие заданию");
    expect(api.createPracticeRepair.mock.calls[0][2].support).toBe("cue");
    wrapper.unmount();
  });

  it("reserves revealed support before showing the reviewed example and keeps it on resume", async () => {
    const child = { ...activity, id: "repair-1", retry_of: activity.id,
      support: { kind: "reveal", instruction_ru: "Попросите воду.",
        example: { serbian: "Молим воду.", translation: "Воду, пожалуйста.", answer: "Молим воду." } }, result: null };
    api.createPracticeRepair.mockResolvedValue(child);
    let wrapper = await load();
    await wrapper.get("textarea").setValue("Можно воду?");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).not.toContain("Молим воду.");
    await wrapper.get("[data-test=show-feedback]").trigger("click");
    await flushPromises();
    expect(wrapper.text()).toContain("Молим воду.");
    expect(wrapper.text()).toContain("Воду, пожалуйста.");
    expect(wrapper.find("[data-test=hint-repair]").exists()).toBe(false);
    expect(api.createPracticeRepair.mock.calls[0][2].support).toBe("reveal");
    expect(api.getPracticeFeedback).not.toHaveBeenCalled();
    wrapper.unmount();
    api.createOrResumePractice.mockResolvedValue({ ...run, activities: [child] });
    wrapper = await load();
    expect(wrapper.text()).toContain("Молим воду.");
    expect(wrapper.find("[data-test=hint-repair]").exists()).toBe(false);
    expect(wrapper.find("textarea").exists()).toBe(true);
    wrapper.unmount();
  });

  it("retries uncertain repair issuance with the same UUID and support across refresh", async () => {
    api.submitPracticeResponse.mockResolvedValue({ ...result, outcome: "incorrect" });
    api.createPracticeRepair.mockRejectedValueOnce(new Error("response lost"));
    let wrapper = await load();
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    await wrapper.get("[data-test=hint-repair]").trigger("click");
    await flushPromises();
    const first = api.createPracticeRepair.mock.calls[0];
    expect(wrapper.find("[data-test=show-feedback]").exists()).toBe(false);
    wrapper.unmount();
    api.createOrResumePractice.mockResolvedValue({ ...run, activities: [{ ...activity, status: "completed", result: { ...result, outcome: "incorrect" } }] });
    api.createPracticeRepair.mockResolvedValue({ ...activity, id: "repair-1", retry_of: activity.id,
      support: { kind: "cue", instruction_ru: "Попросите воду.", example: null } });
    wrapper = await load();
    expect(wrapper.find("[data-test=show-feedback]").exists()).toBe(false);
    await wrapper.get("[data-test=retry-repair]").trigger("click");
    await flushPromises();
    expect(api.createPracticeRepair.mock.calls[1]).toEqual(first);
    wrapper.unmount();
  });

  it("labels transition counts by allocation period and displays its actual reset", async () => {
    const workload = { policy_version: "written-local-budget-v2", timezone: "UTC",
      window: { start: "2026-10-01T00:00:00+00:00", end: "2026-10-02T22:00:00+00:00", transition: true },
      limits: { total: 8, root: 6, new: 2, repair: 2, probe: 0 },
      issued: { total: 2, root: 2, new: 2, repair: 0, due: 0, weak: 0, assessment: 0, probe: 0 },
      remaining: { total: 6, root: 4, new: 0, repair: 2, probe: 0 } };
    api.nextPracticeActivity.mockResolvedValue({ activity: null, reason: "daily_acquire_budget_reached", workload });
    const wrapper = await load();
    expect(wrapper.text()).not.toContain("Выдано сегодня");
    expect(wrapper.text()).toContain("Выдано за период");
    expect(wrapper.text()).toContain(workload.window.end);
    expect(wrapper.text()).toContain("Лимит не сбрасывается");
    wrapper.unmount();
  });

  it("shows UTC issuance limits and creates a new run after a retired policy", async () => {
    const workload = { policy_version: "written-utc-budget-v1", timezone: "UTC",
      limits: { total: 8, root: 6, new: 2, repair: 2, probe: 0 },
      issued: { total: 2, root: 2, new: 2, repair: 0, due: 0, weak: 0, assessment: 0, probe: 0 },
      remaining: { total: 6, root: 4, new: 0, repair: 2, probe: 0 } };
    api.nextPracticeActivity.mockResolvedValue({ activity: null, reason: "policy_retired", workload });
    const wrapper = await load();
    expect(wrapper.text()).toContain("UTC");
    expect(wrapper.text()).toContain("Остаток лимита выдачи");
    expect(wrapper.text()).toContain("Версия сессии больше не выдаёт задания");
    const oldId = api.createOrResumePractice.mock.calls[0][1];
    await wrapper.get("[data-test=new-practice-run]").trigger("click");
    await flushPromises();
    expect(api.createOrResumePractice.mock.calls[1][1]).not.toBe(oldId);
    expect(wrapper.find("[data-test=start-practice]").exists()).toBe(true);
    wrapper.unmount();
  });

  it("explains exhausted total budget in Serbian", async () => {
    sessionStore.setUiLanguage("sr");
    api.nextPracticeActivity.mockResolvedValue({ activity: null, reason: "daily_workload_budget_reached" });
    const wrapper = await load();
    expect(wrapper.text()).toContain("Limit izdavanja za ovaj period je dostignut");
    wrapper.unmount();
  });

  it("does not offer repair on a retired run and recovers a definite rejected issuance", async () => {
    api.createOrResumePractice.mockResolvedValue({ ...run, policy_version: "local-written-selector-v1",
      activities: [{ ...activity, status: "completed", result }] });
    let wrapper = await load();
    expect(wrapper.find("[data-test=hint-repair]").exists()).toBe(false);
    expect(wrapper.find("[data-test=show-feedback]").exists()).toBe(false);
    wrapper.unmount();
    sessionStorage.clear();
    api.createOrResumePractice.mockResolvedValue(run);
    api.createPracticeRepair.mockRejectedValue(Object.assign(new Error("budget stale"), { status: 409 }));
    wrapper = await load();
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    await wrapper.get("[data-test=hint-repair]").trigger("click");
    await flushPromises();
    expect(wrapper.find("[data-test=retry-repair]").exists()).toBe(false);
    const persisted = JSON.parse(sessionStorage.getItem("slovnik.practice.v1.learner-1")!);
    expect(persisted.repair).toBeUndefined();
    wrapper.unmount();
  });
});
