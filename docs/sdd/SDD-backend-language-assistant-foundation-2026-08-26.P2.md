# SDD-backend, фаза P2: неизменяемые свидетельства и проекции ученика

- Родительский документ: [`SDD-backend-language-assistant-foundation-2026-08-26.md`](SDD-backend-language-assistant-foundation-2026-08-26.md)
- **ID:** P2
- **Цель:** записывать идемпотентные неизменяемые свидетельства и строить проекцию компетенции и
  памяти на уровне цели через версионированную политику.
- **Зависимости:** P1, DTO-01, SQL-01.
- **Команда для реализации:** после G1 WS-B выполняет P2.T1→P2.T2, а WS-C параллельно выполняет
  P2.T3→P2.T4. INT запускает P2.T5 только после обоих tracks; события остаются фактами, проекции —
  пересчитываемыми, текущий прогресс — только low-confidence baseline.

## Текущее поведение

Фаза не подключается к текущим маршрутам. `UserWordProgress` остаётся единственным источником
состояния для действующего UI. Новые сервисы до P4 вызываются только тестами и внутренней начальной
загрузкой.

## Задачи

#### [P2.T1] Реализовать жизненный цикл PracticeRun и ActivityInstance

**Уровень:** Standard

**Файлы:**

```changeset
~ backend/app/domain/practice.py
~ backend/app/domain/practice_ports.py
~ backend/app/repositories/practice.py
+ backend/app/services/practice_service.py
```

**Референсы:**

- `backend/app/services/quiz_service.py` — текущий жизненный цикл сохранённых попыток и плана
- `backend/app/services/learning_service.py` — текущая транзакционная граница одного повторения
- `docs/superpowers/specs/2026-08-26-domain-model-v0.1-design.md` §5.4–5.5

**Что сделать:**

Создать прикладной сервис переходов запуска, добавления, завершения и прекращения. При создании
`ActivityInstance` фиксирует неизменяемый снимок `ActivitySpec` и версии политик. После завершения
или отмены действия снимок контента не меняется.

**Ключевые ограничения:**

- принадлежность ученику проверяется при каждой загрузке и изменении;
- запуск не принимает ответы после завершения или прекращения;
- run переходит в completed только если содержит хотя бы одну activity и все они completed;
  abandonment атомарно переводит оставшиеся pending activities в cancelled и завершает run;
- `ended_at`/`terminal_at` заполняются только при конечном переходе и обязательны для terminal state;
- перед приёмом ответа строка activity блокируется; действие не принимается дважды даже при
  конкурентных запросах;
- повторная попытка является новым `ActivityInstance` с `retry_of_activity_instance_id` и
  возрастающим `attempt_number`;
- `sequence_number` уникален внутри run и задаёт показанный порядок; retry получает следующий номер,
  а не timestamp-based ordering; run блокируется при выделении следующего номера;
- activity наследует `selection_policy_version` run; другая версия требует новый run;
- exposure имеет `activity_kind=exposure` и `operation=NULL`; exercise всегда имеет operation;
- ключ цели пересчитывается из DTO-01 и должен совпасть со снимком;
- текущий публичный API тестов, новых слов и повторения не используется как новый доменный enum.

**Проверка:**

- модульные тесты переходов состояния;
- негативные тесты другого ученика и конечного состояния;
- пустой run или run с pending/cancelled activity нельзя пометить completed;
- два конкурентных submission с разными idempotency keys к одному activity дают один event и один
  стабильный conflict; одинаковый ключ и payload возвращают одно сохранённое событие обоим;
- retry создаёт новый связанный activity, не переоткрывая старый;
- одинаковые timestamps не меняют порядок activity sequence;
- снимок не меняется после редактирования каталога.

---

#### [P2.T2] Идемпотентно записывать канонический LearningEvent

**Уровень:** Complex

**Файлы:**

```changeset
~ backend/app/domain/practice.py
~ backend/app/repositories/practice.py
+ backend/app/services/learning_event_service.py
+ backend/tests/test_learning_events.py
```

**Референсы:**

- `backend/app/models.py` — `QuizAnswer` как частичная текущая запись, похожая на событие
- `backend/app/services/ai_vocabulary_service.py` — ограниченные и идемпотентные способы сохранения
- DTO-01 в [P1.T1]

