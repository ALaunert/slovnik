import { mount, RouterLinkStub } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import AppShell from "../../src/components/AppShell.vue";
import { sessionStore } from "../../src/stores/session";

describe("AppShell", () => {
  it("uses Serbian navigation copy when the session language is Serbian", () => {
    sessionStore.setUiLanguage("sr");

    const wrapper = mount(AppShell, {
      global: {
        stubs: { RouterLink: RouterLinkStub, RouterView: true },
      },
    });

    expect(wrapper.text()).toContain("Srpski rečnik");
    expect(wrapper.text()).toContain("Danas");
    expect(wrapper.text()).toContain("Nove reči");
  });
});
