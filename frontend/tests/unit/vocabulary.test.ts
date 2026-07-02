import { describe, expect, it, vi } from "vitest";

import { listVocabulary } from "../../src/api/client";

describe("vocabulary API", () => {
  it("sends optional level and theme filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    vi.stubGlobal("fetch", fetchMock);

    await listVocabulary({ cefr_level: "A1", theme: "greetings" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/vocabulary?cefr_level=A1&theme=greetings",
    );
  });
});
