const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type PracticeResult = {
  event_id: string;
  outcome: "correct" | "incorrect" | "unresolved" | null;
  first_response: string | null;
  evidence_kind?: "first_answer" | "repair" | "supported_retry" | "exposure";
};

export type PracticeSupport = "cue" | "reveal" | "correction";
export type PracticeExample = { serbian: string; translation: string; answer: string };
export type PracticeFeedback = {
  first_result: PracticeResult; instruction_ru: string; error_tags: string[];
  example: PracticeExample; can_repair: boolean;
};

export type PracticeActivity = {
  id: string; kind: "exercise" | "exposure";
  operation: "recognize" | "retrieve" | "complete" | "transform" | null;
  cue_level: string; status: "pending" | "completed" | "cancelled";
  sequence_number: number; capability: string; context_family: string;
  task: { input: string; instruction_ru: string; format: string };
  response_contract: { kind: "text" | "choice"; max_codepoints?: number; max_options?: number; options?: string[] } | null;
  presentation: { serbian: string; translation: string } | null;
  selection_reasons: string[]; result: PracticeResult | null;
  retry_of?: string | null;
  support?: { kind: PracticeSupport; instruction_ru: string; example: PracticeExample | null } | null;
};

export type PracticeRun = {
  schema_version: 1; id: string; status: "active" | "completed" | "abandoned";
  policy_version: string; activities: PracticeActivity[];
  workload?: PracticeWorkload;
};

export type PracticeWorkload = {
  policy_version: string; timezone: string;
  window?: { start: string; end: string; timezone: string; transition: boolean; calendar_policy_version: string };
  issued: Record<"total" | "root" | "new" | "due" | "weak" | "assessment" | "repair" | "probe", number>;
  limits: Record<"total" | "root" | "new" | "repair" | "probe", number>;
  remaining: Record<"total" | "root" | "new" | "repair" | "probe", number>;
};

async function practiceRequest<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE_URL}/api/practice${path}`, {
    method, ...(body === undefined ? {} : {
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    }),
  });
  if (!response.ok) throw Object.assign(new Error(`Practice request failed: ${response.status}`), { status: response.status });
  return response.json();
}

export async function getPracticeAvailability(): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/api/practice/availability`);
  if (response.status === 404) return false;
  if (!response.ok) throw new Error("Practice availability could not be checked");
  return (await response.json()).enabled === true;
}

export function createOrResumePractice(userId: string, runId: string): Promise<PracticeRun> {
  return practiceRequest(`/${encodeURIComponent(userId)}/runs/${encodeURIComponent(runId)}`, "PUT");
}

export function getPracticeRun(userId: string, runId: string): Promise<PracticeRun> {
  return practiceRequest(`/${encodeURIComponent(userId)}/runs/${encodeURIComponent(runId)}`);
}

export function nextPracticeActivity(userId: string, runId: string, kind: "exercise" | "exposure" = "exercise"):
Promise<{ activity: PracticeActivity | null; reason: string | null; workload?: PracticeWorkload }> {
  return practiceRequest(`/${encodeURIComponent(userId)}/runs/${encodeURIComponent(runId)}/next`, "POST", { kind });
}

export function submitPracticeResponse(userId: string, activityId: string,
  body: { idempotency_key: string; response?: string }): Promise<PracticeResult> {
  return practiceRequest(`/${encodeURIComponent(userId)}/activities/${encodeURIComponent(activityId)}/responses`, "POST", body);
}

export function getPracticeFeedback(userId: string, activityId: string): Promise<PracticeFeedback> {
  return practiceRequest(`/${encodeURIComponent(userId)}/activities/${encodeURIComponent(activityId)}/feedback`);
}

export function createPracticeRepair(userId: string, activityId: string,
  body: { retry_id: string; support: PracticeSupport }): Promise<PracticeActivity> {
  return practiceRequest(`/${encodeURIComponent(userId)}/activities/${encodeURIComponent(activityId)}/repair`, "POST", body);
}

export type Profile = {
  user_id: string;
  preferred_level: string;
  daily_new_word_count: number;
  ui_language: string;
  timezone?: string;
  effective_timezone?: string;
  allocation_window?: { start: string; end: string; timezone: string; transition: boolean };
};

