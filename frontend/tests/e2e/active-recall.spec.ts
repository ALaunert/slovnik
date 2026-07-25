import { expect, type Page, test } from "@playwright/test";

const firstWord = {
  id: 41,
  serbian_cyrillic: "хвала",
  serbian_latin: "hvala",
  russian_translation: "спасибо",
  cefr_level: "A1",
  theme: "общение",
  stress_marker: "хва́ла",
  meaning_notes: "Форма благодарности",
  example_sentences: "Хвала лепо.",
  example_translations: "Большое спасибо.",
  incorrect_count: 2,
  is_weak: true,
};

const secondWord = {
  id: 42,
  serbian_cyrillic: "вода",
  serbian_latin: "voda",
  russian_translation: "вода",
  cefr_level: "A1",
  theme: "еда",
  incorrect_count: 0,
  is_weak: false,
};

async function expectNoHorizontalOverflow(page: Page) {
  const width = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.client);
}

async function runActiveRecallFlow(page: Page) {
  let releaseQueue!: () => void;
  let releaseFirstAnswer!: () => void;
  const queueGate = new Promise<void>((resolve) => {
    releaseQueue = resolve;
  });
  const firstAnswerGate = new Promise<void>((resolve) => {
    releaseFirstAnswer = resolve;
  });
  const submittedPayloads: Array<{ word_id: number; rating: string }> = [];

  await page.addInitScript(() => {
    window.localStorage.setItem("slovnik.userId", "recall-learner");
    window.localStorage.setItem("slovnik.uiLanguage", "ru");
  });
  await page.route("**/api/learning/recall-learner/review", async (route) => {
    await queueGate;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ words: [firstWord, secondWord] }),
    });
  });
  await page.route("**/api/learning/recall-learner/review/answers", async (route) => {
    const payload = route.request().postDataJSON() as { word_id: number; rating: string };
    submittedPayloads.push(payload);
    if (submittedPayloads.length === 1) await firstAnswerGate;
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        progress: {
          id: payload.word_id,
          user_id: "recall-learner",
          word_id: payload.word_id,
          status: "reviewing",
          correct_count: 0,
          incorrect_count: payload.word_id === firstWord.id ? firstWord.incorrect_count : 0,
          is_weak: payload.rating === "again",
          next_review_at:
            payload.rating === "again"
              ? "2026-07-25T12:10:00Z"
              : "2026-07-27T12:00:00Z",
          review_interval_days: payload.rating === "again" ? 0 : 2,
          review_streak: payload.rating === "again" ? 0 : 1,
        },
      }),
    });
  });

  await page.goto("/review");
  await expect(page.getByRole("status").filter({ hasText: "Загрузка" })).toBeVisible();
  await expect(page.getByText("На сегодня слов для повторения нет.")).toHaveCount(0);
  releaseQueue();

  await expect(page.getByRole("heading", { name: "спасибо" })).toBeVisible();
  await expect(page.getByText("хвала", { exact: true })).toHaveCount(0);
  await expect(page.getByText("hvala", { exact: true })).toHaveCount(0);
  await expect(page.getByText("хва́ла", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Форма благодарности", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Хвала лепо.", { exact: true })).toHaveCount(0);
  await expect(page.getByText("Большое спасибо.", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Показать ответ" }).click();

  const answerRegion = page.getByRole("region", { name: "Ответ" });
  await expect(answerRegion).toBeFocused();
  await expect(page.getByText("хвала", { exact: true })).toBeVisible();
  await expect(page.getByText("hvala", { exact: true })).toBeVisible();
  await expect(page.getByText("Подробности", { exact: true })).toBeVisible();
  await page.getByText("Подробности", { exact: true }).click();
  await expect(page.getByText("Форма благодарности", { exact: true })).toBeVisible();
  for (const rating of [
    "Не вспомнил",
    "Вспомнил с трудом",
    "Вспомнил",
    "Легко вспомнил",
  ]) {
    await expect(page.getByRole("button", { name: rating, exact: true })).toBeVisible();
  }

  await page.getByRole("button", { name: "Вспомнил", exact: true }).click();
  await expect.poll(() => submittedPayloads).toEqual([{ word_id: 41, rating: "good" }]);
  await expect(page.getByText("Сохраняем...", { exact: true })).toBeVisible();
  await expect(answerRegion).toBeVisible();
  await expect(page.getByRole("heading", { name: "хвала / hvala" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "вода" })).toHaveCount(0);
  releaseFirstAnswer();

  await expect(page.getByRole("heading", { name: "вода" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Показать ответ" })).toBeFocused();

  await page.getByRole("button", { name: "Показать ответ" }).click();
  await page.getByRole("button", { name: "Не вспомнил", exact: true }).click();

  await expect.poll(() => submittedPayloads).toEqual([
    { word_id: 41, rating: "good" },
    { word_id: 42, rating: "again" },
  ]);
  const completion = page.getByRole("status").filter({ hasText: "Повторение завершено" });
  await expect(completion).toBeVisible();
  await expect(completion).toBeFocused();
}

for (const viewport of [
  { name: "desktop", width: 1280, height: 900 },
  { name: "mobile", width: 390, height: 844 },
]) {
  test(`active recall saves before advancing on ${viewport.name}`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await runActiveRecallFlow(page);
    await expectNoHorizontalOverflow(page);
  });
}

test("max-length unbroken review content does not overflow on mobile", async ({ page }) => {
  const longWord = {
    id: 99,
    serbian_cyrillic: "ђ".repeat(160),
    serbian_latin: "d".repeat(160),
    russian_translation: "д".repeat(240),
    cefr_level: "A1",
    theme: "т".repeat(80),
    usage_register: "р".repeat(80),
    stress_marker: "с".repeat(160),
    meaning_notes: "н".repeat(240),
    incorrect_count: 0,
    is_weak: false,
  };

  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    window.localStorage.setItem("slovnik.userId", "overflow-learner");
    window.localStorage.setItem("slovnik.uiLanguage", "ru");
  });
  await page.route("**/api/learning/overflow-learner/review", (route) =>
    route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ words: [longWord] }),
    }),
  );

  await page.goto("/review");
  await expect(page.getByRole("heading", { name: longWord.russian_translation })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.getByRole("button", { name: "Показать ответ" }).click();
  await expect(page.getByRole("region", { name: "Ответ" })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await expect(page.getByRole("group", { name: /Оцените/ })).toBeVisible();
  await expect(page.getByRole("button", { name: "Легко вспомнил", exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);
});
