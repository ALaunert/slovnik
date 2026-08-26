# SDD-backend, фаза P3: граница учебной программы и выбор следующего действия

- Родительский документ: [`SDD-backend-language-assistant-foundation-2026-08-26.md`](SDD-backend-language-assistant-foundation-2026-08-26.md)
- **ID:** P3
- **Цель:** публиковать валидированный pilot программы A1 и выбирать внутреннее следующее действие через
  объяснимую детерминированную политику.
- **Зависимости:** G1/P1, DTO-01 и frozen ALG-02 interface; P3.T4 integration зависит от P2.T5.
- **Команда для реализации:** после G1 WS-A выполняет P3.T1→P3.T3, пока WS-C после своего P2 track
  выполняет P3.T2 с fake curriculum/projection ports. INT выполняет P3.T4 только после P2.T5;
  программа остаётся curated, выбор — deterministic, результат — internal/non-mutating.

## Текущее поведение

Текущие селекторы новых слов, повторения и тестов не меняются. Новый селектор вызывается только
внутренними тестами и начальной загрузкой и не обслуживает публичные маршруты до отдельного SDD
контрактов backend/frontend.

## Задачи

#### [P3.T1] Реализовать публикацию программы и политику границы доступности

**Уровень:** Complex

**Файлы:**

```changeset
~ backend/app/domain/curriculum.py
+ backend/app/domain/curriculum_policy.py
~ backend/app/repositories/curriculum.py
+ backend/app/services/curriculum_service.py
+ backend/tests/test_curriculum.py
```

**Референсы:**

- DTO-01 в [P1.T1]
- `backend/app/services/learning_service.py` — текущий точный фильтр CEFR, который новая политика не
  повторяет
- `docs/adr/ADR-language-assistant-domain-model-2026-08-26.md` §3 Curriculum

**Что сделать:**

Черновик программы разрешает редакционные изменения. Транзакция публикации валидирует ссылки на
цели, дубли ключей целей, коды результатов, принадлежность рёбер, отсутствие self-edge/двух типов
одного ребра и ацикличность HARD-графа.
Активация новой версии атомарно переводит прежнюю активную версию той же программы в состояние
`retired`. После публикации graph/content неизменяемы; единственная разрешённая мутация lifecycle —
`active -> retired` при активации следующей версии.

`outcome_code` имеет формат `<CEFR>.<stable-code>`, например `A1.location.basic`; префикс валиден
по A1→C2 и не является difficulty или memory field.

Граница возвращает `available`, `not_yet_ready` и коды причин. Готовность HARD-предусловия v1
означает, что для предшествующего `TargetSpec` существует состояние из нативных событий как минимум
с одним детерминированным успехом и replayable `competence_peak >= 0.6`. Peak является high-water
mark Beta-подобной оценки `(1 + success) / (2 + success + failure)`: последующее забывание или
ошибка повышает review/strengthen priority, но не закрывает уже открытый branch. SOFT-рёбра добавляют
признак готовности, но никогда не исключают кандидата.

**Ключевые ограничения:**

- на `curriculum_code` существует ровно одна активная версия; инвариант обеспечивает partial unique
  index, а сервис ставит старой версии `status=retired`/`retired_at` до вставки новой active row с
  обязательным `published_at`;
- `priority` лежит в `0..100`, где большее значение означает более высокий curriculum priority;
- выведенная программа остаётся разрешимой для исторических запусков и событий;
- версия программы является cumulative graph и может содержать outcome codes разных CEFR levels;
  CEFR не хранится одним полем версии;
- порядок outcome envelope фиксирован `A1 < A2 < B1 < B2 < C1 < C2`; он фильтрует coverage,
  но не используется как item difficulty;
- отсутствие состояния ученика означает отсутствие свидетельств, а не нулевое постоянное mastery;
- цель повторения, уже использованная учеником, не блокируется снова из-за текущего просроченного
  состояния памяти;
- уровень CEFR не копируется в состояние цели ученика.

**Проверка:**

- публикация отклоняет отсутствующую/неопубликованную цель, дубликат узла и HARD-цикл;
- retirement target, всё ещё используемого active curriculum, отклоняется до активации replacement;
- SOFT-цикл разрешён и никогда не блокирует границу;
- транзакция публикации оставляет одну активную версию при конкуренции PostgreSQL;
- конкурентная первая публикация без существующей active row также оставляет одного победителя;
- временное забывание меняет приоритет повторения, но не доступность границы.
- последующая deterministic failure не уменьшает `competence_peak` и не закрывает branch.

---

#### [P3.T2] Реализовать курированные кандидаты и SelectionPolicy v1

**Уровень:** Complex

**Файлы:**

