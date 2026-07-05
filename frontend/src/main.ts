import { createApp, watch } from "vue";

import App from "./App.vue";
import { router } from "./router";
import { sessionStore } from "./stores/session";
import "./styles.css";

function syncDocumentLanguage(language: string) {
  document.documentElement.lang = language;
}

syncDocumentLanguage(sessionStore.uiLanguage.value);
watch(sessionStore.uiLanguage, syncDocumentLanguage);

createApp(App).use(router).mount("#app");
