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