```changeset
+ backend/app/domain/selection_ports.py
+ backend/app/domain/selection_policy.py
+ backend/app/services/next_activity_service.py
+ backend/tests/test_next_activity.py
```

**Референсы:**

- `backend/app/services/learning_service.py` — текущая сортировка по сроку
- `backend/app/services/quiz_service.py` — текущие три жёстко заданные формы вопросов
- `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` §9.1

**Что сделать:**

Реализовать курированный `ActivityCandidateProvider` для распознавания и извлечения лексики, а также
операций дополнения и преобразования конструкций. Провайдер формирует `ActivitySpec`, после чего
`ActivityValidityPolicy` повторно проверяет цель, HARD-ограничения, контракт ограниченного ответа и
оценивания, а также нагрузку вне основной цели. Реализации на AI нет, существует только порт.

Foundation не выдумывает calibrated `P(success)`. Для lexical activity допустимо `0` unglossed
non-target lexical/construction items. Для construction complete/transform допустим максимум один
unknown SOFT lexical item только с явным gloss; unready HARD target всегда отклоняется. Остальной
difficulty feature vector сохраняется для reason metadata, но не входит в rank до валидации.

Daily acquisition count v1 использует UTC calendar day, потому что текущий профиль не хранит
timezone: это число distinct `target_key` с первым completed `ACQUIRE` activity/event в интервале
`[00:00 UTC, next 00:00 UTC)`. Retry и несколько activities одной цели не расходуют бюджет повторно;
legacy baseline в счётчик не входит.

Селектор возвращает решение с намерением, выбранными целью и действием, полными кодами причин и
версией политики. Он не создаёт событие и не меняет состояние ученика.

Selection reason codes v1 для созданного activity: `due_review`, `weak_competence`, `new_target`,
`assessment_gap`. Decision codes при отсутствии activity: `daily_acquire_budget_reached`,
`no_active_curriculum`, `empty_frontier`, `no_valid_candidate`. Rank components возвращаются
отдельными typed fields, а не одной необъяснимой суммой.

**Ключевые ограничения:**

- участвуют только опубликованные контент и программа;
- у кандидата ровно одна основная цель;
- в основе обязателен детерминированный оценщик;
- в v1 нет случайного исследования; равенство разрешается по ключу цели и отпечатку действия;
- единого скаляра `difficulty` и оценки expected success в v1 нет: кандидат предоставляет только
  поддерживаемый вектор наблюдаемых признаков;
- пустое допустимое множество возвращает явную причину `no_activity`, а не произвольный fallback.

##### Канонический блок: ALG-03 (ALG) (NORMATIVE)

> NORMATIVE. Алгоритм задаёт порядок решения `selector-v1` и стабильное разрешение равенства.

```text
load learner profile, active curriculum and learner target states
frontier = nodes at/below requested CEFR outcome passing target validity and HARD readiness
review_nodes = frontier states with memory_due_at <= now
weak_nodes = frontier states with failure_weight > success_weight
acquire_nodes = frontier without native deterministic evidence and without a future memory hold
remove acquire_nodes when today's acquired-target count reaches profile daily budget
assess_nodes = frontier with native deterministic evidence
if review_nodes not empty: intent=REVIEW; eligible=review_nodes
else if weak_nodes not empty: intent=STRENGTHEN; eligible=weak_nodes
else if acquire_nodes not empty: intent=ACQUIRE; eligible=acquire_nodes
else if assess_nodes not empty: intent=ASSESS; eligible=assess_nodes
else: return no_activity with budget/frontier reason code
build curated candidates for eligible targets
discard candidates failing ActivityValidityPolicy
for each candidate compute repetition_count_7d and activity_fingerprint
rank key REVIEW = (memory_due_at ASC, priority DESC, repetition_count_7d ASC)
rank key STRENGTHEN = ((failure_weight-success_weight) DESC, priority DESC, repetition_count_7d ASC)
rank key ACQUIRE = (priority DESC, soft_ready_count DESC, repetition_count_7d ASC)
rank key ASSESS = (uncertainty DESC, last_evidence_at NULLS FIRST, priority DESC)
append target_key and activity_fingerprint ASC to every rank key
return first candidate plus rank components, stable reason codes and policy_version='selector-v1'
```

##### Канонический блок: ALG-04 (ALG) (NORMATIVE)

> NORMATIVE. Алгоритм задаёт стабильный `activity_fingerprint-v1` для tie-break и repetition history.

```text
payload = {
    schema_version, target_key, activity_kind, operation,
    input_modality, output_modality, cue_policy,
    stimulus_snapshot, feedback_policy_version,
    generator_kind, generator_version, scorer_kind, scorer_version
}
normalize and serialize payload with the canonical JSON profile from ALG-01
activity_fingerprint = SHA256(payload as UTF-8).hexdigest()
exclude activity/run IDs, timestamps, selection metadata and learner ID
```

