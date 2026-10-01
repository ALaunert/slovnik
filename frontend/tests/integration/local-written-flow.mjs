import { chromium, expect } from "@playwright/test";

const browser = await chromium.launch();
try {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  await context.addInitScript(() => {
    localStorage.setItem("slovnik.userId", "browser-pilot-test");
    localStorage.setItem("slovnik.uiLanguage", "ru");
  });
  const page = await context.newPage();
  await page.goto(`${process.env.PILOT_FRONTEND_URL}/practice`);
  await page.getByRole("button", { name: "Начать практику", exact: true }).click();
  await expect(page.locator("textarea")).toBeVisible();
  await expect(page.getByText("Лимиты включают ещё не отвеченные задания. Зона распределения: UTC")).toBeVisible();
  await expect(page.getByText("Остаток действует до (UTC):")).toBeVisible();
  // Lose one network request; all actual responses below come from the live backend.
  await page.route("**/api/practice/**/responses", async (route) => {
    await route.abort("failed");
  }, { times: 1 });
  await page.getByRole("button", { name: "Проверить", exact: true }).click();
  await expect(page.getByRole("button", { name: "Повторить отправку" })).toBeVisible();
  await page.reload();
  await page.getByRole("button", { name: "Повторить отправку" }).click();
  await expect(page.getByRole("heading", { name: "В первом ответе обнаружено несоответствие заданию" })).toBeVisible();
  const repairResponse = page.waitForResponse((response) => response.url().endsWith("/repair"));
  await page.getByRole("button", { name: "Показать проверенный образец" }).click();
  const issued = await (await repairResponse).json();
  expect(issued.support.kind).toBe("reveal");
  await page.reload();
  await expect(page.getByText("Образец показан перед повтором", { exact: true })).toBeVisible();
  await page.getByLabel("Ответ", { exact: true }).fill(issued.support.example.answer);
  await page.getByRole("button", { name: "Проверить", exact: true }).click();
  await expect(page.getByRole("heading", { name: "На повторе после помощи ответ принят" })).toBeVisible();
  await expect(page.getByText("В первом ответе обнаружено несоответствие заданию", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Остановиться и вернуться позже" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);
  await page.goto(`${process.env.PILOT_FRONTEND_URL}/practice`);
  await expect(page.getByRole("heading", { name: "На повторе после помощи ответ принят" })).toBeVisible();
  const forwarded = await context.request.get(`${process.env.PILOT_API_URL}/api/practice/availability`,
    { headers: { "X-Forwarded-For": "127.0.0.1" } });
  expect(forwarded.status()).toBe(404);
  expect((await context.request.get(`${process.env.PILOT_API_URL}/api/health`)).status()).toBe(200);
  console.log("Real loopback browser flow passed: lost request, resume, reveal/repair, stop, forwarding rejection.");
} finally {
  await browser.close();
}
