import { expect, test } from "@playwright/test";

test("direct practice entry explains missing profile and returns after selection", async ({ page }) => {
  await page.route(/\/api\/(profiles|practice)(\/|$)/, async (route) => {
    const url = route.request().url();
    const body = url.endsWith("/availability") ? { enabled: true }
      : url.endsWith("/profiles") ? { user_id: "entry-test", ui_language: "ru" }
      : { schema_version: 1, id: url.split("/").at(-1), status: "active",
          policy_version: "local-written-selector-v2", activities: [] };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/practice");
  await expect(page.getByRole("heading", { name: "Выберите профиль для практики" })).toBeVisible();
  await expect(page.getByText("Локальная практика недоступна", { exact: true })).toHaveCount(0);
  await page.getByRole("link", { name: "Выбрать профиль и продолжить" }).click();
  await page.getByLabel("User ID", { exact: true }).fill("entry-test");
  await page.getByRole("button", { name: "Начать", exact: true }).click();
  await expect(page).toHaveURL(/\/practice$/);
  await expect(page.getByRole("button", { name: "Начать практику", exact: true })).toBeVisible();
});

test("disabled pilot stays readable and can retry after availability recovers", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("slovnik.userId", "entry-test"));
  let enabled = false;
  await page.route("**/api/practice/**", async (route) => {
    const body = route.request().url().endsWith("/availability") ? { enabled }
      : { schema_version: 1, id: route.request().url().split("/").at(-1), status: "active",
          policy_version: "local-written-selector-v2", activities: [] };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/practice");
  await expect(page.getByRole("heading", { name: "Локальная практика недоступна" })).toBeVisible();
  enabled = true;
  await page.getByRole("button", { name: "Загрузить снова", exact: true }).click();
  await expect(page.getByRole("button", { name: "Начать практику", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Локальная практика недоступна" })).toHaveCount(0);
});