**Что сделать:**

В одной транзакции принять ограниченный ответ, создать неизменяемое событие и завершить действие.
Уникальная пара `(learner_id, idempotency_key)` определяет повтор запроса. Дубликат с той же
семантической нагрузкой возвращает исходное событие; дубликат с другой нагрузкой отклоняется как
конфликт идемпотентности.

Семантическая нагрузка для сравнения дубликата — canonical JSON из `activity_instance_id`,
нормализованных NFC response snapshots и stable `legacy_source` ref. Из fingerprint исключены
idempotency key, event ID, server timestamps, latency и полученное evaluation: они создаются один
раз при первой обработке, а повтор всегда возвращает сохранённый результат.

**Ключевые ограничения:**

- строки событий никогда не обновляются и не удаляются прикладными сервисами;
- idempotency key проверяется быстрым lookup до блокировки и повторно после блокировки activity;
  только затем terminal state может дать conflict, поэтому concurrent retry того же запроса
  возвращает сохранённое событие;
- idempotency lookup выполняется до создания retry/run side effects; конфликт или retry не оставляет
  orphan `PracticeRun`/`ActivityInstance`;
- административное удаление/обезличивание данных ученика является отдельным lifecycle, а не
  нарушением обычной append-only семантики;
- снимки ответа ограничены 2000 кодовыми точками Unicode; при превышении хранится ограниченный
  префикс и `truncated=true`, а исходная текущая запись остаётся ссылкой аудита;
- canonical serialized `observation_payload` ограничен 16 KiB; `error_tags` — 32 значениями по 64
  символа, `hints` — 10 bounded objects, `selection_reasons` — только enum v1. Response snapshot
  имеет закрытую форму `{kind, value, truncated}`; choice хранит option key, rating — enum, text —
  максимум 2000 Unicode code points. Hint хранит только `{kind, sequence_number}` с kind
  `cue|reveal|correction`; feedback — только bounded code/delivery metadata. Oversize input
  отклоняется до записи, кроме явно разрешённого truncation response snapshot;
- событие не содержит ключ API, prompt внутреннего AI-провайдера или неограниченный текст беседы;
- цель, спецификация и версии политик берутся из сохранённого `ActivityInstance`, а не изменяемого
  каталога;
- exposure не имеет response/evaluation; exercise `evaluation_source` обязан совпасть с
  `ActivityInstance.scorer_kind`; `partial_score` допустим и обязателен только для `partial`;
- self-report требует `outcome=unknown` и валидированный rating, model-assisted требует finite
  confidence; deterministic partial в projection-v1 сохраняется, но не меняет competence/memory;
- native `occurred_at` должен быть timezone-aware, не раньше `ActivityInstance.selected_at` и не
  позже server receipt time + 5 минут; `created_at` берётся из database clock. Historical import
  обязан использовать отдельную явно помеченную policy, а не ослаблять native validation;
- событие не хранит версию проектора: один и тот же факт можно replay-ить новой политикой, а версия
  применённой интерпретации принадлежит `LearnerTargetState`;
- `SELF_REPORT` и `MODEL_ASSISTED` сохраняются как происхождение, а не детерминированная истина.

##### Канонический блок: EVENT-01 (EVENT) (NORMATIVE)

> NORMATIVE. Контракт описывает семантическую нагрузку неизменяемой схемы `LearningEvent` v1.

