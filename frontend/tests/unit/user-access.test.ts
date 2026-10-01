import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import UserAccessView from "../../src/views/UserAccessView.vue";
import { sessionStore } from "../../src/stores/session";

vi.mock("../../src/api/client", () => ({
  createOrLoadProfile: async (userId: string) => ({ user_id: userId, ui_language: "ru" }),
}));

describe("profile entry return destination", () => {
  beforeEach(() => sessionStore.clearUserId());

  it.each([
    ["/?next=practice", "/practice"],
    ["/", "/dashboard"],
    ["/?next=https://example.com", "/dashboard"],
    ["/?next=//example.com", "/dashboard"],
    ["/?next=practice&next=other", "/dashboard"],
  ])("returns from %s to %s after choosing a profile", async (entry, destination) => {
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: "/", component: UserAccessView },
      { path: "/dashboard", component: { template: "<p>dashboard</p>" } },
      { path: "/practice", component: { template: "<p>practice</p>" } },
      { path: "/textbook", component: { template: "<p>textbook</p>" } },
    ] });
    await router.push(entry);
    const wrapper = mount(UserAccessView, { global: { plugins: [router] } });
    await wrapper.get('input[name="user_id"]').setValue("profile-reader");
    await wrapper.get("form").trigger("submit");
    await flushPromises();
    expect(router.currentRoute.value.path).toBe(destination);
    expect(sessionStore.userId.value).toBe("profile-reader");
    wrapper.unmount();
  });
});
