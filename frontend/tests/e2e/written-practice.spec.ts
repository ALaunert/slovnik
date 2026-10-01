import { expect, test } from "@playwright/test";

for (const viewport of [{ width: 1280, height: 800 }, { width: 390, height: 844 }]) {
  test(`written practice resumes a frozen answer after network failure at ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await page.addInitScript(() => {
      localStorage.setItem("slovnik.userId", "written-test");
      localStorage.setItem("slovnik.uiLanguage", "ru");
    });
    const activity = {
      id: "activity-1", kind: "exercise", operation: "transform", cue_level: "full",
      status: "pending", sequence_number: 1, capability: "apply_construction",
      context_family: "request-practice", task: {
        input: "Вода доступна; сок закончился.", instruction_ru: "Попросите воду.", format: "sentence",
      }, response_contract: { kind: "text", max_codepoints: 2000 }, presentation: null,
      selection_reasons: ["new_target"], result: null as unknown,
    };
    const attempts: Array<{ idempotency_key: string; response: string }> = [];
    let issued = false;
    let accepted = false;
    const result = { event_id: "event-1", outcome: "unresolved", first_response: "Можно воду?" };
    const workload = { policy_version: "written-utc-budget-v1", timezone: "UTC",
      limits: { total: 8, root: 6, new: 2, repair: 2, probe: 0 },
      issued: { total: 2, root: 2, new: 2, repair: 0, due: 0, weak: 0, assessment: 0, probe: 0 },
      remaining: { total: 6, root: 4, new: 0, repair: 2, probe: 0 } };
    await page.route("**/api/practice/**", async (route) => {
      const url = route.request().url();
      let body: unknown;
      if (url.endsWith("/availability")) body = { schema_version: 1, enabled: true };
      else if (url.endsWith("/next")) {
        body = accepted ? { activity: null, reason: "daily_acquire_budget_reached", workload } : { activity, reason: null, workload };
        issued = true;
      } else if (url.endsWith("/responses")) {
        attempts.push(route.request().postDataJSON());
        if (attempts.length === 1) { await route.abort("failed"); return; }
        accepted = true;
        activity.status = "completed";
        activity.result = result;
        body = result;
      } else body = {
        schema_version: 1, id: url.split("/").at(-1), status: "active",
        policy_version: "local-written-selector-v2", activities: issued ? [activity] : [],
        workload,
      };
      await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
    });

    await page.goto("/practice");
    await page.getByRole("button", { name: "Начать практику", exact: true }).click();
    await expect(page.getByText("Попросите воду.", { exact: true })).toBeVisible();
    await expect(page.getByText("Молим воду.", { exact: true })).toHaveCount(0);
    await page.getByLabel("Ответ", { exact: true }).fill("Можно воду?");
    await page.getByLabel("Ответ", { exact: true }).press("Tab");
    await page.keyboard.press("Enter");
    await expect(page.getByRole("button", { name: "Повторить отправку" })).toBeVisible();
    await page.reload();
    await page.getByRole("button", { name: "Повторить отправку" }).click();
    await expect(page.getByRole("heading", { name: "Ответ сохранён без однозначной оценки" })).toBeVisible();
    expect(attempts).toHaveLength(2);
    expect(attempts[1]).toEqual(attempts[0]);
    await page.reload();
    await expect(page.getByText("Можно воду?", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Дальше", exact: true }).click();
    await expect(page.getByRole("heading", { name: "Нет подходящего задания" })).toBeVisible();
    await expect(page.getByText("Лимит новых задач за период достигнут.", { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: "Новая сессия", exact: true })).toBeVisible();
    const width = await page.evaluate(() => ({ client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth }));
    expect(width.scroll).toBeLessThanOrEqual(width.client);
    await page.getByRole("button", { name: "Остановиться и вернуться позже" }).click();
    await expect(page).toHaveURL(/\/dashboard$/);
  });
}

test("revealed repair keeps the first result through reload", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("slovnik.userId", "written-test");
    localStorage.setItem("slovnik.uiLanguage", "ru");
  });
  const parent = {
    id: "parent", kind: "exercise", operation: "transform", status: "completed", sequence_number: 1,
    selection_reasons: ["new_target"],
    task: { input: "Вода доступна.", instruction_ru: "Попросите воду.", format: "sentence" },
    response_contract: { kind: "text", max_codepoints: 2000 },
    result: { outcome: "incorrect", first_response: "", evidence_kind: "first_answer" },
  };
  let child: Record<string, unknown> | null = null;
  await page.route("**/api/practice/**", async (route) => {
    const url = route.request().url();
    let body: unknown;
    if (url.endsWith("/availability")) body = { enabled: true };
    else if (url.endsWith("/repair")) {
      const request = route.request().postDataJSON();
      expect(request.support).toBe("reveal");
      child = { ...parent, id: request.retry_id, retry_of: parent.id, status: "pending", result: null,
        support: { kind: "reveal", instruction_ru: "Попросите воду.",
          example: { serbian: "Молим воду.", translation: "Воду, пожалуйста.", answer: "Молим воду." } } };
      body = child;
    } else if (url.endsWith("/responses")) {
      body = { outcome: "correct", first_response: "Молим воду.", evidence_kind: "repair" };
      child = { ...child, status: "completed", result: body };
    } else body = { id: "run", status: "active", policy_version: "local-written-selector-v2",
      activities: child ? [parent, child] : [parent] };
    await route.fulfill({ contentType: "application/json", body: JSON.stringify(body) });
  });
  await page.goto("/practice");
  await page.getByRole("button", { name: "Показать проверенный образец" }).click();
  await page.reload();
  await expect(page.getByText("Образец показан перед повтором", { exact: true })).toBeVisible();
  await page.getByLabel("Ответ", { exact: true }).fill("Молим воду.");
  await page.getByRole("button", { name: "Проверить", exact: true }).click();
  await expect(page.getByRole("heading", { name: "На повторе после помощи ответ принят" })).toBeVisible();
  await expect(page.getByText("В первом ответе обнаружено несоответствие заданию", { exact: true })).toBeVisible();
});