| Поле | Тип | Обязательность | Описание |
|---|---|---|---|
| `event_id` | UUID string | да | Стабильный идентификатор события |
| `schema_version` | integer | да, `1` | Версия схемы события |
| `learner_id` | string | да | Существующий ключ идентичности ученика |
| `practice_run_id` | UUID string | да | Снимок владеющего запуска |
| `activity_instance_id` | UUID string | да | Снимок вызвавшего действие экземпляра |
| `target_spec` | DTO-01 | да | Каноническая основная цель |
| `event_type` | enum | да | `exposure` или `response_evaluated` |
| `learning_intent` | enum | да | `acquire`, `review`, `strengthen`, `assess` |
| `activity_kind` | enum | да | `exposure` или `exercise` |
| `operation` | enum/null | нет для exposure | `recognize`, `retrieve`, `complete`, `transform` |
| `input_modality` | enum | да | MVP: `written` |
| `output_modality` | enum/null | нет для exposure | MVP: `written` |
| `cue_level` | enum | да | `full`, `partial`, `minimal`, `none` |
| `first_response` | bounded object/null | нет | Снимок текста или значения и признак усечения |
| `final_response` | bounded object/null | нет | После подсказок или исправления |
| `evaluation_source` | enum/null | нет для exposure | `deterministic`, `self_report`, `model_assisted` |
| `evaluation_outcome` | enum/null | нет для exposure | `correct`, `partial`, `incorrect`, `unknown` |
| `evaluation_confidence` | number/null | да для model-assisted | Finite confidence оценщика `0..1`; null для остальных |
| `partial_score` | number/null | нет | Диапазон `0..1` |
| `error_tags` | string array | да | Пустой массив, если неизвестно |
| `latency_ms` | integer/null | нет | Измеренная неотрицательная задержка |
| `hints` | object array | да | Пустой массив, если не использовались или не наблюдались |
| `learner_confidence` | number/null | нет | Самооценка в диапазоне `0..1` |
| `feedback` | object/null | нет | Тип и время без секретов провайдера |
| `repair_outcome` | enum/null | нет | `repaired`, `not_repaired`, `not_attempted` |
| `legacy_source` | object/null | нет | Тип источника и стабильная ссылка на текущую строку или запрос |
| `generator_kind` | enum | да | `curated` или `model_assisted` |
| `generator_version` | string | да | Происхождение генератора действия |
| `scorer_version` | string/null | нет для exposure | Происхождение оценивания |
| `selection_policy_version` | string | да | Версия политики выбора activity |
| `selection_reasons` | string array | да | Стабильные коды причин выбора |
| `selection_propensity` | number/null | нет | Вероятность logged policy; `NULL` для deterministic v1 |
| `idempotency_key` | string | да | Уникален в пределах ученика |
| `occurred_at` | UTC timestamp | да | Время взаимодействия ученика |

Колонки SQL-01 хранят identity, ownership, `target_key`, activity/event kind, idempotency и timestamps.
Остальные поля EVENT-01 входят в canonical `observation_payload`; сохранённый `target_spec`
пересчитывается в тот же `target_key`. Для созданного activity разрешены selection reason codes
`due_review`, `weak_competence`, `new_target`, `assessment_gap`, `legacy_new_word`, `legacy_review`
и `legacy_quiz`; отсутствие решения имеет отдельные decision codes и не создаёт event.

**Проверка:**

- повтор с тем же ключом и нагрузкой возвращает одну строку;
- concurrent повтор с тем же ключом возвращает тот же event, а не terminal-activity conflict;
- тот же ключ с другой нагрузкой возвращает стабильную ошибку конфликта;
- конечное действие, другой ученик и несовпадающая цель отклоняются;
- несовместимые activity/scorer/outcome/partial-score combinations отклоняются;
- naive/future/pre-selection timestamps отклоняются;
- разные idempotency keys не могут создать два события для одного activity;
- сохранённое событие не меняется после редактирования каталога или программы;
- тесты удаления секретов и сырого prompt провайдера.

---

#### [P2.T3] Реализовать проектор и консервативную MemoryPolicy v1

**Уровень:** Complex

**Файлы:**

```changeset
~ backend/app/domain/progress.py
~ backend/app/domain/memory_policy.py
~ backend/app/repositories/progress.py
+ backend/app/services/learner_projection_service.py
+ backend/tests/test_projection.py
```

**Референсы:**

- `backend/app/services/learning_service.py` — текущий переход срока и способ блокировки строки
- `backend/tests/test_learning.py` — текущая проверка конкурентности PostgreSQL
- EVENT-01 в [P2.T2]

**Что сделать:**

Проектор создаёт и блокирует одно `LearnerTargetState`, применяет только допустимые свидетельства и
сохраняет версии политик проекции и памяти. Чистая функция проекции должна выдавать то же состояние
при replay frozen baseline и событий в каноническом порядке `(occurred_at, event_id)`.

Интервалы `memory-v1` — явная compatibility heuristic, а не научно универсальный schedule. Они
нужны для проверяемого baseline и заменяются новой версией политики без переписывания событий.

