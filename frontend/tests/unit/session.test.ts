import { describe, expect, it } from "vitest";
import { createSessionStore } from "../../src/stores/session";

describe("session store", () => {
  it("persists the last user id", () => {
    const storage = new Map<string, string>();
    const store = createSessionStore({
      getItem: (key) => storage.get(key) ?? null,
      setItem: (key, value) => storage.set(key, value),
      removeItem: (key) => storage.delete(key),
    });

    store.setUserId("learner-1");

    expect(storage.get("slovnik.userId")).toBe("learner-1");
    expect(store.userId.value).toBe("learner-1");
  });
});
