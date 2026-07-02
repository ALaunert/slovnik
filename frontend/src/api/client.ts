const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export type Profile = {
  user_id: string;
  preferred_level: string;
  daily_new_word_count: number;
  ui_language: string;
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
  payload: { preferred_level?: string; daily_new_word_count?: number; ui_language?: string },
): Promise<Profile> {
  const response = await fetch(`${API_BASE_URL}/api/profiles/${encodeURIComponent(userId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to update profile");
  return response.json();
}


export type VocabularyWord = {
  id: number;
  serbian_cyrillic: string;
  serbian_latin: string;
  russian_translation: string;
  cefr_level: string;
  theme: string;
  usage_register?: string | null;
  stress_marker?: string | null;
  meaning_notes?: string | null;
  example_sentences?: string | null;
  example_translations?: string | null;
};

export type VocabularyPayload = Omit<VocabularyWord, "id">;

export async function listVocabulary(filters: { cefr_level?: string; theme?: string } = {}): Promise<VocabularyWord[]> {
  const params = new URLSearchParams();
  if (filters.cefr_level) params.set("cefr_level", filters.cefr_level);
  if (filters.theme) params.set("theme", filters.theme);
  const suffix = params.toString() ? `?${params.toString()}` : "";
  const response = await fetch(`${API_BASE_URL}/api/vocabulary${suffix}`);
  if (!response.ok) throw new Error("Failed to load vocabulary");
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
export type QuizCompletion = { score: number; total_questions: number; weak_word_ids: number[]; mistakes: Record<string, unknown>[] };

export async function startQuiz(userId: string, quizType: "daily" | "weekly" = "daily"): Promise<QuizStart> {
  const response = await fetch(`${API_BASE_URL}/api/quizzes/${encodeURIComponent(userId)}/start`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ quiz_type: quizType }),
  });
  if (!response.ok) throw new Error("Failed to start quiz");
  return response.json();
}

export async function submitQuizAnswer(
  attemptId: number,
  payload: { word_id: number; question_type: string; answer: string },
): Promise<{ is_correct: boolean; repeat_word: boolean; is_weak: boolean }> {
  const response = await fetch(`${API_BASE_URL}/api/quizzes/${attemptId}/answers`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error("Failed to submit answer");
  return response.json();
}

export async function completeQuiz(attemptId: number): Promise<QuizCompletion> {
  const response = await fetch(`${API_BASE_URL}/api/quizzes/${attemptId}/complete`, { method: "POST" });
  if (!response.ok) throw new Error("Failed to complete quiz");
  return response.json();
}