**Проверка:**

- просроченное повторение опережает освоение нового;
- слабое место опережает освоение с равным приоритетом, не обходя HARD-ограничения;
- готовность SOFT влияет только на оценку;
- future legacy/bootstrap memory hold не приводит к повторному ACQUIRE до срока;
- дневной лимит блокирует только ACQUIRE, но никогда не review/strengthen;
- кандидат MCQ нацелен на распознавание, но никогда на извлечение;
- детерминированный порядок стабилен между запусками и не зависит от порядка строк базы;
- semantically equal activity specs имеют одинаковый ALG-04 fingerprint независимо от JSON key order;
- пустой или невалидный каталог возвращает `no_activity` с кодами причин.
- достигнутый daily budget не мешает выбрать due review.
- две ACQUIRE activities одной цели в один UTC-day расходуют одну единицу бюджета.
- unseen target никогда не получает ASSESS как обход daily acquisition budget.
- candidate за пределами non-target burden bounds отклоняется, а не получает произвольный penalty.

---

#### [P3.T3] Создать технический pilot A1 из текущего контента

**Уровень:** Standard

**Файлы:**

```changeset
~ backend/app/services/domain_bootstrap_service.py
~ backend/app/services/curriculum_service.py
~ backend/app/seed.py
```

**Референсы:**

- `backend/app/seed.py` — текущие начальные данные из трёх слов
- `backend/app/models.py` — текущие поля CEFR и темы
- `docs/progress/domain-model-v0.1.md` — отложенные решения о полной онтологии

**Что сделать:**

Расширить детерминированную команду начальной загрузки: она создаёт черновик технического pilot
`serbian-from-russian` версии 1 с A1 outcome codes. Каждый подходящий текущий элемент A1 добавляет
два узла для одного `Sense`: `recognize_meaning` и `retrieve_form`; ожидаемая citation `Form`
хранится в activity snapshot. Узлы конструкций и рёбра предусловий берутся только из явных
начальных данных; AI и порядок тем их не выводят.

**Ключевые ограничения:**

- текущий CEFR — ассоциация начальной загрузки, а не постоянное свойство контента;
- загрузка идемпотентна по коду и версии программы и стабильному сопоставлению цели;
- публикация происходит только после валидации; частично невалидная загрузка остаётся черновиком;
- текущие три seed-слова являются техническим fixture, а не заявлением о покрытии курса A1;
- контент A2–C2 и полные парадигмы не генерируются.

**Проверка:**

- повторная загрузка оставляет одну версию и стабильные ID узлов;
- узлы распознавания и извлечения используют разные ключи целей;
- оба lexical узла адресуют один Sense с разными capabilities, а не Sense и Form;
- явные HARD/SOFT-рёбра сохраняются после публикации и чтения;
- невалидная ссылка на конструкцию блокирует публикацию без частичной активации.

---

#### [P3.T4] Закрыть матрицу тестов программы и выбора

**Уровень:** Standard

**Файлы:**

```changeset
~ backend/tests/test_curriculum.py
~ backend/tests/test_next_activity.py
~ backend/tests/test_projection.py
```

**Референсы:**

- `backend/tests/test_learning.py` — табличные сценарии планировщика и сортировки
- `backend/tests/test_quizzes.py` — негативные сценарии кандидатов и вопросов

**Что сделать:**

INT объединяет green WS-A/WS-C commits после P2.T5 и покрывает состояния программы, циклы,
разрешение целей, выбор намерения, rank components, разделение памяти и компетенции, причины
отсутствия действия. Тесты проверяют коды причин, а не только выбранный ID.

**Ключевые ограничения:**

- тестовые сценарии используют фиксированное время UTC;
- до P3.T4 WS-A не редактирует selector tests, а WS-C — curriculum tests;
- нет зависимости от случайного порядка строк базы;
- нет реальных вызовов AI и сети;
- версии политик проверяются в каждой фикстуре решения и проекции.

**Проверка:**

- целевые модульные и интеграционные тесты проходят;
- повторный выбор для одного снимка побайтово стабилен;
- селекторы никогда не меняют строки каталога, программы и состояния.

## Проверка фазы

**Автотесты:** модульные и интеграционные тесты публикации и границы программы, конкуренция
активации PostgreSQL, матрица селектора и детерминированные снимки.

**Откат:** прекратить использовать новую активную программу и откатить код P3. Схема и события
P1/P2 остаются валидными, текущие селекторы продолжают работать без изменений.
