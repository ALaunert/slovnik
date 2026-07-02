import { expect, test } from "@playwright/test";

test("user can reach dashboard from user id entry", async ({ page }) => {
  await page.route("**/api/profiles", async (route) => {
    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({
        user_id: "learner-1",
        preferred_level: "A1",
        daily_new_word_count: 5,
        ui_language: "ru",
      }),
    });
  });

  await page.goto("/");
  await page.getByLabel("User ID").fill("learner-1");
  await page.getByRole("button", { name: /start|начать/i }).click();
  await expect(page.getByText("Сегодня").first()).toBeVisible();
});
