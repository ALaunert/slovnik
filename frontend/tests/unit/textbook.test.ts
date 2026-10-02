import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createMemoryHistory, createRouter } from "vue-router";
import AppShell from "../../src/components/AppShell.vue";
import { router as appRouter } from "../../src/router";
import { sessionStore } from "../../src/stores/session";
import { matchesChapter, textbook, type TextbookChapter } from "../../src/content/textbook";

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
    // These routes were published in edition 1 and must remain addressable.
    expect(ids).toEqual(expect.arrayContaining([
      "alphabet", "biti", "gender-plural", "adjectives-possession", "present",
      "questions-negation", "accusative", "genitive", "dative", "locative",
      "instrumental", "perfect", "future", "modals-da", "imperative", "aspect",
      "clitics", "comparisons", "conditional", "conjunctions",
    ]));
    for (const chapter of textbook.chapters) {
      expect(chapter.id).toMatch(/^[a-z]+(?:-[a-z]+)*$/);
      expect(textbook.groups.some((group) => group.id === chapter.group_id)).toBe(true);
      expect(chapter.sections.flatMap((section) => section.paragraphs).length).toBeGreaterThanOrEqual(2);
      expect(chapter.examples.length).toBeGreaterThanOrEqual(2);
      expect(chapter.practice.length).toBeGreaterThan(0);
      expect(chapter.source_refs.length).toBeGreaterThan(0);
      for (const exercise of chapter.practice) expect(["ru", "sr"]).toContain(exercise.answer_language ?? "sr");
      for (const related of chapter.related) expect(ids).toContain(related);
      for (const ref of chapter.source_refs) {
        const source = textbook.sources.find((item) => item.id === ref.source_id);
        expect(source?.url).toMatch(/^https?:\/\//);
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
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBe(textbook.chapters.length);
    await wrapper.get('input[type="search"]').setValue("генитив");
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBeGreaterThan(0);
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBeLessThan(textbook.chapters.length);
    expect(wrapper.text()).toContain("Генитив");
    await wrapper.get('input[type="search"]').setValue("несуществующая тема ххх");
    expect(wrapper.text()).toContain("Темы не найдены");
    await wrapper.get('[data-test=clear-search]').trigger('click');
    expect(wrapper.findAll("[data-test=chapter-card]").length).toBe(textbook.chapters.length);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("renders a direct chapter with explanations, sources and concealed sample answers", async () => {
    ({ wrapper } = await reader("/textbook/accusative"));
    expect(wrapper.get("main h1").text()).toContain("Аккузатив");
    expect(wrapper.findAll(".lesson-section").length).toBeGreaterThanOrEqual(2);
    expect(wrapper.findAll('[lang="sr"]').length).toBeGreaterThanOrEqual(2);
    expect(wrapper.find(".lesson-sources a").attributes("href")).toMatch(/^https?:\/\//);
    expect(wrapper.get("details").attributes("open")).toBeUndefined();
    expect(wrapper.get("details summary").text()).toBe("Показать образец ответа");
    expect(fetch).not.toHaveBeenCalled();
  });

  it("finds Serbian words across scripts and includes notes, table headings and self-checks", () => {
    const chapter: TextbookChapter = {
      ...textbook.chapters[0]!,
      sections: [{ title: "Формы", paragraphs: ["Описание"], table: { headers: ["Локатив"], rows: [["kući"]] } }],
      examples: [{ serbian: "Љубичаста торба.", translation: "Фиолетовая сумка.", note: "konjugacija, dođi" }],
      practice: [{ prompt: "Перепишите njena", answer: "њена", explanation: "Сохраняйте диакритику" }],
    };
    expect(matchesChapter(chapter, "ljubičasta")).toBe(true);
    expect(matchesChapter(chapter, "кући")).toBe(true);
    expect(matchesChapter(chapter, "локатив")).toBe(true);
    expect(matchesChapter(chapter, "konjugacija")).toBe(true);
    expect(matchesChapter(chapter, "dodi")).toBe(true);
    expect(matchesChapter(chapter, "dodji")).toBe(true);
    expect(matchesChapter(chapter, "дођи")).toBe(true);
    expect(matchesChapter(chapter, "njena диакритику")).toBe(true);
    expect(matchesChapter(chapter, "njena отсутствующее")).toBe(false);
  });

  it("links the directory sections and hides empty groups during search", async () => {
    ({ wrapper } = await reader());
    const contents = wrapper.get('nav[aria-label="Разделы учебника"]');
    expect(contents.findAll("a")).toHaveLength(textbook.groups.length);
    for (const link of contents.findAll("a")) {
      const hash = link.attributes("href")?.split("#")[1];
      expect(wrapper.find(`[id="${hash}"]`).exists()).toBe(true);
    }
    await wrapper.get('input[type="search"]').setValue("несуществующая тема ххх");
    expect(wrapper.find('nav[aria-label="Разделы учебника"]').exists()).toBe(false);
  });

  it("marks Russian explanations and Serbian sample answers in their own languages", async () => {
    const result = await reader("/textbook/dictionary-notation");
    wrapper = result.wrapper;
    expect(wrapper.get("details p").attributes("lang")).toBe("ru");
    await result.router.push("/textbook/alphabet");
    await flushPromises();
    expect(wrapper.findAll("details p[lang=sr]")).toHaveLength(3);
  });

  it("links the chapter contents to rendered sections and resets answers on chapter changes", async () => {
    const result = await reader("/textbook/accusative");
    wrapper = result.wrapper;
    const contents = wrapper.get('nav[aria-label="В этой главе"]');
    for (const link of contents.findAll("a")) {
      const hash = link.attributes("href")?.split("#")[1];
      expect(hash).toBeTruthy();
      expect(wrapper.find(`[id="${hash}"]`).exists()).toBe(true);
    }
    (wrapper.get("details").element as HTMLDetailsElement).open = true;
    await result.router.push("/textbook/genitive");
    await flushPromises();
    expect(wrapper.get("details").attributes("open")).toBeUndefined();
  });

  it("offers the directory for a nonexistent chapter instead of silently rendering another topic", async () => {
    ({ wrapper } = await reader("/textbook/no-such-topic"));
    expect(wrapper.text()).toContain("Тема не найдена");
    expect(wrapper.get('main a[href="/textbook"]').text()).toContain("оглавлению");
  });
});