**Ключевые ограничения:**

- в v1 компетенцию обновляют только детерминированные события `response_evaluated`;
- self-report не меняет competence, но может менять отдельное memory schedule через сохранённую
  Again/Hard/Good/Easy-семантику; первое exposure создаёт acquisition hold/первый due для своего
  declared target через один день, но не получает competence или memory-strength credit;
  model-assisted evidence не получает credit в v1;
- self-report rating хранится в bounded `first_response.value`, имеет
  `evaluation_source=self_report` и `evaluation_outcome=unknown`; projector принимает только
  валидированный enum, а не произвольную строку;
- неверный детерминированный ответ не отменяет доступность узла программы;
- отсутствующая state row сначала материализуется конфликт-безопасным insert с neutral frozen
  baseline, затем блокируется; глобальной блокировки ученика нет;
- replay начинает с неизменяемых baseline schedule/source fingerprint; legacy baseline не даёт
  evidence и не меняется после первого native event;
- событие раньше сохранённого cursor `(last_evidence_at,last_event_id)` запускает target-local replay,
  иначе incremental state может разойтись с canonical order даже при одинаковых timestamps;
- все временные метки используют UTC и корректные значения базы; время запроса измеряется
  монотонными часами до события.

##### Канонический блок: ALG-02 (ALG) (NORMATIVE)

> NORMATIVE. Алгоритм задаёт переход состояния `projection-v1` и `memory-v1`.

```text
insert event by (learner_id, idempotency_key)
if existing semantic event: return existing state without update
ensure state exists with conflict-safe insert and frozen neutral baseline; then lock learner/target row
if (event.occurred_at,event.id) < state.cursor: reset to frozen baseline; replay target events by tuple; return
increment evidence_count and set cursor=(event.occurred_at,event.id)
if event is deterministic and outcome is correct:
    success_weight += 1
    competence_peak = max(competence_peak, (1+success_weight)/(2+success_weight+failure_weight))
    interval_days = 1 if interval_days == 0 else min(interval_days * 2, 180)
    memory_due_at = occurred_at + interval_days
if event is deterministic and outcome is incorrect:
    failure_weight += 1
    interval_days = 0
    memory_lapses += 1
    memory_due_at = occurred_at
if event is first exposure and memory_due_at is null: interval_days=1; memory_due_at=occurred_at+1d
if event is self_report:
    AGAIN => interval=0, due=occurred_at+10m, lapses+=1
    HARD  => interval=1, due=occurred_at+1d
    GOOD  => interval=2 if interval<2 else min(interval*2, 180), due accordingly
    EASY  => interval=4 if interval<4 else min(interval*3, 365), due accordingly
uncertainty = 2 / (2 + success_weight + failure_weight)
store projection_version='projection-v1' and memory_version='memory-v1'
commit event, activity transition and state atomically
```

**Проверка:**

- табличные тесты для каждого события, источника оценки и результата;
- replay и пошаговая проекция создают одинаковое состояние;
- событие, пришедшее раньше cursor, включая reverse-ID при равном времени, включает replay и не
  меняет итог;
- дубликат события не меняет счётчики и расписание;
- две сессии PostgreSQL безопасно создают отсутствующий state и не могут применить один event дважды;
- self-report меняет только memory; первое exposure только планирует retrieval; model-assisted
  меняет только evidence metadata; ни один из них не меняет `competence_peak`;
- `competence_peak` replayable и не снижается от последующей ошибки;
- просроченное состояние не меняет доступность программы, потому что эти поля здесь не принадлежат.

---

#### [P2.T4] Перенести текущий прогресс как низкоуверенную проекцию

**Уровень:** Complex

**Файлы:**

```changeset
+ backend/app/services/legacy_progress_bootstrap_service.py
~ backend/app/repositories/progress.py
+ backend/tests/test_legacy_progress_bootstrap.py
~ backend/tests/test_projection.py
```

**Референсы:**

- `backend/app/models.py` — текущий `UserWordProgress` и его расписание
- `backend/app/services/learning_service.py` — текущая семантика срока и weak-состояния
- `frontend/src/views/ReviewView.vue` — русский cue требует извлечь сербскую форму
- ADR §3 «Migration policy»

