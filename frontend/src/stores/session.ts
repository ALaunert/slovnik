import { ref } from "vue";

const USER_ID_KEY = "slovnik.userId";
const UI_LANGUAGE_KEY = "slovnik.uiLanguage";

export type UiLanguage = "ru" | "sr";
type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

function normalizeUiLanguage(value: string | null): UiLanguage {
  return value === "sr" ? "sr" : "ru";
}

export function createSessionStore(storage: StorageLike) {
  const userId = ref(storage.getItem(USER_ID_KEY) ?? "");
  const uiLanguage = ref<UiLanguage>(normalizeUiLanguage(storage.getItem(UI_LANGUAGE_KEY)));

  function setUserId(nextUserId: string) {
    userId.value = nextUserId;
    storage.setItem(USER_ID_KEY, nextUserId);
  }

  function setUiLanguage(nextLanguage: string) {
    const normalized = normalizeUiLanguage(nextLanguage);
    uiLanguage.value = normalized;
    storage.setItem(UI_LANGUAGE_KEY, normalized);
  }

  function clearUserId() {
    userId.value = "";
    storage.removeItem(USER_ID_KEY);
  }

  return { userId, uiLanguage, setUserId, setUiLanguage, clearUserId };
}

const memoryStorage = new Map<string, string>();
const fallbackStorage: StorageLike = {
  getItem: (key) => memoryStorage.get(key) ?? null,
  setItem: (key, value) => {
    memoryStorage.set(key, value);
  },
  removeItem: (key) => {
    memoryStorage.delete(key);
  },
};

const browserStorage =
  typeof window !== "undefined" &&
  window.localStorage &&
  typeof window.localStorage.getItem === "function"
    ? window.localStorage
    : fallbackStorage;

export const sessionStore = createSessionStore(browserStorage);
