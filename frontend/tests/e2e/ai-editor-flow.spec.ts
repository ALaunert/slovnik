import { expect, type Page, test } from "@playwright/test";

const completePayload = {
  serbian_cyrillic: "радити",
  serbian_latin: "raditi",
  russian_translation: "делать",
  cefr_level: "A1",
  theme: "work",
  stress_pattern: {
    cyrillic_syllables: ["ра", "ди", "ти"],
    latin_syllables: ["ra", "di", "ti"],
    stressed_syllable_index: 1,
  },
};

async function runEditorFlow(page: Page) {
  let savedPayload: Record<string, unknown> | null = null;

  await page.addInitScript(() => {
    window.localStorage.setItem("slovnik.uiLanguage", "ru");
  });
  await page.route("**/api/vocabulary/editor/verify", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: '{"ok":true}' }),
  );
  await page.route("**/api/vocabulary/ai-fill", async (route) => {
    const request = route.request().postDataJSON() as { source_word: string };
    if (request.source_word === "timeout") {
      await route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({ code: "openai_timeout", message: "AI fill timed out." }),
      });
      return;
    }
    if (request.source_word === "postojati") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          status: "already_exists",
          word_id: 7,
          message: "Word already exists.",
        }),
      });
      return;
    }
    if (request.source_word === "pisati") {
      await route.fulfill({
        contentType: "application/json",
        body: JSON.stringify({
          status: "generated",
          source: "openai",
          payload: {
            serbian_latin: "pisati",
            russian_translation: "писать",
          },
          missing_required_fields: ["serbian_cyrillic", "cefr_level", "theme"],
        }),
      });
      return;
    }
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        status: "generated",
        source: request.source_word === "uciti" ? "store" : "openai",
        payload: completePayload,
        missing_required_fields: [],
      }),
    });
  });
  await page.route(/\/api\/vocabulary$/, async (route) => {
    savedPayload = route.request().postDataJSON() as Record<string, unknown>;
    await route.fulfill({
      status: 201,
      contentType: "application/json",
      body: JSON.stringify({ id: 42, ...savedPayload }),
    });
  });

  await page.goto("/editor");
  await expect(page.getByTestId("ai-fill")).toHaveCount(0);
  await page.getByLabel("Пароль редактора").fill("test-password");
  await page.getByRole("button", { name: "Открыть редактирование" }).click();
  await expect(page.getByTestId("ai-fill")).toBeVisible();

  const aiInput = page.getByLabel("Одно сербское слово");
  await aiInput.fill("raditi");
  await page.getByTestId("ai-fill-button").click();
  await expect(page.getByRole("status")).toContainText("OpenAI");
  await expect(page.getByLabel("Сербская кириллица")).toHaveValue("радити");
  await expect(page.getByLabel("Сербская латиница")).toHaveValue("raditi");
  await expect(page.locator(".stress-preview strong")).toHaveText(["ди", "di"]);

  await page.getByRole("button", { name: "Сохранить" }).click();
  await expect(page.getByText("Слово сохранено")).toBeVisible();
  expect(savedPayload).toMatchObject({
    serbian_cyrillic: "радити",
    serbian_latin: "raditi",
    stress_pattern: completePayload.stress_pattern,
  });

  await page.getByTestId("ai-restore").click();
  await expect(page.getByLabel("Сербская кириллица")).toHaveValue("");
  await expect(page.getByLabel("Сербская латиница")).toHaveValue("");

  await aiInput.fill("pisati");
  await page.getByTestId("ai-fill-button").click();
  await expect(page.locator("[data-missing-field]")).toHaveCount(2);
  await expect(page.locator('[data-missing-field="serbian_cyrillic"]')).toBeVisible();
  await expect(page.locator('[data-missing-field="theme"]')).toBeVisible();
  await page.getByLabel("Сербская кириллица").fill("писати");
  await page.getByLabel("Тема").fill("work");
  await expect(page.locator("[data-missing-field]")).toHaveCount(0);

  await aiInput.fill("timeout");
  await page.getByTestId("ai-fill-button").click();
  await expect(page.getByRole("alert")).toContainText("не ответил вовремя");
  await expect(page.getByLabel("Сербская латиница")).toHaveValue("pisati");
  await expect(page.getByTestId("ai-restore")).toBeVisible();
  await page.getByTestId("dismiss-ai-error").click();

  await aiInput.fill("postojati");
  await page.getByTestId("ai-fill-button").click();
  await expect(page.getByTestId("existing-word-link")).toHaveAttribute("href", "/editor/7");
  await expect(page.getByLabel("Сербская латиница")).toHaveValue("pisati");

  await aiInput.fill("uciti");
  await page.getByTestId("ai-fill-button").click();
  await expect(page.getByRole("status")).toContainText("ранее сохраненный результат");
  const pageWidth = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(pageWidth.scroll).toBeLessThanOrEqual(pageWidth.client);
}

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test(`AI editor flow is usable on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await runEditorFlow(page);
  });
}
