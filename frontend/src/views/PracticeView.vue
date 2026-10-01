<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { RouterLink, useRouter } from "vue-router";

import {
  createOrResumePractice, getPracticeAvailability, nextPracticeActivity, submitPracticeResponse,
  createPracticeRepair, getPracticeFeedback, getPracticeRun,
  type PracticeActivity, type PracticeRun, type PracticeFeedback, type PracticeSupport, type PracticeWorkload,
} from "../api/client";
import { messages } from "../i18n/messages";
import { sessionStore } from "../stores/session";

type Pending = { activityId: string; idempotency_key: string; response?: string };
type PendingRepair = { parentId: string; retry_id: string; support: PracticeSupport };
type Saved = { version: 1; runId: string; pending?: Pending; repair?: PendingRepair };

const router = useRouter();
const userId = sessionStore.userId.value;
const copy = computed(() => messages[sessionStore.uiLanguage.value]);
const storageKey = `slovnik.practice.v1.${encodeURIComponent(userId)}`;
const run = ref<PracticeRun | null>(null);
const activity = ref<PracticeActivity | null>(null);
const answer = ref("");
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const unavailable = ref(false);
const profileRequired = ref(false);
const reason = ref<string | null>(null);
const pending = ref<Pending | undefined>();
const pendingRepair = ref<PendingRepair | undefined>();
const feedback = ref<PracticeFeedback | null>(null);
const workload = ref<PracticeWorkload | undefined>();
let saved: Saved | undefined;
let mounted = true;
onUnmounted(() => { mounted = false; });

function persist() {
  if (!saved) return;
  saved.pending = pending.value;
  saved.repair = pendingRepair.value;
  sessionStorage.setItem(storageKey, JSON.stringify(saved));
}

function readSaved(): Saved | undefined {
  try {
    const value = JSON.parse(sessionStorage.getItem(storageKey) ?? "null");
    if (value?.version !== 1 || typeof value.runId !== "string" || !value.runId) return;
    if (value.pending && (typeof value.pending.activityId !== "string"
      || typeof value.pending.idempotency_key !== "string"
      || (value.pending.response !== undefined && typeof value.pending.response !== "string"))) return;
    if (value.repair && (typeof value.repair.parentId !== "string" || typeof value.repair.retry_id !== "string"
      || !["cue", "reveal", "correction"].includes(value.repair.support))) return;
    return value;
  } catch { return; }
}

function adopt(nextRun: PracticeRun) {
  run.value = nextRun;
  workload.value = nextRun.workload;
  activity.value = nextRun.activities.find((item) => item.status === "pending")
    ?? nextRun.activities.at(-1) ?? null;
  if (activity.value?.result || (pending.value && pending.value.activityId !== activity.value?.id)) {
    pending.value = undefined;
    persist();
  }
  if (activity.value?.id === pendingRepair.value?.retry_id) {
    pendingRepair.value = undefined;
    persist();
  }
  answer.value = pending.value?.response ?? "";
}

async function load() {
  if (loading.value && run.value) return;
  loading.value = true;
  error.value = "";
  unavailable.value = false;
  profileRequired.value = !userId;
  try {
    if (profileRequired.value) return;
    if (!await getPracticeAvailability()) { unavailable.value = true; return; }
    saved = readSaved() ?? { version: 1, runId: crypto.randomUUID() };
    pending.value = saved.pending;
    pendingRepair.value = saved.repair;
    persist();
    const response = await createOrResumePractice(userId, saved.runId);
    if (!mounted) return;
    adopt(response);
    feedback.value = null;
  } catch {
    error.value = copy.value.practiceLoadError;
  } finally { if (mounted) loading.value = false; }
}

async function next(kind: "exercise" | "exposure" = "exercise") {
  if (!saved || saving.value || loading.value || pendingRepair.value) return;
  loading.value = true;
  error.value = "";
  try {
    const response = await nextPracticeActivity(userId, saved.runId, kind);
    if (!mounted) return;
    setActivity(response.activity);
    reason.value = response.reason;
    workload.value = response.workload;
    answer.value = "";
    feedback.value = null;
  } catch { error.value = copy.value.practiceLoadError; }
  finally { if (mounted) loading.value = false; }
}

