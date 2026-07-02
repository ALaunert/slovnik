import { ref } from "vue";

const USER_ID_KEY = "slovnik.userId";

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

export function createSessionStore(storage: StorageLike) {
  const userId = ref(storage.getItem(USER_ID_KEY) ?? "");

  function setUserId(nextUserId: string) {
    userId.value = nextUserId;
    storage.setItem(USER_ID_KEY, nextUserId);
  }

  function clearUserId() {
    userId.value = "";
    storage.removeItem(USER_ID_KEY);
  }

  return { userId, setUserId, clearUserId };
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
