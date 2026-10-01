import { expect, test } from "@playwright/test";

for (const width of [1280, 390]) {
  test(`textbook reading, search and revealed answers work without a profile at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    const apiRequests: string[] = [];
    await page.route(/\/api\/(profiles|practice|vocabulary|learning|quizzes)(\/|$)/, async (route) => {
      apiRequests.push(route.request().url());
      await route.abort("failed");
    });
    await page.goto("/");
    await page.getByRole("link", { name: "Читать учебник без профиля", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Учебник сербского языка", exact: true })).toBeVisible();
    await expect(page.locator('[data-test=chapter-card]')).toHaveCount(20);
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
  await expect(page.locator('[data-test=chapter-card]')).toHaveCount(20);
});

test("missing chapter links back to the book and Serbian controls preserve Russian explanations", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("slovnik.uiLanguage", "sr"));
  await page.goto("/textbook/unknown-chapter");
  await expect(page.getByRole("heading", { name: "Tema nije pronađena", exact: true })).toBeVisible();
  await page.getByRole("link", { name: "← Na sadržaj", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Udžbenik srpskog jezika", exact: true })).toBeVisible();
  await page.getByRole("link", { name: /^Личные местоимения и biti/ }).click();
  await expect(page.getByRole("heading", { name: "Личные местоимения и biti", exact: true })).toBeVisible();
  await expect(page.getByText("Prikaži primer odgovora", { exact: true })).toBeVisible();
});