async function submit() {
  if (!activity.value || activity.value.result || saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    pending.value ??= {
      activityId: activity.value.id, idempotency_key: crypto.randomUUID(),
      ...(activity.value.kind === "exposure" ? {} : { response: answer.value }),
    };
    persist();
    const { activityId, ...body } = pending.value;
    const result = await submitPracticeResponse(userId, activityId, body);
    if (!mounted) return;
    setActivity({ ...activity.value, result, status: "completed" });
    pending.value = undefined;
    persist();
  } catch { error.value = copy.value.practiceSaveError; }
  finally { if (mounted) saving.value = false; }
}

function setActivity(value: PracticeActivity | null) {
  activity.value = value;
  if (!value || !run.value) return;
  run.value = { ...run.value, activities: [...run.value.activities.filter((item) => item.id !== value.id), value] };
}

async function showFeedback() {
  if (!activity.value?.result || saving.value || pendingRepair.value) return;
  if (canRepair.value) { await repair("reveal"); return; }
  saving.value = true;
  error.value = "";
  try {
    const response = await getPracticeFeedback(userId, activity.value.id);
    if (mounted) feedback.value = response;
  } catch { error.value = copy.value.practiceFeedbackError; }
  finally { if (mounted) saving.value = false; }
}

async function repair(support: PracticeSupport) {
  if (!activity.value?.result || saving.value) return;
  saving.value = true;
  error.value = "";
  try {
    pendingRepair.value ??= { parentId: activity.value.id, retry_id: crypto.randomUUID(), support };
    persist();
    const { parentId, ...body } = pendingRepair.value;
    const child = await createPracticeRepair(userId, parentId, body);
    if (!mounted) return;
    setActivity(child);
    answer.value = "";
    feedback.value = null;
    pendingRepair.value = undefined;
    persist();
    if (saved) {
      try { workload.value = (await getPracticeRun(userId, saved.runId)).workload; }
      catch { /* Issued repair remains usable; refreshing limits can wait for resume. */ }
    }
  } catch (failure) {
    const rejected = failure instanceof Error && "status" in failure && failure.status === 409;
    if (rejected) {
      pendingRepair.value = undefined;
      persist();
      if (saved) {
        try { adopt(await getPracticeRun(userId, saved.runId)); }
        catch { /* Definite rejection permits navigation; retry reload for server state. */ }
      }
    }
    error.value = rejected ? copy.value.practiceRepairRejected : copy.value.practiceRepairError;
  }
  finally { if (mounted) saving.value = false; }
}

const originalResult = computed(() => run.value?.activities.find((item) => item.id === activity.value?.retry_of)?.result);
const repairEligible = computed(() => activity.value?.kind === "exercise" && !activity.value.retry_of
  && ["incorrect", "unresolved"].includes(activity.value.result?.outcome ?? "")
  && feedback.value?.can_repair !== false);
const retiredPolicy = computed(() => run.value?.policy_version !== "local-written-selector-v2");
const canRepair = computed(() => repairEligible.value && !retiredPolicy.value
  && (!workload.value || workload.value.remaining.repair > 0));
const workloadKind = computed(() => activity.value?.retry_of ? copy.value.practiceKindRepair
  : activity.value?.selection_reasons.includes("new_target") ? copy.value.practiceKindNew
    : activity.value?.selection_reasons.includes("due_review") ? copy.value.practiceKindDue : copy.value.practiceKindPractice);
const stopReason = computed(() => reason.value === "daily_acquire_budget_reached" ? copy.value.practiceBudgetReached
  : reason.value === "daily_workload_budget_reached" ? copy.value.practiceWorkloadReached
    : reason.value === "policy_retired" ? copy.value.practicePolicyRetired : copy.value.practiceNoReviewedTask);

async function newRun() {
  if (saving.value || loading.value || pending.value || pendingRepair.value || activity.value?.status === "pending") return;
  saved = { version: 1, runId: crypto.randomUUID() };
  persist();
  run.value = null;
  activity.value = null;
  reason.value = null;
  feedback.value = null;
  workload.value = undefined;
  await load();
}

const resultText = computed(() => {
  const outcome = activity.value?.result?.outcome;
  if (outcome === "correct") return activity.value?.retry_of ? copy.value.practiceRepairCorrect : copy.value.practiceCorrect;
  if (outcome === "incorrect") return activity.value?.retry_of ? copy.value.practiceRepairIncorrect : copy.value.practiceIncorrect;
  if (outcome === "unresolved") return copy.value.practiceUnresolved;
  return copy.value.practiceExposureSaved;
});