**Что сделать:**

Идемпотентно создать по одной низкоуверенной `LearnerTargetState` для каждого сопоставленного
`UserWordProgress`. Цель — письменная `retrieve_form` для основного `Sense`; ожидаемая citation
`Form` остаётся частью будущего activity snapshot. Старое расписание переносится как память, но не
как свидетельство компетенции. Синтетические `LearningEvent` не создаются.

Правила `legacy-bootstrap-v1`:

- `success_weight=0`, `failure_weight=0`, `competence_peak=0`, `evidence_count=0`, `uncertainty=1`;
- `memory_due_at` копирует нормализованный `next_review_at`; если он отсутствует, но текущая логика
  считает запись просроченной или weak, используется время запуска bootstrap; для legacy null-row,
  показанной сегодня и ещё не due, используется начало следующего дня UTC как migration hold;
- `memory_interval_days` копируется, `memory_lapses=0`, потому что `incorrect_count` смешивает
  результаты разных упражнений;
- `baseline_kind=legacy_bootstrap`; baseline due/interval являются frozen columns, а bounded
  `baseline_payload` (до 4 KiB) содержит schema version, stable source-row ref и source fingerprint;
- до первого native event текущие due/interval равны baseline, обе версии политик —
  `legacy-bootstrap-v1`; после event текущие версии меняются на v1, но baseline остаётся прежним.

**Ключевые ограничения:**

- bootstrap-состояние не удовлетворяет HARD prerequisite и не становится native evidence;
- neutral baseline и state с `evidence_count > 0` bootstrap никогда не перезаписывает;
- изменившийся source можно повторно snapshot-ить только пока `evidence_count=0`; после первого
  event baseline навсегда frozen для детерминированного replay;
- повторный запуск не меняет ID и не сдвигает срок, если исходная строка не изменилась;
- отсутствующее или неоднозначное сопоставление пропускается с диагностическим счётчиком, без
  придумывания цели;
- личные данные и сырой ответ ученика не журналируются.

**Проверка:**

- learned/seen/reviewing-строки дают только низкоуверенное `Sense + retrieve_form` состояние;
- due/weak/null-schedule сценарии совпадают с текущей семантикой срока;
- null-schedule row, показанная сегодня, не попадает в ACQUIRE и становится due на следующий день;
- bootstrap не создаёт события и не открывает HARD-зависимость;
- state с `evidence_count > 0` сохраняется без изменений;
- два запуска побайтово стабильны для неизменившихся источников.

---

#### [P2.T5] Закрыть интеграционные тесты свидетельств и replay

**Уровень:** Standard

**Файлы:**

```changeset
~ backend/tests/test_learning_events.py
~ backend/tests/test_projection.py
~ backend/tests/test_migrations.py
```

**Референсы:**

- `backend/tests/test_ai_vocabulary.py` — стиль тестов конкурентности и сбоев
- `backend/tests/test_migrations.py` — одноразовая цель PostgreSQL

**Что сделать:**

INT объединяет только green WS-B/WS-C commits и добавляет сценарии отката транзакции, конфликта
идемпотентности, порядка replay, принадлежности разным ученикам и конкуренции PostgreSQL. Проверить,
что сбой проектора откатывает изменение события и действия.

**Ключевые ограничения:**

- тесты не используют паузы как механизм корректности;
- до P2.T5 WS-B не редактирует projection tests, а WS-C — event tests;
- конкурентная синхронизация строится на барьерах и событиях;
- ошибки переданной конфигурации PostgreSQL завершают тест ошибкой, а не пропуском.

**Проверка:**

- целевые тесты проходят на SQLite;
- цель конкуренции событий проходит на PostgreSQL;
- Ruff проходит для всех новых доменных, сервисных и тестовых модулей.

## Проверка фазы

**Автотесты:** модульные переходы состояния, интеграционная транзакция события, эквивалентность
replay, legacy progress seed, владение, идемпотентность и конкуренция PostgreSQL.

**Откат:** отключить вызывающие стороны сервиса P2 и откатить код; схему и события можно оставить.
Если понижается миграция P1, данные P2 удаляются вместе с новыми таблицами без влияния на текущую
модель.
