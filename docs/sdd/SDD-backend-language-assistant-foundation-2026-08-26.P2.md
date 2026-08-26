# SDD-backend, фаза P2: неизменяемые свидетельства и проекции ученика

- Родительский документ: [`SDD-backend-language-assistant-foundation-2026-08-26.md`](SDD-backend-language-assistant-foundation-2026-08-26.md)
- **ID:** P2
- **Цель:** записывать идемпотентные неизменяемые свидетельства и строить проекцию компетенции и
  памяти на уровне цели через версионированную политику.
- **Зависимости:** P1, DTO-01, SQL-01.
- **Команда для реализации:** выполнить P2.T1–P2.T5 после зелёной P1, сохранив события фактами,
  проекции пересчитываемыми, а текущий прогресс — только низкоуверенной начальной точкой.

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
~ backend/app/domain/ports.py
~ backend/app/repositories/domain.py
+ backend/app/services/learning_event_service.py
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
- действие не принимается дважды;
- ключ цели пересчитывается из DTO-01 и должен совпасть со снимком;
- текущий публичный API тестов, новых слов и повторения не используется как новый доменный enum.

**Проверка:**

- модульные тесты переходов состояния;
- негативные тесты другого ученика и конечного состояния;
- снимок не меняется после редактирования каталога.

---

#### [P2.T2] Идемпотентно записывать канонический LearningEvent

**Уровень:** Complex

**Файлы:**

```changeset
~ backend/app/domain/practice.py
~ backend/app/repositories/domain.py
~ backend/app/services/learning_event_service.py
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

**Ключевые ограничения:**

- строки событий никогда не обновляются и не удаляются прикладными сервисами;
- снимки ответа ограничены 2000 кодовыми точками Unicode; при превышении хранится ограниченный
  префикс и `truncated=true`, а исходная текущая запись остаётся ссылкой аудита;
- событие не содержит ключ API, prompt внутреннего AI-провайдера или неограниченный текст беседы;
- цель, спецификация и версии политик берутся из сохранённого `ActivityInstance`, а не изменяемого
  каталога;
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
| `operation` | enum | да | `recognize`, `retrieve`, `complete`, `transform` |
| `input_modality` | enum | да | MVP: `written` |
| `output_modality` | enum/null | нет для exposure | MVP: `written` |
| `cue_level` | enum | да | `full`, `partial`, `minimal`, `none` |
| `first_response` | bounded object/null | нет | Снимок текста или значения и признак усечения |
| `final_response` | bounded object/null | нет | После подсказок или исправления |
| `evaluation_source` | enum/null | нет для exposure | `deterministic`, `self_report`, `model_assisted` |
| `evaluation_outcome` | enum/null | нет для exposure | `correct`, `partial`, `incorrect`, `unknown` |
| `partial_score` | number/null | нет | Диапазон `0..1` |
| `error_tags` | string array | да | Пустой массив, если неизвестно |
| `latency_ms` | integer/null | нет | Измеренная неотрицательная задержка |
| `hints` | object array | да | Пустой массив, если не использовались или не наблюдались |
| `learner_confidence` | number/null | нет | Самооценка в диапазоне `0..1` |
| `feedback` | object/null | нет | Тип и время без секретов провайдера |
| `repair_outcome` | enum/null | нет | `repaired`, `not_repaired`, `not_attempted` |
| `legacy_source` | object/null | нет | Тип источника и стабильная ссылка на текущую строку или запрос |
| `generator_version` | string | да | Происхождение генератора действия |
| `scorer_version` | string | да | Происхождение оценивания |
| `idempotency_key` | string | да | Уникален в пределах ученика |
| `occurred_at` | UTC timestamp | да | Время взаимодействия ученика |

**Проверка:**

- повтор с тем же ключом и нагрузкой возвращает одну строку;
- тот же ключ с другой нагрузкой возвращает стабильную ошибку конфликта;
- конечное действие, другой ученик и несовпадающая цель отклоняются;
- сохранённое событие не меняется после редактирования каталога или программы;
- тесты удаления секретов и сырого prompt провайдера.

---

#### [P2.T3] Реализовать проектор и консервативную MemoryPolicy v1

**Уровень:** Complex

**Файлы:**

```changeset
~ backend/app/domain/progress.py
+ backend/app/domain/policies.py
~ backend/app/repositories/domain.py
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
при replay событий в каноническом порядке `(occurred_at, event_id)`.

**Ключевые ограничения:**

