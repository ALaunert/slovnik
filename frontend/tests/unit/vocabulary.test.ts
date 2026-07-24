import { describe, expect, it, vi } from "vitest";

import {
  AiFillApiError,
  fillVocabularyWithAi,
  listVocabulary,
  verifyEditorPassword,
} from "../../src/api/client";

describe("vocabulary API", () => {
  it("sends optional level and theme filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
    vi.stubGlobal("fetch", fetchMock);

    await listVocabulary({ cefr_level: "A1", theme: "greetings" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/api/vocabulary?cefr_level=A1&theme=greetings",
    );
  });

  it("verifies editor password before unlock", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    await verifyEditorPassword("secret");

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/vocabulary/editor/verify", {
      method: "POST",
      headers: { "X-Editor-Password": "secret" },
    });
  });

  it("requests an AI-filled word without a current id on create", async () => {
    const response = {
      status: "generated",
      source: "openai",
      payload: { serbian_latin: "raditi" },
      missing_required_fields: [],
    };
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(response),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(fillVocabularyWithAi("raditi", "secret")).resolves.toEqual(response);

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/vocabulary/ai-fill", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Editor-Password": "secret" },
      body: JSON.stringify({ source_word: "raditi" }),
    });
  });

  it("requests an AI-filled word with the current id on edit", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({
        status: "already_exists",
        word_id: 9,
        message: "Word already exists.",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await fillVocabularyWithAi("raditi", "secret", 7);

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/api/vocabulary/ai-fill", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Editor-Password": "secret" },
      body: JSON.stringify({ source_word: "raditi", current_word_id: 7 }),
    });
  });

  it("throws a typed AI fill error with the stable backend code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      json: () => Promise.resolve({
        code: "openai_timeout",
        message: "AI fill timed out.",
      }),
    }));

    const request = fillVocabularyWithAi("raditi", "secret");

    await expect(request).rejects.toBeInstanceOf(AiFillApiError);
    await expect(request).rejects.toMatchObject({
      code: "openai_timeout",
      message: "AI fill timed out.",
      status: 503,
    });
  });

  it("uses a safe fallback when the AI error body cannot be parsed", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      json: () => Promise.reject(new SyntaxError("invalid JSON")),
    }));

    await expect(fillVocabularyWithAi("raditi", "secret")).rejects.toMatchObject({
      code: "ai_fill_failed",
      message: "Failed to fill vocabulary with AI",
      status: 502,
    });
  });
});