export async function createOrLoadProfile(userId: string): Promise<Profile> {
  const response = await fetch(`${API_BASE_URL}/api/profiles`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  if (!response.ok) throw new Error("Failed to load profile");
  return response.json();
}

export async function updateProfile(
  userId: string,
  payload: { preferred_level?: string; daily_new_word_count?: number; ui_language?: string; timezone?: string },
): Promise<Profile> {
  const response = await fetch(`${API_BASE_URL}/api/profiles/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to update profile");
  return response.json();
}


export type StressPattern = {
  cyrillic_syllables: string[];
  latin_syllables: string[];
  stressed_syllable_index: number;
};

export type VocabularyWord = {
  id: number;
  serbian_cyrillic: string;
  serbian_latin: string;
  russian_translation: string;
  cefr_level: string;
  theme: string;
  usage_register?: string | null;
  stress_marker?: string | null;
  stress_pattern?: StressPattern | null;
  meaning_notes?: string | null;
  example_sentences?: string | null;
  example_translations?: string | null;
  incorrect_count?: number;
  is_weak?: boolean;
};

export type VocabularyPayload = Omit<VocabularyWord, "id">;

export type AiFillPayload = {
  serbian_cyrillic?: string;
  serbian_latin?: string;
  russian_translation?: string;
  cefr_level?: string;
  theme?: string;
  usage_register?: string;
  stress_pattern?: StressPattern;
  meaning_notes?: string;
  example_sentences?: string;
  example_translations?: string;
};

export type AiFillGeneratedResponse = {
  status: "generated";
  source: "openai" | "store";
  payload: AiFillPayload;
  missing_required_fields: string[];
};

export type AiFillExistingResponse = {
  status: "already_exists";
  word_id: number;
  message: string;
};

export type AiFillResponse = AiFillGeneratedResponse | AiFillExistingResponse;

export class AiFillApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly status: number,
  ) {
    super(message);
    this.name = "AiFillApiError";
  }
}

function parseAiFillErrorBody(body: unknown): { code: string; message: string } | null {
  if (typeof body !== "object" || body === null) return null;
  const candidate = body as Record<string, unknown>;
  if (typeof candidate.code !== "string" || typeof candidate.message !== "string") return null;
  return { code: candidate.code, message: candidate.message };
}

export async function fillVocabularyWithAi(
  sourceWord: string,
  editorPassword: string,
  currentWordId?: number,
): Promise<AiFillResponse> {
  const body: { source_word: string; current_word_id?: number } = { source_word: sourceWord };
  if (currentWordId !== undefined) body.current_word_id = currentWordId;

  const response = await fetch(`${API_BASE_URL}/api/vocabulary/ai-fill`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Editor-Password": editorPassword },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const parsedBody = await response.json().catch(() => null);
    const errorBody = parseAiFillErrorBody(parsedBody);
    throw new AiFillApiError(
      errorBody?.code ?? "ai_fill_failed",
      errorBody?.message ?? "Failed to fill vocabulary with AI",
      response.status,
    );
  }
  return response.json();
}

export async function listVocabulary(filters: { cefr_level?: string; theme?: string } = {}): Promise<VocabularyWord[]> {
  const params = new URLSearchParams();
  if (filters.cefr_level) params.set("cefr_level", filters.cefr_level);
  if (filters.theme) params.set("theme", filters.theme);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/api/vocabulary${suffix}`);
  if (!response.ok) throw new Error("Failed to load vocabulary");
  return response.json();
}

export async function getVocabularyWord(wordId: number): Promise<VocabularyWord> {
  const response = await fetch(`${API_BASE_URL}/api/vocabulary/${wordId}`);
  if (!response.ok) throw new Error("Failed to load word");
  return response.json();
}

export async function listVocabularyThemes(): Promise<string[]> {
  const response = await fetch(`${API_BASE_URL}/api/vocabulary/themes`);
  if (!response.ok) throw new Error("Failed to load themes");
  return response.json();
}

export async function createVocabularyWord(payload: VocabularyPayload, editorPassword: string): Promise<VocabularyWord> {
  const response = await fetch(`${API_BASE_URL}/api/vocabulary`, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Editor-Password": editorPassword },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to save word");
  return response.json();
}

export async function updateVocabularyWord(
  wordId: number,
  payload: VocabularyPayload,
  editorPassword: string,
): Promise<VocabularyWord> {
  const response = await fetch(`${API_BASE_URL}/api/vocabulary/${wordId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", "X-Editor-Password": editorPassword },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to update word");
  return response.json();
}


export async function verifyEditorPassword(editorPassword: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/vocabulary/editor/verify`, {
    method: "POST",
    headers: { "X-Editor-Password": editorPassword },
  });
  if (!response.ok) throw new Error("Failed to verify editor password");
}


export async function getNewWords(userId: string): Promise<{ words: VocabularyWord[] }> {
  const response = await fetch(`${API_BASE_URL}/api/learning/${encodeURIComponent(userId)}/new-words`);
  if (!response.ok) throw new Error("Failed to load new words");
  return response.json();
}

export async function completeNewWords(userId: string, wordIds: number[]) {
  const response = await fetch(`${API_BASE_URL}/api/learning/${encodeURIComponent(userId)}/new-words/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word_ids: wordIds }),
  });
  if (!response.ok) throw new Error("Failed to complete new words");
  return response.json();
}


export async function getReviewWords(userId: string): Promise<{ words: VocabularyWord[] }> {
  const response = await fetch(`${API_BASE_URL}/api/learning/${encodeURIComponent(userId)}/review`);
  if (!response.ok) throw new Error("Failed to load review words");
  return response.json();
}

export async function getReviewStatus(userId: string, wordId: number): Promise<{ is_due: boolean }> {
  const response = await fetch(
    `${API_BASE_URL}/api/learning/${encodeURIComponent(userId)}/review/status/${wordId}`,
  );
  if (!response.ok) throw new Error("Failed to load review status");
  return response.json();
}

export type ReviewRating = "again" | "hard" | "good" | "easy";

export type LearningProgress = {
  id: number;
  user_id: string;
  word_id: number;
  status: string;
  correct_count: number;
  incorrect_count: number;
  is_weak: boolean;
  next_review_at: string | null;
  review_interval_days: number;
  review_streak: number;
};

export async function submitReviewAnswer(
  userId: string,
  payload: { word_id: number; rating: ReviewRating },
): Promise<{ progress: LearningProgress }> {
  const response = await fetch(`${API_BASE_URL}/api/learning/${encodeURIComponent(userId)}/review/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to submit review answer");
  return response.json();
}

export async function completeReview(userId: string, wordIds: number[]) {
  const response = await fetch(`${API_BASE_URL}/api/learning/${encodeURIComponent(userId)}/review/complete`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ word_ids: wordIds }),
  });
  if (!response.ok) throw new Error("Failed to complete review");
  return response.json();
}


