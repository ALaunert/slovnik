import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import AppShell from "../../src/components/AppShell.vue";
import { router as appRouter } from "../../src/router";
import { sessionStore } from "../../src/stores/session";
import { textbook } from "../../src/content/textbook";

async function reader(path = "/textbook") {
  const router = createRouter({ history: createMemoryHistory(), routes: appRouter.options.routes });
  await router.push(path);
  const wrapper = mount(AppShell, { global: { plugins: [router] } });
  await flushPromises();
  return { wrapper, router };
}

let wrapper: VueWrapper | undefined;

describe("grammar textbook reading without a profile", () => {
  beforeEach(() => {
    sessionStore.clearUserId();
    sessionStore.setUiLanguage("ru");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("backend offline")));
  });
  afterEach(() => { wrapper?.unmount(); wrapper = undefined; vi.unstubAllGlobals(); });

  it("keeps every published topic, table and reading reference navigable", () => {
    const ids = textbook.chapters.map((chapter) => chapter.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const chapter of textbook.chapters) {
      expect(chapter.id).toMatch(/^[a-z]+(?:-[a-z]+)*$/);
      expect(textbook.groups.some((group) => group.id === chapter.group_id)).toBe(true);
      expect(chapter.sections.flatMap((section) => section.paragraphs).length).toBeGreaterThanOrEqual(2);
      expect(chapter.examples.length).toBeGreaterThanOrEqual(2);
      expect(chapter.practice.length).toBeGreaterThan(0);
      expect(chapter.source_refs.length).toBeGreaterThan(0);
      for (const related of chapter.related) expect(ids).toContain(related);
      for (const ref of chapter.source_refs) {
        const source = textbook.sources.find((item) => item.id === ref.source_id);
        expect(source?.url).toMatch(/^https:\/\//);
        expect(ref.locator.trim()).not.toBe("");
      }
      for (const section of chapter.sections) {
        for (const row of section.table?.rows ?? []) expect(row).toHaveLength(section.table!.headers.length);
      }
    }
  });

  it("exposes a grouped grammar directory and filters topics without requiring the backend", async () => {
    ({ wrapper } = await reader());
    expect(wrapper.get("main h1").text()).toBe("Учебник сербского языка");
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBeGreaterThanOrEqual(18);
    await wrapper.get('input[type="search"]').setValue("генитив");
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBeGreaterThan(0);
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBeLessThan(18);
    expect(wrapper.text()).toContain("Генитив");
    await wrapper.get('input[type="search"]').setValue("несуществующая тема ххх");
    expect(wrapper.text()).toContain("Темы не найдены");
    await wrapper.get('[data-test=clear-search]').trigger('click');
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBeGreaterThanOrEqual(18);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("renders a direct chapter with explanations, sources and concealed sample answers", async () => {
    ({ wrapper } = await reader("/textbook/accusative"));
    expect(wrapper.get("main h1").text()).toContain("Аккузатив");
    expect(wrapper.findAll(".lesson-section").length).toBeGreaterThanOrEqual(2);
    expect(wrapper.findAll('[lang="sr"]').length).toBeGreaterThanOrEqual(2);
    expect(wrapper.find(".lesson-sources a").attributes("href")).toMatch(/^https:\/\//);
    expect(wrapper.get("details").attributes("open")).toBeUndefined();
    expect(wrapper.get("details summary").text()).toBe("Показать образец ответа");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("offers the directory for a nonexistent chapter instead of silently rendering another topic", async () => {
    ({ wrapper } = await reader("/textbook/no-such-topic"));
    expect(wrapper.text()).toContain("Тема не найдена");
    expect(wrapper.get('main a[href="/textbook"]').text()).toContain("оглавлению");
  });
});
