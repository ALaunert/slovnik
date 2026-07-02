import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";

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
import DashboardView from "../../src/views/DashboardView.vue";
import { sessionStore } from "../../src/stores/session";

describe("DashboardView", () => {
  it("sends updated profile settings", async () => {
    sessionStore.setUserId("learner-1");
    const wrapper = mount(DashboardView, {
      global: {
        stubs: { RouterLink: true },
      },
    });
    await Promise.resolve();
    await Promise.resolve();

    await wrapper.get('select[name="preferred_level"]').setValue("A2");
    await wrapper.get('input[name="daily_new_word_count"]').setValue(7);
    await wrapper.get('select[name="ui_language"]').setValue("sr");
    await wrapper.get('form').trigger("submit.prevent");

    expect(updateProfile).toHaveBeenCalledWith("learner-1", {
      preferred_level: "A2",
      daily_new_word_count: 7,
      ui_language: "sr",
    });
  });
});