- в v1 компетенцию и память обновляют только детерминированные события `response_evaluated`;
- знакомство, самостоятельная оценка и события с помощью модели увеличивают метаданные свидетельств,
  но не дают вклада в компетенцию и память;
- неверный детерминированный ответ не отменяет доступность узла программы;
- глобальной блокировки ученика нет; сериализуется одна строка ученика и цели;
- все временные метки используют UTC и корректные значения базы; время запроса измеряется
  монотонными часами до события.

##### Канонический блок: ALG-02 (ALG) (NORMATIVE)

> NORMATIVE. Алгоритм задаёт переход состояния `projection-v1` и `memory-v1`.

```text
insert event by (learner_id, idempotency_key)
if existing semantic event: return existing state without update
load or create LearnerTargetState for event.target_key with row lock
increment evidence_count and set last_evidence_at
if event is deterministic and outcome is correct:
    success_weight += 1
    interval_days = 1 if interval_days == 0 else min(interval_days * 2, 180)
    memory_due_at = occurred_at + interval_days
if event is deterministic and outcome is incorrect:
    failure_weight += 1
    interval_days = 0
    memory_lapses += 1
    memory_due_at = occurred_at
uncertainty = 2 / (2 + success_weight + failure_weight)
store projection_version='projection-v1' and memory_version='memory-v1'
commit event, activity transition and state atomically
```

**Проверка:**

- табличные тесты для каждого события, источника оценки и результата;
- replay и пошаговая проекция создают одинаковое состояние;
- дубликат события не меняет счётчики и расписание;
- две сессии PostgreSQL не могут применить один ключ идемпотентности;
- просроченное состояние не меняет доступность программы, потому что эти поля здесь не принадлежат.

---

#### [P2.T4] Перенести текущий прогресс как низкоуверенную проекцию

**Уровень:** Complex

**Файлы:**

```changeset
+ backend/app/services/legacy_progress_bootstrap_service.py
~ backend/app/repositories/domain.py
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
`UserWordProgress`. Цель — письменная `retrieve_form` для основной формы; старое расписание переносится
как память, но не как свидетельство компетенции. Синтетические `LearningEvent` не создаются.

Правила `legacy-bootstrap-v1`:

- `success_weight=0`, `failure_weight=0`, `evidence_count=0`, `uncertainty=1`;
- `memory_due_at` копирует нормализованный `next_review_at`; если он отсутствует, но текущая логика
  считает запись просроченной или weak, используется время запуска bootstrap;
- `memory_interval_days` копируется, `memory_lapses=0`, потому что `incorrect_count` смешивает
  результаты разных упражнений;
- `source_kind=legacy_bootstrap`, обе версии политик равны `legacy-bootstrap-v1`.

**Ключевые ограничения:**

- bootstrap-состояние не удовлетворяет HARD prerequisite и не становится native evidence;
- существующее состояние `native_event` никогда не перезаписывается;
- повторный запуск не меняет ID и не сдвигает срок, если исходная строка не изменилась;
- отсутствующее или неоднозначное сопоставление пропускается с диагностическим счётчиком, без
  придумывания цели;
- личные данные и сырой ответ ученика не журналируются.

**Проверка:**

- learned/seen/reviewing-строки дают только низкоуверенное состояние `retrieve_form`;
- due/weak/null-schedule сценарии совпадают с текущей семантикой срока;
- bootstrap не создаёт события и не открывает HARD-зависимость;
- native-event state сохраняется без изменений;
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

Добавить сценарии отката транзакции, конфликта идемпотентности, порядка replay, принадлежности
разным ученикам и конкуренции PostgreSQL. Проверить, что сбой проектора откатывает изменение события
и действия.

**Ключевые ограничения:**

- тесты не используют паузы как механизм корректности;
- конкурентная синхронизация строится на барьерах и событиях;
- ошибки переданной конфигурации PostgreSQL завершают тест ошибкой, а не пропуском.

**Проверка:**

- целевые тесты проходят на SQLite;
- цель конкуренции событий проходит на PostgreSQL;
- Ruff проходит для всех новых доменных, сервисных и тестовых модулей.

## Проверка фазы

**Автотесты:** модульные переходы состояния, интеграционная транзакция события, эквивалентность
replay, владение, идемпотентность и конкуренция PostgreSQL.

**Откат:** отключить вызывающие стороны сервиса P2 и откатить код; схему и события можно оставить.
Если понижается миграция P1, данные P2 удаляются вместе с новыми таблицами без влияния на текущую
модель.