export type QuizQuestion = {
  word_id: number;
  question_type: "sr_to_ru_choice" | "ru_to_sr_typing" | "remembered_forgot_self_check";
  prompt: string;
  answer?: string | null;
  choices: string[];
};

export type QuizStart = { attempt_id: number; quiz_type: string; questions: QuizQuestion[] };
export type QuizCompletion = {
  score: number; total_questions: number; weak_word_ids: number[]; mistakes: Record<string, unknown>[];
  result_version?: 2; answer_key_status?: "frozen" | "legacy";
  breakdown_status?: "available" | "unavailable";
  first_attempt_correct?: number | null; first_attempt_eligible?: number | null;
  recovered_objective_items?: number | null;
  self_report_remembered?: number | null; self_report_total?: number | null;
};

export async function startQuiz(userId: string, quizType: "daily" | "weekly" = "daily"): Promise<QuizStart> {
  const response = await fetch(`${API_BASE_URL}/api/quizzes/${encodeURIComponent(userId)}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quiz_type: quizType }),
  });
  if (!response.ok) throw new Error("Failed to start quiz");
  return response.json();
}

export async function revealQuizAnswer(
  userId: string,
  attemptId: number,
  wordId: number,
  questionType: string,
): Promise<{ answer: string }> {
  const response = await fetch(
    `${API_BASE_URL}/api/quizzes/${encodeURIComponent(userId)}/${attemptId}/questions/${wordId}/${questionType}/answer`,
  );
  if (!response.ok) throw new Error("Failed to reveal answer");
  return response.json();
}

export async function submitQuizAnswer(
  userId: string,
  attemptId: number,
  payload: { word_id: number; question_type: string; answer: string },
): Promise<{ is_correct: boolean; repeat_word: boolean; is_weak: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/quizzes/${encodeURIComponent(userId)}/${attemptId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to submit answer");
  return response.json();
}

export async function completeQuiz(userId: string, attemptId: number): Promise<QuizCompletion> {
  const response = await fetch(`${API_BASE_URL}/api/quizzes/${encodeURIComponent(userId)}/${attemptId}/complete`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to complete quiz");
  return response.json();
}