onMounted(load);
</script>

<template>
  <main class="page practice-page">
    <header class="page-header">
      <h1>{{ copy.practiceTitle }}</h1>
      <RouterLink to="/dashboard">{{ copy.backToDashboard }}</RouterLink>
    </header>
    <p>{{ copy.practiceScope }}</p>
    <aside v-if="workload" class="panel" data-test="practice-workload">
      <h2>{{ copy.practiceWorkloadTitle }}</h2>
      <p>{{ copy.practiceWorkloadWindow }} {{ workload.timezone }}</p>
      <p v-if="workload.window">{{ copy.practiceWorkloadReset }} {{ workload.window.end }}</p>
      <p v-if="workload.window?.transition">{{ copy.timezonePolicy }}</p>
      <p>{{ copy.practiceIssued }}: {{ workload.issued.total }} / {{ workload.limits.total }}.</p>
      <p>{{ copy.practiceRemainingLimit }}: {{ workload.remaining.total }}.</p>
      <p>{{ copy.practiceKindNew }}: {{ workload.issued.new }} / {{ workload.limits.new }};
        {{ copy.practiceKindDue }}: {{ workload.issued.due }};
        {{ copy.practiceKindPractice }}: {{ workload.issued.weak + workload.issued.assessment }};
        {{ copy.practiceKindRepair }}: {{ workload.issued.repair }} / {{ workload.limits.repair }}.</p>
      <p>{{ copy.practiceLimitCaveat }}</p>
    </aside>
    <p v-if="loading" role="status">{{ copy.loading }}</p>
    <section v-if="profileRequired" class="panel" role="status">
      <h2>{{ copy.practiceProfileRequired }}</h2>
      <p>{{ copy.practiceProfileHint }}</p>
      <RouterLink data-test="practice-profile-entry" class="button-link" to="/?next=practice">{{ copy.practiceSelectProfile }}</RouterLink>
    </section>
    <section v-else-if="unavailable" class="panel" role="status">
      <h2>{{ copy.practiceUnavailable }}</h2>
      <p>{{ copy.practiceUnavailableHint }}</p>
      <button data-test="retry-availability" type="button" :disabled="loading" @click="load">{{ copy.practiceReload }}</button>
      <RouterLink to="/textbook">{{ copy.textbook }}</RouterLink>
    </section>
    <p v-if="error" class="error" role="alert">{{ error }}</p>
    <button v-if="error && (!pending || !activity)" type="button" @click="load">{{ copy.practiceReload }}</button>
    <section v-if="run && !activity && !loading && !reason && !error" class="panel">
      <p>{{ copy.practiceChoose }}</p>
      <button data-test="start-practice" type="button" @click="next('exercise')">{{ copy.practiceStart }}</button>
      <button data-test="start-exposure" type="button" @click="next('exposure')">{{ copy.practiceStartExposure }}</button>
    </section>
    <section v-if="activity && !loading" class="panel">
      <p class="eyebrow">{{ copy.practiceTask }} {{ activity.sequence_number }}</p>
      <p>{{ workloadKind }}</p>
      <p class="practice-text">{{ activity.task.input }}</p>
      <p id="practice-instruction" class="practice-text">{{ activity.task.instruction_ru }}</p>
      <aside v-if="activity.retry_of" class="panel">
        <p>{{ copy.practiceAssisted }}</p>
        <p v-if="originalResult">{{ originalResult.outcome === 'incorrect' ? copy.practiceIncorrect : copy.practiceUnresolved }}</p>
        <p v-if="originalResult?.first_response" class="practice-text">{{ originalResult.first_response }}</p>
        <p v-if="activity.support?.kind === 'cue'">{{ copy.practiceHint }}</p>
        <p v-else>{{ copy.practiceShownExample }}</p>
        <p class="practice-text">{{ activity.support?.instruction_ru }}</p>
        <template v-if="activity.support?.example">
          <p lang="sr" class="practice-text">{{ activity.support.example.serbian }}</p>
          <p lang="ru" class="practice-text">{{ activity.support.example.translation }}</p>
          <p class="practice-text">{{ copy.answerLabel }}: {{ activity.support.example.answer }}</p>
        </template>
      </aside>
      <div v-if="activity.kind === 'exposure' && activity.presentation">
        <p class="practice-text" lang="sr">{{ activity.presentation.serbian }}</p>
        <p class="practice-text" lang="ru">{{ activity.presentation.translation }}</p>
        <p>{{ copy.practiceExposure }}</p>
      </div>
      <div v-if="activity.result" role="status" aria-live="polite">
        <h2>{{ resultText }}</h2>
        <p v-if="activity.result.first_response !== null" class="practice-text">{{ activity.result.first_response }}</p>
        <p>{{ copy.practiceEvidence }}</p>
        <button v-if="activity.kind === 'exercise' && !feedback && !pendingRepair && (!repairEligible || canRepair)" data-test="show-feedback" type="button" :disabled="saving" @click="showFeedback">{{ copy.practiceShowFeedback }}</button>
        <aside v-if="feedback" class="panel">
          <h3>{{ copy.practiceReviewedExample }}</h3>
          <p class="practice-text">{{ feedback.instruction_ru }}</p>
          <p lang="sr" class="practice-text">{{ feedback.example.serbian }}</p>
          <p lang="ru" class="practice-text">{{ feedback.example.translation }}</p>
          <p class="practice-text">{{ copy.answerLabel }}: {{ feedback.example.answer }}</p>
          <p v-if="activity.result.outcome === 'unresolved'">{{ copy.practiceUnresolvedFeedback }}</p>
        </aside>
        <button v-if="pendingRepair" data-test="retry-repair" type="button" :disabled="saving" @click="repair(pendingRepair.support)">{{ copy.practiceRetryRepair }}</button>
        <template v-else-if="canRepair">
          <button data-test="hint-repair" type="button" :disabled="saving" @click="repair('cue')">{{ copy.practiceUseHint }}</button>
        </template>
        <p v-else-if="repairEligible">{{ retiredPolicy ? copy.practicePolicyRetired : copy.practiceRepairBudgetReached }}</p>
        <button type="button" :disabled="saving || !!pendingRepair" @click="next(activity.kind)">{{ copy.next }}</button>
      </div>
      <div v-else-if="pending">
        <p class="practice-text">{{ pending.response }}</p>
        <p>{{ copy.practicePending }}</p>
        <button data-test="retry-submit" type="button" :disabled="saving" @click="submit">{{ saving ? copy.savingReview : copy.practiceRetrySubmit }}</button>
      </div>
      <button v-else-if="activity.kind === 'exposure'" data-test="record-exposure" type="button" :disabled="saving" @click="submit">{{ copy.practiceRecordExposure }}</button>
      <form v-else @submit.prevent="submit">
        <fieldset v-if="activity.response_contract?.kind === 'choice'" :disabled="saving">
          <legend>{{ copy.answerLabel }}</legend>
          <label v-for="(option, index) in activity.response_contract.options ?? []" :key="index">
            <input v-model="answer" type="radio" name="practice-answer" :value="option" required /> {{ option }}
          </label>
        </fieldset>
        <label v-else>
          {{ copy.answerLabel }}
          <textarea v-model="answer" name="practice-answer" rows="4" :maxlength="activity.response_contract?.max_codepoints ?? 2000" :disabled="saving" aria-describedby="practice-instruction" />
        </label>
        <button type="submit" :disabled="saving">{{ saving ? copy.savingReview : copy.check }}</button>
      </form>
    </section>
    <section v-if="!loading && !unavailable && reason" class="panel" role="status">
      <h2>{{ copy.practiceNoActivity }}</h2>
      <p>{{ stopReason }}</p>
      <button data-test="new-practice-run" type="button" :disabled="saving || !!pending || !!pendingRepair" @click="newRun">{{ copy.practiceNewRun }}</button>
    </section>
    <button data-test="stop-practice" type="button" :disabled="saving" @click="router.push('/dashboard')">{{ copy.practiceStop }}</button>
  </main>
</template>

<style scoped>
.practice-text { white-space: pre-wrap; overflow-wrap: anywhere; }
.practice-page textarea { width: 100%; min-height: 7rem; box-sizing: border-box; font: inherit; }
.practice-page fieldset { display: grid; gap: 0.75rem; }
.practice-page label { display: grid; gap: 0.5rem; margin-bottom: 1rem; }
.practice-page input[type="radio"] { width: auto; }
</style>
