import { mount, RouterLinkStub } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../../src/api/client", () => ({
  createOrLoadProfile: vi.fn().mockResolvedValue({
    user_id: "learner-1",
    preferred_level: "A1",
    daily_new_word_count: 5,
    ui_language: "ru",
  }),
  updateProfile: vi.fn().mockResolvedValue({
    user_id: "learner-1",
    preferred_level: "A2",
    daily_new_word_count: 7,
    ui_language: "sr",
  }),
}));

import { updateProfile } from "../../src/api/client";
import { sessionStore } from "../../src/stores/session";
import DashboardView from "../../src/views/DashboardView.vue";

async function flushPromises() {
  await Promise.resolve();
  await Promise.resolve();
}

describe("DashboardView", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    sessionStore.setUserId("learner-1");
    sessionStore.setUiLanguage("ru");
  });

  it("sends updated profile settings", async () => {
    const wrapper = mount(DashboardView, {
      global: {
        stubs: { RouterLink: RouterLinkStub },
      },
    });
    await flushPromises();

    await wrapper.get('select[name="preferred_level"]').setValue("A2");
    await wrapper.get('input[name="daily_new_word_count"]').setValue(7);
    await wrapper.get('select[name="ui_language"]').setValue("sr");
    await wrapper.get("form").trigger("submit.prevent");

    expect(updateProfile).toHaveBeenCalledWith("learner-1", {
      preferred_level: "A2",
      daily_new_word_count: 7,
      ui_language: "sr",
    });
  });

  it("renders Serbian route copy after the saved profile selects Serbian", async () => {
    const wrapper = mount(DashboardView, {
      global: {
        stubs: { RouterLink: RouterLinkStub },
      },
    });
    await flushPromises();

    await wrapper.get('select[name="ui_language"]').setValue("sr");
    await wrapper.get("form").trigger("submit.prevent");
    await flushPromises();

    expect(wrapper.text()).toContain("Danas");
    expect(wrapper.text()).toContain("Nove reči");
    expect(wrapper.text()).toContain("Podešavanja");
  });
});
