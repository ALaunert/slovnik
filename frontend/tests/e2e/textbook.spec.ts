import { expect, test } from "@playwright/test";
import book from "../../src/content/serbian-textbook.json";

for (const width of [1280, 390]) {
  test(`textbook reading, search and revealed answers work without a profile at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const apiRequests: string[] = [];
    await page.route((url) => url.pathname.startsWith("/api/"), async (route) => {
      apiRequests.push(route.request().url());
      await route.abort("failed");
    });
    await page.goto("/");
    await page.getByRole("link", { name: "Читать учебник без профиля", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Учебник сербского языка", exact: true })).toBeVisible();
    await expect(page.locator('[data-test=chapter-card]')).toHaveCount(book.chapters.length);
    await page.getByRole("searchbox").fill("генитив");
    await page.getByRole("link", { name: /^Генитив:/ }).click();
    await expect(page).toHaveURL(/\/textbook\/genitive$/);
    await expect(page.getByRole("heading", { name: /^Генитив:/ })).toBeVisible();
    const answer = page.locator("details [lang=sr]").first();
    await expect(answer).not.toBeVisible();
    await page.getByText("Показать образец ответа", { exact: true }).first().click();
    await expect(answer).toBeVisible();
    await page.getByRole("link", { name: /^Аккузатив:/ }).first().click();
    await expect(page).toHaveURL(/\/textbook\/accusative$/);
    await expect(page.locator("details [lang=sr]").first()).not.toBeVisible();
    await page.reload();
    await expect(page.getByRole("heading", { name: /^Аккузатив:/ })).toBeVisible();
    const dimensions = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client);
    expect(apiRequests).toEqual([]);
  });
}

test("search accepts Serbian diacritics and provides empty-result recovery", async ({ page }) => {
  await page.goto("/textbook");
  await page.getByRole("searchbox").fill("pisem");
  await expect(page.getByRole("link", { name: /^Настоящее время/ })).toBeVisible();
  await page.getByRole("searchbox").fill("несуществующая тема ххх");
  await expect(page.getByRole("heading", { name: "Темы не найдены", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Сбросить поиск", exact: true }).click();
  await expect(page.locator('[data-test=chapter-card]')).toHaveCount(book.chapters.length);
});

test("missing chapter links back to the book and Serbian controls preserve Russian explanations", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("slovnik.uiLanguage", "sr"));
  await page.goto("/textbook/unknown-chapter");
  await expect(page.getByRole("heading", { name: "Tema nije pronađena", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "← Na sadržaj", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Udžbenik srpskog jezika", exact: true })).toBeVisible();
  await page.getByRole("link", { name: /^Личные местоимения и biti/ }).click();
  await expect(page.getByRole("heading", { name: /^Личные местоимения и biti/ })).toBeVisible();
  await expect(page.getByText("Prikaži primer odgovora", { exact: true }).first()).toBeVisible();
});

for (const width of [1280, 390]) {
  test(`long chapters, table scrolling and anchored contents at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/textbook");
    await page.getByRole("navigation", { name: "Разделы учебника", exact: true })
      .getByRole("link", { name: /^Глаголы/ }).click();
    await expect(page).toHaveURL(/#group-verbs$/);
    await expect(page.getByRole("heading", { name: "Глаголы", exact: true })).toBeInViewport();
    const belowHeader = async (selector: string) => page.evaluate((target) => {
      const heading = document.querySelector(target)!;
      const header = document.querySelector(".app-header")!;
      return heading.getBoundingClientRect().top - header.getBoundingClientRect().bottom;
    }, selector);
    await expect.poll(() => belowHeader("#group-verbs h2")).toBeGreaterThanOrEqual(0);
    await page.getByRole("searchbox").fill("пишем");
    await expect(page.getByRole("link", { name: /^Настоящее время/ })).toBeVisible();
    await page.goto("/textbook/alphabet");
    const contents = page.getByRole("navigation", { name: "В этой главе", exact: true });
    await contents.getByRole("link", { name: "Проверьте себя", exact: true }).click();
    await expect(page).toHaveURL(/#self-check$/);
    await expect(page.getByRole("heading", { name: "Проверьте себя", exact: true })).toBeInViewport();
    await expect.poll(() => belowHeader("#self-check h2")).toBeGreaterThanOrEqual(0);
    await page.reload();
    await expect(page.getByRole("heading", { name: "Проверьте себя", exact: true })).toBeInViewport();
    await expect.poll(() => belowHeader("#self-check h2")).toBeGreaterThanOrEqual(0);
    // The widest real paradigm exercises the same reader with authored content.
    const widest = [...book.chapters].sort((a, b) =>
      Math.max(...b.sections.map((s) => s.table?.headers.length ?? 0)) -
      Math.max(...a.sections.map((s) => s.table?.headers.length ?? 0)))[0]!;
    await page.goto(`/textbook/${widest.id}`);
    const regions = page.locator(".table-scroll");
    const widestRegion = await regions.evaluateAll((elements) => elements
      .map((element, index) => ({ index, overflow: element.scrollWidth - element.clientWidth }))
      .sort((a, b) => b.overflow - a.overflow)[0]!);
    const region = regions.nth(widestRegion.index);
    await region.scrollIntoViewIfNeeded();
    await region.focus();
    if (width === 390) {
      expect(widestRegion.overflow).toBeGreaterThan(0);
      await page.keyboard.press("ArrowRight");
      await expect.poll(() => region.evaluate((element) => element.scrollLeft)).toBeGreaterThan(0);
    }
    const sizes = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    expect(sizes.scroll).toBeLessThanOrEqual(sizes.client);
  });
}
